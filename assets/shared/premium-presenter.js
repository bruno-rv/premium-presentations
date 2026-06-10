/**
 * Premium Presentations — presenter view.
 *
 * Architecture (per PLAN.md, 5-round Codex-approved):
 *   - Two windows: deck (audience-shared) + popup (presenter).
 *   - Per-session BroadcastChannel ('premium-deck:<uuid>') with sessionId in
 *     every message. Mismatched sessionIds are ignored.
 *   - Initial handshake: popup sends `presenter.ready`, deck replies with
 *     `snapshot` (titles + notes + current index).
 *   - Heartbeat: popup sends `presenter.heartbeat` every 1s carrying
 *     `popupFocused`; deck takes over input if heartbeat is silent >2.5s
 *     OR if `popupFocused === false`.
 *   - Control: popup → deck via discriminated messages with `commandId`
 *     and `sessionId`; deck dedupes by commandId.
 *   - Popup URL: built by mutating a `new URL(location.href)` so hash and
 *     all existing query params are preserved. Window name is
 *     'premium-presenter:<sessionId>'.
 *   - On window.open null (popup blocked), show a small retry prompt in
 *     the deck window corner. NO notes, no jump list, no timer pill in
 *     the prompt — presenter content stays presenter-only.
 *   - Owner state machine: 'deck' | 'popup' | 'none'. See premium-controller.js.
 */
(function () {
  const AUTO_OPEN_FLAG_KEY = 'premium-presenter-auto:';
  const FALLBACK_RETRY_FLAG = 'premium-presenter-fallback-shown';
  const HEARTBEAT_MS = 1000;
  const OPEN_AFTER_MS = 800;  // wait for the first slide to settle before opening

  let channel = null;
  let popup = null;
  let popupTitle = '';
  let sessionId = '';
  let storageTick = 0;
  const STORAGE_KEY = 'premium-deck-msg';
  let commandIdCounter = 0;
  let seenCommandIds = new Set();
  let heartbeatTimer = 0;
  let discoverTimer = 0;
  let popupTimerInterval = 0;
  let popupTimerState = null;
  let fallbackPrompt = null;
  let openingTimer = 0;
  // window-message transport — needed for file:// origins where BroadcastChannel
  // is blocked by Chrome's opaque-origin rule. The deck holds a `popup` ref;
  // the popup reaches the deck via `window.opener`. Both transports are tried
  // on send; the dedup set on receive collapses any echo.
  let postTransportInstalled = false;
  let autoOpenDone = false;
  // Diagnostics (only when ?presenter=diag)
  const DIAG = {
    sent: 0, recv: 0, lastSent: '', lastRecv: '',
    bcAvail: false, lsAvail: false, opener: false,
  };
  function updateDiag() {
    const el = document.getElementById('pp-diag');
    if (!el) return;
    el.hidden = false;
    el.textContent =
      'opener=' + (DIAG.opener ? 'set' : 'null') +
      ' · bc=' + (DIAG.bcAvail ? 'ok' : 'NO') +
      ' · ls=' + (DIAG.lsAvail ? 'ok' : 'NO') +
      ' · sid=' + (getSessionId() || '').slice(0, 8) +
      ' · sent=' + DIAG.sent + (DIAG.lastSent ? ' (' + DIAG.lastSent + ')' : '') +
      ' · recv=' + DIAG.recv + (DIAG.lastRecv ? ' (' + DIAG.lastRecv + ')' : '');
  }

  function isInPopup() {
    return new URLSearchParams(location.search).get('presenter') === '1';
  }

  function getSessionId() {
    return document.documentElement.dataset.session || '';
  }

  function getCh() {
    if (!channel) {
      // Use a single global channel name. Per-session channels break when
      // either side reloads (the URL-stamped sessionId in the popup becomes
      // stale), forcing a discovery dance. The sessionId in the message
      // payload is still validated on receive, so wrong-target messages
      // are filtered out — and a single user only runs one deck at a time.
      try { channel = new BroadcastChannel('premium-deck'); } catch (_) { return null; }
    }
    return channel;
  }

  function shouldAutoOpen() {
    const params = new URLSearchParams(location.search);
    if (params.get('presenter') === 'off') return false;
    if (params.get('presenter') === 'auto') return true;
    try {
      return localStorage.getItem(AUTO_OPEN_FLAG_KEY + location.pathname) === '1';
    } catch (_) { return false; }
  }

  // Open the popup window. Chrome blocks window.open() without a user gesture,
  // so callers should be in a gesture context (one-shot click/keydown listener).
  function openPopup() {
    if (popup && !popup.closed) {
      popup.focus();
      return popup;
    }
    const sid = getSessionId();
    if (!sid) {
      console.warn('PremiumPresenter: no sessionId, cannot open popup');
      return null;
    }
    const popupUrl = new URL(location.href);
    popupUrl.searchParams.set('presenter', '1');
    popupUrl.searchParams.set('session', sid);
    // hash and all other params preserved automatically
    const features = 'popup,width=1280,height=720,left=' + Math.max(0, screen.width - 1300) + ',top=80';
    const windowName = 'premium-presenter:' + sid;
    popupTitle = 'Presenter — ' + (document.title || 'deck');
    try {
      popup = window.open(popupUrl.href, windowName, features);
    } catch (_) { popup = null; }
    if (!popup) {
      showFallbackPrompt();
      return null;
    }
    // Some browsers (Safari, some Chrome configs) set document.title in the new window
    // before the new page's scripts run. We can't reliably set it from here; the popup
    // itself sets its title from `document.title` after parsing query params.
    return popup;
  }

  // Show a small "popup blocked — click to retry" prompt in the deck window corner.
  // Critical: NO notes content here. The audience window must remain clean.
  function showFallbackPrompt() {
    if (fallbackPrompt) return;
    if (document.documentElement.dataset.presenterOpening === 'true') {
      document.documentElement.dataset.presenterOpening = 'false';
    }
    fallbackPrompt = document.createElement('div');
    fallbackPrompt.className = 'premium-presenter-fallback';
    fallbackPrompt.setAttribute('role', 'alert');
    fallbackPrompt.innerHTML =
      '<span class="premium-presenter-fallback__icon" aria-hidden="true">ⓘ</span>' +
      '<span class="premium-presenter-fallback__msg">Presenter window blocked — click to retry</span>' +
      '<button type="button" class="premium-presenter-fallback__btn">Retry</button>';
    document.body.appendChild(fallbackPrompt);
    fallbackPrompt.querySelector('.premium-presenter-fallback__btn')
      .addEventListener('click', () => {
        // A real click is a user gesture — window.open() will succeed.
        hideFallbackPrompt();
        try { localStorage.setItem(AUTO_OPEN_FLAG_KEY + location.pathname, '1'); } catch (_) {}
        openPopup();
      });
  }

  function hideFallbackPrompt() {
    if (fallbackPrompt) { fallbackPrompt.remove(); fallbackPrompt = null; }
  }

  function rememberPopupSource(e) {
    try {
      if (e && e.source && e.source !== window && typeof e.source.postMessage === 'function') {
        popup = e.source;
      }
    } catch (_) {}
  }

  // ─── Deck-side message handling ────────────────────────────────────────────

  function onDeckMessage(e) {
    if (!e.data) return;
    const type = e.data.type;
    if (!type) return;
    if (
      type === 'presenter.discover' ||
      type === 'presenter.ready' ||
      type === 'presenter.heartbeat' ||
      type === 'presenter.closing' ||
      type === 'control'
    ) {
      rememberPopupSource(e);
    }
    // The popup asks "who is the deck?" so it can re-sync session after the
    // deck reloads. Reply on the SAME transport the discover came in on —
    // otherwise popup might be listening on a stale session's channel.
    if (type === 'presenter.discover') {
      try {
        const reply = { type: 'presenter.hereIam', deckSessionId: getSessionId() };
        // Reply via window.postMessage to the popup (opener is the deck; popup
        // is the one that opened the request). postMessage is direct, so it
        // doesn't depend on channel sessionId matching.
        // But e.source is the actual popup window object (window.postMessage
        // sets it on the receiving side). Use it.
        if (e.source && typeof e.source.postMessage === 'function') {
          e.source.postMessage(reply, '*');
        } else if (popup && !popup.closed) {
          popup.postMessage(reply, '*');
        }
      } catch (_) {}
      return;
    }
    DIAG.recv++;
    DIAG.lastRecv = e.data.type || '?';
    try { updateDeckBadge(); } catch (_) {}

    if (type === 'presenter.ready') {
      // Popup is alive and ready. Hand over the deck.
      document.documentElement.dataset.presenterDisplay = 'on';
      document.documentElement.dataset.presenterOpening = 'false';
      document.title = 'Audience — ' + (document.title.replace(/^Presenter — /, '').replace(/^Audience — /, '') || 'deck');
      try { showDeckBadge(); updateDeckBadge(); } catch (_) {}
      replyWithSnapshot();
    } else if (type === 'presenter.heartbeat') {
      // Controller's listener already records this for the owner state machine.
      // The presenter-display attribute is set on the first ready, not on
      // every heartbeat (avoid flicker on transient connection blips).
    } else if (type === 'presenter.closing') {
      teardownPresenterMode();
    } else if (type === 'control' && e.data.action) {
      handleControl(e.data);
    }
  }

  function replyWithSnapshot() {
    if (!window.PremiumDeckControls) return;
    const titles = window.PremiumDeckControls.getTitles();
    const state = window.PremiumDeckControls.getState();
    const notes = [];
    const bodyHtmls = [];
    for (let i = 0; i < state.total; i++) {
      notes.push(window.PremiumDeckControls.getNotes(i) || '');
      bodyHtmls.push(window.PremiumDeckControls.getSummary ? (window.PremiumDeckControls.getSummary(i) || '') : '');
    }
    postToPeer({
      type: 'snapshot',
      sessionId: getSessionId(),
      index: state.index,
      total: state.total,
      titles,
      notes,
      bodyHtmls,
      timer: window.PremiumTimer ? window.PremiumTimer.getState() : null,
    });
  }

  function handleControl(msg) {
    // NOTE: we deliberately do NOT check msg.sessionId against our sessionId
    // here. The popup's URL-stamped sessionId can desync from the deck's
    // (e.g. the deck reloaded with a fresh randomUUID). The popup is the
    // only legitimate sender of control messages on this channel, and the
    // BroadcastChannel listener only runs on the popup's window. Accept.
    if (msg.commandId) {
      if (seenCommandIds.has(msg.commandId)) return;
      seenCommandIds.add(msg.commandId);
      if (seenCommandIds.size > 64) {
        const arr = [...seenCommandIds];
        seenCommandIds = new Set(arr.slice(-32));
      }
    }
    const a = msg.action;
    if (!window.PremiumDeckControls) return;
    if (a === 'next') window.PremiumDeckControls.next();
    else if (a === 'prev') window.PremiumDeckControls.prev();
    else if (a === 'jump' && Number.isInteger(msg.index)) window.PremiumDeckControls.goTo(msg.index);
    else if (a === 'curtain' && window.PremiumPresentations) window.PremiumPresentations.toggleCurtain();
    else if (a === 'controls.toggleHidden' && window.PremiumPresentations) window.PremiumPresentations.toggleControlsHidden();
    else if (a === 'theme.cycle' && window.PremiumPresentations) window.PremiumPresentations.cycleTheme();
    else if (a === 'parallax.toggle' && window.PremiumPresentations) window.PremiumPresentations.toggleParallax();
    else if (a === 'mode3d.cycle' && window.PremiumPresentations && window.PremiumPresentations.cycle3d) {
      window.PremiumPresentations.cycle3d(msg.dir === -1 ? -1 : 1);
    } else if (a === 'mode3d.set' && window.PremiumPresentations && window.PremiumPresentations.set3dMode) {
      window.PremiumPresentations.set3dMode(msg.value);
    }
    else if (a === 'timer.toggle' && window.PremiumTimer) {
      if (window.PremiumTimer.getState().running) window.PremiumTimer.pause();
      else window.PremiumTimer.start();
    }
    else if (a === 'timer.start' && window.PremiumTimer) window.PremiumTimer.start();
    else if (a === 'timer.pause' && window.PremiumTimer) window.PremiumTimer.pause();
    else if (a === 'timer.reset' && window.PremiumTimer) {
      window.PremiumTimer.reset();
    } else if (a === 'timer.setMinutes' && window.PremiumTimer) {
      try { window.PremiumTimer.setMinutes(msg.value); }
      catch (err) { console.warn('PremiumPresenter: setMinutes rejected', err); }
    } else if (a === 'timer.setEndAt' && window.PremiumTimer) {
      try { window.PremiumTimer.setEndAt(msg.value); }
      catch (err) { console.warn('PremiumPresenter: setEndAt rejected', err); }
    }
  }

  function teardownPresenterMode() {
    delete document.documentElement.dataset.presenterDisplay;
    delete document.documentElement.dataset.presenterOpening;
  }

  function monitorPopup() {
    if (!popup) return;
    if (popup.closed) {
      teardownPresenterMode();
      popup = null;
    }
  }

  // ─── Popup-side rendering ──────────────────────────────────────────────────

  function buildPopupDom() {
    document.title = popupTitle || ('Presenter — ' + (document.title || 'deck'));
    document.documentElement.dataset.controller = 'popup';
    document.body.classList.add('premium-presenter-popup');

    const root = document.createElement('div');
    root.className = 'premium-presenter';
    root.innerHTML = `
      <header class="premium-presenter__top">
        <div class="premium-presenter__title" id="pp-title">${escapeHtml(document.title.replace(/^Presenter — /, ''))}</div>
        <div class="premium-presenter__counter" id="pp-counter">– / –</div>
        <div class="premium-presenter__mode" id="pp-mode">—</div>
      </header>
      <main class="premium-presenter__main">
        <aside class="premium-presenter__notes" id="pp-notes-wrap">
          <h2 class="premium-presenter__next-label">Next slide</h2>
          <h3 class="premium-presenter__next-title" id="pp-next-title">—</h3>
          <h2 class="premium-presenter__notes-label">Notes</h2>
          <div class="premium-presenter__notes-body" id="pp-notes"></div>
        </aside>
        <nav class="premium-presenter__rail" id="pp-rail">
          <h2 class="premium-presenter__rail-label">Slides</h2>
          <ol class="premium-presenter__list" id="pp-list"></ol>
        </nav>
      </main>
      <footer class="premium-presenter__status" id="pp-status">
        <span>presenter: connecting…</span>
        <span>session: ${escapeHtml(getSessionId().slice(0, 8))}</span>
      </footer>
      <div class="premium-presenter__timer" id="pp-timer">
        <div class="premium-presenter__timer-time" id="pp-timer-time">--:--</div>
        <div class="premium-presenter__timer-pace" id="pp-timer-pace">—</div>
      </div>
      <div class="premium-presenter__controls" id="pp-controls">
        <label>Mode
          <select id="pp-mode-select">
            <option value="duration">Duration</option>
            <option value="endAt">End time</option>
          </select>
        </label>
        <label>Minutes <input type="number" id="pp-minutes" min="1" max="600" step="1"></label>
        <label>End time <input type="time" id="pp-endtime"></label>
        <button type="button" id="pp-start" data-action="start">Start ⇧T</button>
        <button type="button" id="pp-pause" data-action="pause">Pause</button>
        <button type="button" id="pp-reset" data-action="reset">Reset</button>
      </div>
      <div class="premium-presenter__diag" id="pp-diag" hidden></div>
    `;
    document.body.appendChild(root);

    bindPopupEvents();
    // Send initial handshake
    sendReady();
    // Heartbeat
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    heartbeatTimer = setInterval(sendHeartbeat, HEARTBEAT_MS);
    sendHeartbeat();
    // Discover poll — keeps the popup's sessionId in sync with the deck's
    // (which changes whenever the deck reloads). Every 2s is enough.
    if (discoverTimer) clearInterval(discoverTimer);
    discoverTimer = setInterval(sendDiscover, 2000);
    sendDiscover();
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function sendReady() {
    postToPeer({ type: 'presenter.ready', sessionId: getSessionId(), seq: ++commandIdCounter });
  }

  function sendHeartbeat() {
    postToPeer({
      type: 'presenter.heartbeat',
      sessionId: getSessionId(),
      popupFocused: document.hasFocus(),
      seq: ++commandIdCounter,
    });
    // Update the status line
    const status = document.getElementById('pp-status');
    if (status) {
      const focused = document.hasFocus();
      status.firstElementChild.textContent =
        'presenter: ' + (focused ? 'connected (focused)' : 'connected (unfocused — deck has input)');
    }
  }

  function sendControl(action, extra) {
    postToPeer(Object.assign({
      type: 'control',
      sessionId: getSessionId(),
      commandId: ++commandIdCounter,
      action,
    }, extra || {}));
  }

  // Send a payload to the peer window. Tries BOTH BroadcastChannel and a
  // direct window.postMessage (which works on file:// where BC is blocked).
  // The receiver dedupes by commandId, so even if multiple transports land, only
  // the first is processed. Three transports, in order of preference:
  //   1) BroadcastChannel — fast, works on http/https same-origin.
  //   2) window.postMessage — direct ref, works on file:// popups opened via
  //      window.open (the popup is also a file:// but Chrome still permits
  //      postMessage between them when opener was set at open time).
  //   3) localStorage 'storage' event — most reliable on file:// because it
  //      does not require any origin relationship. Also catches the case
  //      where the popup was opened in a separate tab (no opener reference).
  function postToPeer(payload) {
    DIAG.sent++;
    DIAG.lastSent = payload.type || '?';
    updateDiag();
    // 1) BroadcastChannel
    try {
      const ch = getCh();
      if (ch) ch.postMessage(payload);
    } catch (_) {}
    // 2) window.postMessage
    try {
      if (isInPopup()) {
        if (window.opener && !window.opener.closed) window.opener.postMessage(payload, '*');
      } else if (popup && !popup.closed) {
        popup.postMessage(payload, '*');
      }
    } catch (_) {}
    // 3) localStorage storage event. Global key — same rationale as the
    //    global BroadcastChannel name: the popup is the only legitimate
    //    sender, and the receiver validates by channel/listener, not by
    //    storage key. Per-session keys would break when either side reloads.
    try {
      storageTick++;
      const wrapped = JSON.stringify({ _t: storageTick, payload });
      localStorage.setItem(STORAGE_KEY, wrapped);
    } catch (_) {}
  }

  function bindPopupEvents() {
    // Wire jump list clicks
    document.getElementById('pp-list').addEventListener('click', (e) => {
      const li = e.target.closest('li[data-index]');
      try { console.log('[PP-popup] rail click target=' + (e.target && e.target.tagName) + ' text=' + ((e.target && e.target.textContent || '').slice(0, 30)) + ' li=' + (li ? li.dataset.index : 'null')); } catch (_) {}
      if (!li) return;
      const idx = parseInt(li.dataset.index, 10);
      if (Number.isInteger(idx)) {
        try { console.log('[PP-popup] sending control.jump index=' + idx + ' sid=' + getSessionId().slice(0, 8)); } catch (_) {}
        sendControl('jump', { index: idx });
      }
    });

    // Timer controls
    const minutesInput = document.getElementById('pp-minutes');
    const endtimeInput = document.getElementById('pp-endtime');
    const modeSelect = document.getElementById('pp-mode-select');

    let minutesDebounce = 0;
    minutesInput.addEventListener('input', () => {
      clearTimeout(minutesDebounce);
      minutesDebounce = setTimeout(() => {
        const m = parseFloat(minutesInput.value);
        if (Number.isFinite(m) && m > 0) sendControl('timer.setMinutes', { value: m });
      }, 400);
    });
    let endtimeDebounce = 0;
    endtimeInput.addEventListener('input', () => {
      clearTimeout(endtimeDebounce);
      endtimeDebounce = setTimeout(() => {
        const v = endtimeInput.value;
        if (!v) return;
        const [h, mm] = v.split(':').map(Number);
        if (!Number.isFinite(h) || !Number.isFinite(mm)) return;
        const target = new Date();
        target.setHours(h, mm, 0, 0);
        if (target.getTime() <= Date.now()) target.setDate(target.getDate() + 1);
        sendControl('timer.setEndAt', { value: target.getTime() });
      }, 400);
    });
    modeSelect.addEventListener('change', () => {
      if (modeSelect.value === 'endAt') {
        // Switch UI to end-time input; deck will recompute mode.
        endtimeInput.focus();
      } else {
        // Revert to duration; the most recently set minutes (or current default) applies.
        const m = parseFloat(minutesInput.value);
        if (Number.isFinite(m) && m > 0) sendControl('timer.setMinutes', { value: m });
      }
    });
    document.getElementById('pp-start').addEventListener('click', () => sendControl('timer.start'));
    document.getElementById('pp-pause').addEventListener('click', () => sendControl('timer.pause'));
    document.getElementById('pp-reset').addEventListener('click', () => sendControl('timer.reset'));

    // Keyboard
    document.addEventListener('keydown', (e) => {
      if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA')) return;
      const key = e.key.toLowerCase();
      if (e.key === 'Escape') { e.preventDefault(); try { window.close(); } catch (_) {} return; }
      if (key === ' ' || e.code === 'ArrowRight' || e.code === 'ArrowDown' || e.code === 'PageDown') {
        e.preventDefault(); sendControl('next'); return;
      }
      if (e.code === 'ArrowLeft' || e.code === 'ArrowUp' || e.code === 'PageUp') {
        e.preventDefault(); sendControl('prev'); return;
      }
      if (key === 'h') { e.preventDefault(); sendControl('controls.toggleHidden'); return; }
      // e.code, not e.key: Shift+3 produces layout-specific characters.
      if (e.code === 'Digit3') {
        e.preventDefault();
        sendControl('mode3d.cycle', { dir: e.shiftKey ? -1 : 1 });
        return;
      }
      if (key === 't' && e.shiftKey) { e.preventDefault(); sendControl('timer.toggle'); return; }
      if (key === 't') { e.preventDefault(); sendControl('theme.cycle'); return; }
      if (key === 'b' || key === '.') { e.preventDefault(); sendControl('curtain'); return; }
      if (key === 'd') { e.preventDefault(); sendControl('curtain'); return; }  // deck blackout = curtain
    });
  }

  function renderSnapshot(d) {
    const counter = document.getElementById('pp-counter');
    if (counter) counter.textContent = (d.index + 1) + ' / ' + d.total;
    const list = document.getElementById('pp-list');
    if (list && d.titles) {
      list.innerHTML = d.titles.map((t, i) =>
        `<li data-index="${i}" class="${i === d.index ? 'is-active' : ''}">${escapeHtml(t)}</li>`
      ).join('');
    }
    const notes = d.notes || [];
    const bodies = d.bodyHtmls || [];
    renderNotes(notes[d.index] || bodies[d.index] || '');
    const nextTitle = document.getElementById('pp-next-title');
    if (nextTitle) nextTitle.textContent = (d.titles && d.titles[d.index + 1]) || 'End of deck';
    // Timer state from snapshot
    if (d.timer) renderTimer(d.timer);
  }

  function renderSlidechange(d) {
    const counter = document.getElementById('pp-counter');
    if (counter) counter.textContent = (d.index + 1) + ' / ' + d.total;
    const list = document.getElementById('pp-list');
    if (list) {
      [...list.querySelectorAll('li')].forEach((li, i) => {
        li.classList.toggle('is-active', i === d.index);
      });
    }
    renderNotes(d.notes || d.bodyHtml || '');
    const nextTitle = document.getElementById('pp-next-title');
    if (nextTitle) nextTitle.textContent = d.nextTitle || 'End of deck';
  }

  function renderNotes(html) {
    const el = document.getElementById('pp-notes');
    if (el) el.innerHTML = html || '<em class="premium-presenter__no-notes">No notes for this slide</em>';
  }

  function derivePopupTimerState() {
    if (!popupTimerState) return null;
    const base = popupTimerState;
    const elapsedSinceUpdate = Math.max(0, Date.now() - (base.receivedAtMs || Date.now()));
    const next = Object.assign({}, base);
    if (base.running) {
      if (base.mode === 'endAt' && base.targetEndAtMs) {
        next.remainingMs = Math.max(0, base.targetEndAtMs - Date.now());
        next.elapsedMs = Math.max(0, (base.totalMs || 0) - next.remainingMs);
      } else {
        next.remainingMs = Math.max(0, (base.remainingMs || 0) - elapsedSinceUpdate);
        next.elapsedMs = (base.elapsedMs || 0) + elapsedSinceUpdate;
      }
      if (next.remainingMs <= 0) next.running = false;
    }
    return next;
  }

  function syncPopupTimerLoop() {
    if (!isInPopup()) return;
    const running = !!(popupTimerState && popupTimerState.running && popupTimerState.remainingMs > 0);
    if (!running) {
      if (popupTimerInterval) {
        clearInterval(popupTimerInterval);
        popupTimerInterval = 0;
      }
      return;
    }
    if (popupTimerInterval) return;
    popupTimerInterval = setInterval(() => {
      const next = derivePopupTimerState();
      paintTimer(next);
      if (!next || !next.running) {
        if (popupTimerState) popupTimerState.running = false;
        syncPopupTimerLoop();
      }
    }, 250);
  }

  function paintTimer(s) {
    const time = document.getElementById('pp-timer-time');
    const pace = document.getElementById('pp-timer-pace');
    const modeEl = document.getElementById('pp-mode');
    if (!s) {
      if (time) time.textContent = '--:--';
      return;
    }
    if (time) {
      const totalSec = Math.max(0, Math.ceil((s.remainingMs || 0) / 1000));
      const m = Math.floor(totalSec / 60);
      const ss = totalSec % 60;
      time.textContent = m + ':' + (ss < 10 ? '0' + ss : ss);
    }
    if (pace) pace.textContent = (s.state || 'ok');
    if (modeEl) modeEl.textContent = s.mode === 'endAt' ? 'ends at ' + new Date(s.targetEndAtMs).toLocaleTimeString() : Math.round((s.totalMs || 0) / 60000) + ' min';
    // Reflect current mode + value into the controls (without re-posting).
    const minutesInput = document.getElementById('pp-minutes');
    const endtimeInput = document.getElementById('pp-endtime');
    const modeSelect = document.getElementById('pp-mode-select');
    if (modeSelect && s.mode) modeSelect.value = s.mode === 'endAt' ? 'endAt' : 'duration';
    if (minutesInput && s.mode === 'duration' && s.totalMs) {
      const current = Math.round(s.totalMs / 60000);
      if (document.activeElement !== minutesInput) minutesInput.value = current;
    }
    if (endtimeInput && s.mode === 'endAt' && s.targetEndAtMs) {
      const d = new Date(s.targetEndAtMs);
      const hh = String(d.getHours()).padStart(2, '0');
      const mm = String(d.getMinutes()).padStart(2, '0');
      if (document.activeElement !== endtimeInput) endtimeInput.value = hh + ':' + mm;
    }
  }

  function renderTimer(s) {
    if (s) {
      popupTimerState = Object.assign({}, s, {
        receivedAtMs: Number.isFinite(s.ts) ? s.ts : Date.now(),
      });
      paintTimer(derivePopupTimerState());
      syncPopupTimerLoop();
      return;
    }
    popupTimerState = null;
    paintTimer(null);
    syncPopupTimerLoop();
  }

  function onPopupMessage(e) {
    if (!e.data) return;
    // Special case: the deck's `presenter.hereIam` carries the deck's actual
    // sessionId, which may differ from the popup's (stale URL param). Adopt
    // the deck's session and rebuild the BroadcastChannel.
    if (e.data.type === 'presenter.hereIam') {
      const deckSid = e.data.deckSessionId;
      if (deckSid && deckSid !== getSessionId()) {
        try { console.log('[PP-popup] adopting deck session ' + deckSid.slice(0, 8) + ' (was ' + getSessionId().slice(0, 8) + ')'); } catch (_) {}
        document.documentElement.dataset.session = deckSid;
        // getCh() will close the old channel and open a new one on next call.
        // Re-send ready so the deck can reply with the snapshot on the new channel.
        sendReady();
      }
      return;
    }
    // Accept any message from the deck regardless of sessionId — the deck
    // may have reloaded with a fresh randomUUID. If the deck told us its
    // new sessionId via presenter.hereIam, we already adopted it. Any
    // subsequent slidechange/snapshot/tick we accept unconditionally.
    DIAG.recv++;
    DIAG.lastRecv = e.data.type || '?';
    updateDiag();
    if (e.data.type === 'snapshot') renderSnapshot(e.data);
    else if (e.data.type === 'slidechange') renderSlidechange(e.data);
    else if (e.data.type === 'tick') renderTimer(e.data);
    else if (e.data.type === 'bell') flashTimerOnBell();
  }

  // Popup periodically asks "who is the deck?" so it can re-sync if the deck
  // reloaded with a new session. Targets the opener (deck window) directly.
  function sendDiscover() {
    try {
      if (window.opener && !window.opener.closed) {
        window.opener.postMessage({ type: 'presenter.discover', popupSessionId: getSessionId() }, '*');
      }
    } catch (_) {}
  }

  function flashTimerOnBell() {
    const el = document.getElementById('pp-timer');
    if (!el) return;
    el.classList.remove('is-bell');
    void el.offsetWidth;  // restart animation
    el.classList.add('is-bell');
  }

  function onPopupUnload() {
    // Tell the deck we're going away so it can tear down presenter mode quickly.
    // postToPeer covers both BroadcastChannel (http) and window.postMessage (file://).
    postToPeer({ type: 'presenter.closing', sessionId: getSessionId() });
  }

  // ─── init() ────────────────────────────────────────────────────────────────

  function init() {
    sessionId = getSessionId();
    if (!sessionId) {
      console.warn('PremiumPresenter: no sessionId, presenter view disabled');
      return;
    }
    // Channel is optional: BroadcastChannel may be unavailable (e.g. on
    // file:// in Chrome, where each window has an opaque origin). The
    // postMessage + localStorage 'storage' transports installed below
    // cover that case.
    const ch = getCh();

    // window.message is the file://-compatible transport; install before any
    // send so the popup's `presenter.ready` (sent synchronously inside
    // buildPopupDom) can be answered by the deck's replyWithSnapshot via the
    // same path.
    if (!postTransportInstalled) {
      postTransportInstalled = true;
      window.addEventListener('message', (e) => {
        if (!e.data || typeof e.data !== 'object') return;
        // The popup is the only legitimate sender on this window (other than
        // the deck sending itself). Accept any payload that has a type we
        // recognize, regardless of sessionId — the per-receiver handlers
        // (handleControl, onPopupMessage) apply their own filtering where
        // it matters.
        if (isInPopup()) onPopupMessage(e);
        else onDeckMessage(e);
      });
      // localStorage 'storage' event — the reliable file:// transport. Fires
      // on every OTHER window of the same origin (and on file:// Chrome treats
      // each tab as same-origin for this event) when our key is written.
      window.addEventListener('storage', (e) => {
        if (e.key !== STORAGE_KEY) return;
        if (!e.newValue) return;
        let parsed;
        try { parsed = JSON.parse(e.newValue); } catch (_) { return; }
        const payload = parsed && parsed.payload;
        if (!payload) return;
        if (isInPopup()) onPopupMessage({ data: payload });
        else onDeckMessage({ data: payload });
      });
    }

    if (isInPopup()) {
      // Detect capabilities for diagnostics
      try { DIAG.opener = !!(window.opener && !window.opener.closed); } catch (_) {}
      try { DIAG.bcAvail = !!(typeof BroadcastChannel === 'function' && getCh()); } catch (_) {}
      try { DIAG.lsAvail = !!localStorage; } catch (_) {}
      // Attach the listener BEFORE buildPopupDom(): buildPopupDom calls
      // sendReady() synchronously, and the deck's replyWithSnapshot() must
      // land on a listener that exists. Otherwise the popup would miss its
      // first snapshot and stay empty until the next slidechange.
      if (ch) ch.addEventListener('message', onPopupMessage);
      buildPopupDom();
      updateDiag();
      window.addEventListener('beforeunload', onPopupUnload);
      window.addEventListener('unload', onPopupUnload);
      return;
    }

    // Deck side
    if (ch) ch.addEventListener('message', onDeckMessage);
    // ⇧P opens popup
    document.addEventListener('keydown', (e) => {
      if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      if (e.shiftKey && e.key.toLowerCase() === 'p') {
        e.preventDefault();
        openPopup();
      }
    });

    // Deck-side diag — small badge top-right when presenter is connected.
    // Shows last received message type and recv count, so the user can
    // confirm controls actually land on the deck.
    function showDeckBadge() {
      let badge = document.getElementById('pp-deck-badge');
      if (badge) { badge.hidden = false; return; }
      badge = document.createElement('div');
      badge.id = 'pp-deck-badge';
      badge.className = 'pp-deck-badge';
      badge.textContent = 'presenter: connecting…';
      document.body.appendChild(badge);
    }
    function updateDeckBadge() {
      const badge = document.getElementById('pp-deck-badge');
      if (!badge) return;
      if (document.documentElement.dataset.presenterDisplay === 'on') {
        badge.textContent = 'presenter: ON · recv=' + DIAG.recv + (DIAG.lastRecv ? ' (' + DIAG.lastRecv + ')' : '');
      } else {
        badge.textContent = 'presenter: connecting… · recv=' + DIAG.recv;
      }
    }

    // Poll popup liveness; not authoritative, but responsive to X-button
    setInterval(monitorPopup, 2000);

    // Auto-open if requested, on first user gesture
    if (shouldAutoOpen()) {
      document.documentElement.dataset.presenterOpening = 'true';
      const onGesture = () => {
        document.removeEventListener('click', onGesture, true);
        document.removeEventListener('keydown', onGesture, true);
        if (autoOpenDone) return;
        autoOpenDone = true;
        openingTimer = setTimeout(() => {
          openPopup();
        }, OPEN_AFTER_MS);
      };
      document.addEventListener('click', onGesture, true);
      document.addEventListener('keydown', onGesture, true);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumPresenterView = {
    openPopup,
    isInPopup,
    sessionId: () => getSessionId(),
  };
  // Expose postToPeer so other modules (e.g. SlideEngine on deck side) can
  // broadcast via the SAME 3 transports popup listens on: global BC,
  // window.message to the popup, and localStorage. Without this, the deck's
  // slidechange went out on a per-session BC the popup never subscribed to.
  window.PremiumPresenter = Object.assign(window.PremiumPresenter || {}, {
    postToPeer,
  });
})();
