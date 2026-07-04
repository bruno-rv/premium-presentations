/**
 * Premium Presentations — presenter view.
 *
 * Architecture (per PLAN.md, 5-round Codex-approved):
 *   - Two windows: deck (audience-shared) + popup (presenter).
 *   - Per-session BroadcastChannel ('premium-deck' global) with sessionId in
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
 *
 * Seq allocator: PremiumPresenter.nextStateSeq() — monotonic counter shared
 *   across all modules. Popup reducer ignores messages with seq <= last seen
 *   per kind (slideSeq, timerSeq) to drop stale replays.
 */
(function () {
  const AUTO_OPEN_FLAG_KEY = 'premium-presenter-auto:';
  const HEARTBEAT_MS = 1000;
  const OPEN_AFTER_MS = 800;

  let channel = null;
  let popup = null;
  let popupTitle = '';
  let storageTick = 0;
  const STORAGE_KEY = 'premium-deck-msg';
  let commandIdCounter = 0;
  let _previewCounter = 0;
  let seenCommandIds = new Set();
  let heartbeatTimer = 0;
  let discoverTimer = 0;
  let popupTimerInterval = 0;
  let popupTimerState = null;
  let rehearsalInterval = 0;
  let fallbackPrompt = null;
  let openingTimer = 0;
  let postTransportInstalled = false;
  let autoOpenDone = false;

  const presenterState = {
    index: 0,
    total: 0,
    titles: [],
  };

  const rehearsalState = {
    active: false,
    currentIndex: 0,
    currentSince: 0,
    elapsedMs: 0,
    slideMs: [],
    visited: [],
  };

  // Monotonic seq counter shared with timer and any future modules.
  let _seq = 0;
  function nextStateSeq() {
    return ++_seq;
  }

  // Per-kind cursors for the popup reducer (Phase 2b).
  let slideSeq = 0;
  let timerSeq = 0;

  // Diagnostics — only when ?ppdiag=1.
  const DIAG = {
    sent: 0, recv: 0, lastSent: '', lastRecv: '',
    bcAvail: false, lsAvail: false, opener: false,
  };

  function isDiagMode() {
    return new URLSearchParams(location.search).get('ppdiag') === '1';
  }

  function updateDiag() {
    if (!isDiagMode()) return;
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
    return popup;
  }

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

    // presenter.discover and presenter.hereIam bypass session filtering:
    // they are the adoption handshake and must cross session boundaries.
    if (type === 'presenter.discover') {
      rememberPopupSource(e);
      try {
        const reply = { type: 'presenter.hereIam', deckSessionId: getSessionId() };
        if (e.source && typeof e.source.postMessage === 'function') {
          e.source.postMessage(reply, '*');
        } else if (popup && !popup.closed) {
          popup.postMessage(reply, '*');
        }
      } catch (_) {}
      return;
    }

    // Shared session filter: drop messages from a known foreign session.
    // Messages that carry no sessionId (legacy bundles without stamping) pass.
    const msgSid = e.data.sessionId || '';
    const ourSid = getSessionId();
    if (msgSid && ourSid && msgSid !== ourSid) return;

    // rememberPopupSource only for messages that passed the session gate.
    if (
      type === 'presenter.ready' ||
      type === 'presenter.heartbeat' ||
      type === 'presenter.closing' ||
      type === 'control'
    ) {
      rememberPopupSource(e);
    }

    DIAG.recv++;
    DIAG.lastRecv = e.data.type || '?';
    updateDiag();

    if (type === 'presenter.ready') {
      document.documentElement.dataset.presenterDisplay = 'on';
      document.documentElement.dataset.presenterOpening = 'false';
      document.title = 'Audience — ' + (document.title.replace(/^Presenter — /, '').replace(/^Audience — /, '') || 'deck');
      replyWithSnapshot();
    } else if (type === 'presenter.heartbeat') {
      if (window.PremiumController && typeof window.PremiumController.recordHeartbeat === 'function') {
        try { window.PremiumController.recordHeartbeat(!!e.data.popupFocused); } catch (_) {}
      }
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
      seq: nextStateSeq(),
      index: state.index,
      total: state.total,
      titles,
      notes,
      bodyHtmls,
      timer: window.PremiumTimer ? window.PremiumTimer.getState() : null,
    });
  }

  function handleControl(msg) {
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
    } else if (a === 'timer.toggle' && window.PremiumTimer) {
      if (window.PremiumTimer.getState().running) window.PremiumTimer.pause();
      else window.PremiumTimer.start();
    } else if (a === 'timer.start' && window.PremiumTimer) window.PremiumTimer.start();
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

  // Build a DOM clone of a slide for preview. Uses a deterministic rename-map to
  // give all IDs unique suffixes so that SVG url(#...) refs, data-* attributes,
  // and ARIA references remain internally consistent inside the clone.
  function buildSlidePreview(slide) {
    if (!slide) return null;
    const wrap = document.createElement('div');
    wrap.className = 'pp-preview';
    wrap.setAttribute('aria-hidden', 'true');

    const clone = slide.cloneNode(true);
    // Add .visible so deck CSS (`.slide { opacity: 0 }` unless `.visible`) shows the clone.
    clone.classList.add('visible');

    // Build rename map: include the clone root itself if it has an id,
    // plus all descendant elements with ids.
    const suffix = '-pp' + (++_previewCounter);
    const idMap = new Map();
    if (clone.id) {
      const newId = clone.id + suffix;
      idMap.set(clone.id, newId);
      clone.id = newId;
    }
    clone.querySelectorAll('[id]').forEach((el) => {
      const oldId = el.id;
      const newId = oldId + suffix;
      idMap.set(oldId, newId);
      el.id = newId;
    });

    function rewriteIdRef(oldRef) {
      return idMap.has(oldRef) ? idMap.get(oldRef) : oldRef;
    }

    function rewriteUrlHash(val) {
      if (!val) return val;
      return val.replace(/url\(#([^)]+)\)/g, (_, id) => 'url(#' + rewriteIdRef(id) + ')');
    }

    // Rewrite href / xlink:href fragment refs.
    clone.querySelectorAll('[href]').forEach((el) => {
      const v = el.getAttribute('href');
      if (v && v.startsWith('#')) el.setAttribute('href', '#' + rewriteIdRef(v.slice(1)));
    });
    clone.querySelectorAll('[xlink\\:href]').forEach((el) => {
      const v = el.getAttribute('xlink:href');
      if (v && v.startsWith('#')) el.setAttribute('xlink:href', '#' + rewriteIdRef(v.slice(1)));
    });

    // Rewrite url(#oldId) in inline style attributes and SVG presentation attributes.
    const SVG_PRES_ATTRS = ['fill', 'stroke', 'clip-path', 'mask', 'filter',
      'marker-start', 'marker-mid', 'marker-end'];
    clone.querySelectorAll('[style]').forEach((el) => {
      el.setAttribute('style', rewriteUrlHash(el.getAttribute('style')));
    });
    SVG_PRES_ATTRS.forEach((attr) => {
      clone.querySelectorAll('[' + attr + ']').forEach((el) => {
        el.setAttribute(attr, rewriteUrlHash(el.getAttribute(attr)));
      });
    });

    // Rewrite data-journey-gradient (id reference).
    clone.querySelectorAll('[data-journey-gradient]').forEach((el) => {
      const v = el.getAttribute('data-journey-gradient');
      if (v && idMap.has(v)) el.setAttribute('data-journey-gradient', idMap.get(v));
    });

    // Rewrite data-flow-phases JSON (ids may be embedded as strings).
    clone.querySelectorAll('[data-flow-phases]').forEach((el) => {
      const raw = el.getAttribute('data-flow-phases');
      try {
        const parsed = JSON.parse(raw);
        const json = JSON.stringify(parsed, (key, val) => {
          if (typeof val === 'string' && idMap.has(val)) return idMap.get(val);
          return val;
        });
        el.setAttribute('data-flow-phases', json);
      } catch (_) {
        el.removeAttribute('data-flow-phases');
      }
    });

    // Rewrite label for= and ARIA space-separated id lists.
    clone.querySelectorAll('[for]').forEach((el) => {
      el.setAttribute('for', rewriteIdRef(el.getAttribute('for')));
    });
    ['aria-labelledby', 'aria-describedby', 'aria-controls'].forEach((attr) => {
      clone.querySelectorAll('[' + attr + ']').forEach((el) => {
        const rewritten = el.getAttribute(attr).split(/\s+/)
          .map((id) => rewriteIdRef(id)).join(' ');
        el.setAttribute(attr, rewritten);
      });
    });

    // Strip notes from preview.
    clone.querySelectorAll('aside.notes, .slide__notes').forEach((n) => n.remove());

    wrap.appendChild(clone);
    return wrap;
  }

  function buildPopupDom() {
    document.title = popupTitle || ('Presenter — ' + (document.title || 'deck'));
    document.documentElement.dataset.controller = 'popup';
    document.body.classList.add('premium-presenter-popup');

    const sessionShort = escapeHtml(getSessionId().slice(0, 8));
    const diagAttr = isDiagMode() ? '' : ' hidden';

    // Grid layout: .premium-presenter is a direct-child grid container.
    // Children: __top (top), __instrument (main), __rail (rail), __status (status).
    // __rail is a direct child — NOT nested inside __instrument — so CSS grid-area works.
    const root = document.createElement('div');
    root.className = 'premium-presenter';
    root.innerHTML = `
      <header class="premium-presenter__top" id="pp-top">
        <div class="premium-presenter__title" id="pp-title">${escapeHtml(document.title.replace(/^Presenter — /, ''))}</div>
        <div class="premium-presenter__counter" id="pp-counter">– / –</div>
        <div class="premium-presenter__mode" id="pp-mode">—</div>
        <button type="button" class="premium-presenter__gear" id="pp-gear" aria-expanded="false" aria-controls="pp-timer-settings" title="Timer settings">⚙</button>
      </header>
      <section class="premium-presenter__instrument" id="pp-instrument">
        <div class="pp-previews" id="pp-previews">
          <div class="pp-previews__current" id="pp-preview-current" aria-label="Current slide preview"></div>
          <div class="pp-previews__next" id="pp-preview-next" aria-label="Next slide preview"></div>
        </div>
        <div class="premium-presenter__notes-panel" id="pp-notes-panel">
          <div class="premium-presenter__next-label">Next</div>
          <div class="premium-presenter__next-title" id="pp-next-title">—</div>
          <div class="premium-presenter__notes-label">Notes</div>
          <div class="premium-presenter__notes-body" id="pp-notes"></div>
        </div>
      </section>
      <section class="premium-presenter__timeline" id="pp-timeline-panel" aria-label="Presenter timeline">
        <div class="premium-presenter__timeline-head">
          <span>Timeline</span>
          <span id="pp-rehearsal-status">Rehearsal off</span>
        </div>
        <ol class="premium-presenter__timeline-list" id="pp-timeline"></ol>
      </section>
      <nav class="premium-presenter__rail" id="pp-rail" aria-label="Slide navigation" data-open="false">
        <button type="button" class="premium-presenter__rail-close" id="pp-rail-close" aria-label="Close slide list">✕</button>
        <div class="premium-presenter__rail-label">Slides</div>
        <ol class="premium-presenter__list" id="pp-list"></ol>
      </nav>
      <footer class="premium-presenter__status" id="pp-status">
        <span class="pp-status__dot" id="pp-status-dot" aria-label="Connection status"></span>
        <span id="pp-status-label">connecting…</span>
        <span id="pp-status-session">session: ${sessionShort}</span>
      </footer>
      <div class="premium-presenter__timer-bar" id="pp-timer-bar">
        <div class="premium-presenter__timer-time" id="pp-timer-time">--:--</div>
        <div class="premium-presenter__timer-pace" id="pp-timer-pace">—</div>
        <button type="button" id="pp-timer-startstop" class="pp-timer-btn">Start</button>
        <button type="button" id="pp-timer-reset" class="pp-timer-btn">Reset</button>
        <button type="button" id="pp-rehearsal-toggle" class="pp-timer-btn">Start rehearsal</button>
        <button type="button" id="pp-rehearsal-reset" class="pp-timer-btn">Clear</button>
      </div>
      <div class="premium-presenter__timer-settings" id="pp-timer-settings" hidden>
        <label>Mode
          <select id="pp-mode-select">
            <option value="duration">Duration</option>
            <option value="endAt">End time</option>
          </select>
        </label>
        <label>Minutes <input type="number" id="pp-minutes" min="1" max="600" step="1"></label>
        <label>End time <input type="time" id="pp-endtime"></label>
      </div>
      <div class="premium-presenter__diag" id="pp-diag"${diagAttr}></div>
    `;
    document.body.appendChild(root);

    bindPopupEvents();
    window.addEventListener('resize', recomputePreviewScales);
    sendReady();
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    heartbeatTimer = setInterval(sendHeartbeat, HEARTBEAT_MS);
    sendHeartbeat();
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
    postToPeer({ type: 'presenter.ready', sessionId: getSessionId(), seq: nextStateSeq() });
  }

  function sendHeartbeat() {
    postToPeer({
      type: 'presenter.heartbeat',
      sessionId: getSessionId(),
      popupFocused: document.hasFocus(),
      seq: nextStateSeq(),
    });
    const focused = document.hasFocus();
    const dot = document.getElementById('pp-status-dot');
    const label = document.getElementById('pp-status-label');
    if (dot) dot.dataset.state = focused ? 'connected-focused' : 'connected';
    if (label) label.textContent = focused ? 'focused' : 'connected (deck has input)';
    // Session can change via hereIam adoption — keep the footer label live.
    const sessionEl = document.getElementById('pp-status-session');
    if (sessionEl) sessionEl.textContent = 'session: ' + getSessionId().slice(0, 8);
  }

  function sendControl(action, extra) {
    postToPeer(Object.assign({
      type: 'control',
      sessionId: getSessionId(),
      commandId: ++commandIdCounter,
      action,
    }, extra || {}));
  }

  // Three transports: BroadcastChannel, window.postMessage, localStorage.
  // Receiver dedupes by commandId.
  function postToPeer(payload) {
    DIAG.sent++;
    DIAG.lastSent = payload.type || '?';
    updateDiag();
    try {
      const ch = getCh();
      if (ch) ch.postMessage(payload);
    } catch (_) {}
    try {
      if (isInPopup()) {
        if (window.opener && !window.opener.closed) window.opener.postMessage(payload, '*');
      } else if (popup && !popup.closed) {
        popup.postMessage(payload, '*');
      }
    } catch (_) {}
    try {
      storageTick++;
      const wrapped = JSON.stringify({ _t: storageTick, payload });
      localStorage.setItem(STORAGE_KEY, wrapped);
    } catch (_) {}
  }

  function bindPopupEvents() {
    // Timeline jump list.
    const timeline = document.getElementById('pp-timeline');
    if (timeline) {
      timeline.addEventListener('click', (e) => {
        const li = e.target.closest('li[data-index]');
        if (!li) return;
        const idx = parseInt(li.dataset.index, 10);
        if (Number.isInteger(idx)) sendControl('jump', { index: idx });
      });
    }

    // Rail jump list.
    document.getElementById('pp-list').addEventListener('click', (e) => {
      const li = e.target.closest('li[data-index]');
      if (!li) return;
      const idx = parseInt(li.dataset.index, 10);
      if (Number.isInteger(idx)) sendControl('jump', { index: idx });
    });

    // Rail toggle via keyboard (g) and close button.
    const rail = document.getElementById('pp-rail');
    const railClose = document.getElementById('pp-rail-close');
    if (railClose) {
      railClose.addEventListener('click', () => {
        if (rail) rail.dataset.open = 'false';
      });
    }

    // Gear → timer settings disclosure.
    const gear = document.getElementById('pp-gear');
    const timerSettings = document.getElementById('pp-timer-settings');
    if (gear && timerSettings) {
      gear.addEventListener('click', () => {
        const expanded = gear.getAttribute('aria-expanded') === 'true';
        gear.setAttribute('aria-expanded', expanded ? 'false' : 'true');
        timerSettings.hidden = expanded;
      });
    }

    // Timer bar buttons.
    const startStopBtn = document.getElementById('pp-timer-startstop');
    const resetBtn = document.getElementById('pp-timer-reset');
    if (startStopBtn) startStopBtn.addEventListener('click', () => sendControl('timer.toggle'));
    if (resetBtn) resetBtn.addEventListener('click', () => sendControl('timer.reset'));

    const rehearsalToggle = document.getElementById('pp-rehearsal-toggle');
    const rehearsalReset = document.getElementById('pp-rehearsal-reset');
    if (rehearsalToggle) rehearsalToggle.addEventListener('click', toggleRehearsal);
    if (rehearsalReset) rehearsalReset.addEventListener('click', resetRehearsal);

    // Timer settings inputs.
    const minutesInput = document.getElementById('pp-minutes');
    const endtimeInput = document.getElementById('pp-endtime');
    const modeSelect = document.getElementById('pp-mode-select');

    if (minutesInput) {
      let minutesDebounce = 0;
      minutesInput.addEventListener('input', () => {
        clearTimeout(minutesDebounce);
        minutesDebounce = setTimeout(() => {
          const m = parseFloat(minutesInput.value);
          if (Number.isFinite(m) && m > 0) sendControl('timer.setMinutes', { value: m });
        }, 400);
      });
    }

    if (endtimeInput) {
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
    }

    if (modeSelect) {
      modeSelect.addEventListener('change', () => {
        if (modeSelect.value === 'endAt') {
          if (endtimeInput) endtimeInput.focus();
        } else {
          if (minutesInput) {
            const m = parseFloat(minutesInput.value);
            if (Number.isFinite(m) && m > 0) sendControl('timer.setMinutes', { value: m });
          }
        }
      });
    }

    // Keyboard shortcuts.
    document.addEventListener('keydown', (e) => {
      if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA')) return;
      const key = e.key.toLowerCase();

      if (e.key === 'Escape') {
        e.preventDefault();
        // Close rail if open, else close popup.
        const r = document.getElementById('pp-rail');
        if (r && r.dataset.open === 'true') { r.dataset.open = 'false'; return; }
        try { window.close(); } catch (_) {}
        return;
      }
      if (key === 'g') {
        e.preventDefault();
        const r = document.getElementById('pp-rail');
        if (r) r.dataset.open = r.dataset.open === 'true' ? 'false' : 'true';
        return;
      }
      if (key === '?' || (e.key === '/' && e.shiftKey)) {
        e.preventDefault();
        return;
      }
      if (key === ' ' || e.code === 'ArrowRight' || e.code === 'ArrowDown' || e.code === 'PageDown') {
        e.preventDefault(); sendControl('next'); return;
      }
      if (e.code === 'ArrowLeft' || e.code === 'ArrowUp' || e.code === 'PageUp') {
        e.preventDefault(); sendControl('prev'); return;
      }
      if (key === 'b' || key === '.') { e.preventDefault(); sendControl('curtain'); return; }
      if (key === 'h') { e.preventDefault(); sendControl('controls.toggleHidden'); return; }
      if (e.code === 'Digit3') {
        e.preventDefault();
        sendControl('mode3d.cycle', { dir: e.shiftKey ? -1 : 1 });
        return;
      }
      if (key === 'r' && e.shiftKey) { e.preventDefault(); resetRehearsal(); return; }
      if (key === 'r') { e.preventDefault(); toggleRehearsal(); return; }
      if (key === 't' && e.shiftKey) { e.preventDefault(); sendControl('timer.toggle'); return; }
      if (key === 't') { e.preventDefault(); sendControl('theme.cycle'); return; }
    });
  }

  function ensureRehearsalSize(total) {
    const n = Math.max(0, total || presenterState.total || 0);
    while (rehearsalState.slideMs.length < n) rehearsalState.slideMs.push(0);
    while (rehearsalState.visited.length < n) rehearsalState.visited.push(false);
    if (rehearsalState.slideMs.length > n) rehearsalState.slideMs.length = n;
    if (rehearsalState.visited.length > n) rehearsalState.visited.length = n;
  }

  function hasRehearsalData() {
    return rehearsalState.elapsedMs > 0 || rehearsalState.slideMs.some((ms) => ms > 0);
  }

  function currentSlideElapsedMs(index) {
    ensureRehearsalSize();
    let ms = rehearsalState.slideMs[index] || 0;
    if (rehearsalState.active && rehearsalState.currentIndex === index && rehearsalState.currentSince) {
      ms += Math.max(0, Date.now() - rehearsalState.currentSince);
    }
    return ms;
  }

  function totalRehearsalElapsedMs() {
    let total = rehearsalState.elapsedMs || 0;
    if (rehearsalState.active && rehearsalState.currentSince) {
      total += Math.max(0, Date.now() - rehearsalState.currentSince);
    }
    return total;
  }

  function commitCurrentRehearsalSegment(now) {
    if (!rehearsalState.active || !rehearsalState.currentSince) return;
    ensureRehearsalSize();
    const delta = Math.max(0, now - rehearsalState.currentSince);
    const idx = rehearsalState.currentIndex;
    rehearsalState.elapsedMs += delta;
    rehearsalState.slideMs[idx] = (rehearsalState.slideMs[idx] || 0) + delta;
    rehearsalState.visited[idx] = true;
    rehearsalState.currentSince = now;
  }

  function startRehearsal() {
    ensureRehearsalSize();
    if (rehearsalState.active) return;
    rehearsalState.active = true;
    rehearsalState.currentIndex = presenterState.index || 0;
    rehearsalState.currentSince = Date.now();
    rehearsalState.visited[rehearsalState.currentIndex] = true;
    if (!rehearsalInterval) {
      rehearsalInterval = setInterval(renderTimeline, 1000);
    }
    renderTimeline();
  }

  function pauseRehearsal() {
    if (!rehearsalState.active) return;
    commitCurrentRehearsalSegment(Date.now());
    rehearsalState.active = false;
    rehearsalState.currentSince = 0;
    if (rehearsalInterval) {
      clearInterval(rehearsalInterval);
      rehearsalInterval = 0;
    }
    renderTimeline();
  }

  function toggleRehearsal() {
    if (rehearsalState.active) pauseRehearsal();
    else startRehearsal();
  }

  function resetRehearsal() {
    if (rehearsalInterval) {
      clearInterval(rehearsalInterval);
      rehearsalInterval = 0;
    }
    rehearsalState.active = false;
    rehearsalState.currentIndex = presenterState.index || 0;
    rehearsalState.currentSince = 0;
    rehearsalState.elapsedMs = 0;
    rehearsalState.slideMs = [];
    rehearsalState.visited = [];
    ensureRehearsalSize();
    renderTimeline();
  }

  function onPresenterSlideIndex(index, total) {
    presenterState.index = Number.isInteger(index) ? index : 0;
    presenterState.total = Number.isInteger(total) && total > 0 ? total : presenterState.total;
    ensureRehearsalSize();
    if (rehearsalState.active && presenterState.index !== rehearsalState.currentIndex) {
      commitCurrentRehearsalSegment(Date.now());
      rehearsalState.currentIndex = presenterState.index;
      rehearsalState.currentSince = Date.now();
      rehearsalState.visited[presenterState.index] = true;
    } else if (rehearsalState.active) {
      rehearsalState.visited[presenterState.index] = true;
    }
    renderTimeline();
  }

  function formatDuration(ms) {
    const totalSec = Math.max(0, Math.floor((ms || 0) / 1000));
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    if (h > 0) return h + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
    return m + ':' + String(s).padStart(2, '0');
  }

  function getPlannedSlideMs() {
    const s = derivePopupTimerState() || popupTimerState;
    const total = presenterState.total || 0;
    if (!s || !Number.isFinite(s.totalMs) || s.totalMs <= 0 || total <= 0) return 0;
    return s.totalMs / total;
  }

  function renderTimeline() {
    const list = document.getElementById('pp-timeline');
    const status = document.getElementById('pp-rehearsal-status');
    const toggle = document.getElementById('pp-rehearsal-toggle');
    if (!list) return;

    const total = presenterState.total || presenterState.titles.length || 0;
    ensureRehearsalSize(total);
    const plannedMs = getPlannedSlideMs();
    const titles = presenterState.titles.length ? presenterState.titles : Array.from({ length: total }, (_, i) => 'Slide ' + (i + 1));

    const timelineItemState = (i) => {
      const state = i === presenterState.index ? 'current' : (i < presenterState.index ? 'past' : 'upcoming');
      const actualMs = currentSlideElapsedMs(i);
      let rehearsal = 'idle';
      if (rehearsalState.active && i === rehearsalState.currentIndex) rehearsal = 'active';
      else if (rehearsalState.visited[i] || actualMs > 0) rehearsal = 'visited';
      const meta = actualMs > 0
        ? 'actual ' + formatDuration(actualMs)
        : (plannedMs > 0 ? 'plan ' + formatDuration(plannedMs) : 'not timed');
      return { state, rehearsal, meta };
    };

    // Update existing <li> nodes in place when the slide count is unchanged —
    // a full innerHTML rebuild every second (during rehearsal) resets scroll
    // position and drops focus/hover on the timeline list.
    const existing = list.querySelectorAll('li');
    if (existing.length === titles.length) {
      titles.forEach((_, i) => {
        const li = existing[i];
        const { state, rehearsal, meta } = timelineItemState(i);
        li.dataset.state = state;
        li.dataset.rehearsal = rehearsal;
        const metaEl = li.querySelector('.pp-timeline__meta');
        if (metaEl) metaEl.textContent = meta;
      });
    } else {
      list.innerHTML = titles.map((title, i) => {
        const { state, rehearsal, meta } = timelineItemState(i);
        return '<li data-index="' + i + '" data-state="' + state + '" data-rehearsal="' + rehearsal + '">' +
          '<button type="button">' +
            '<span class="pp-timeline__num">' + String(i + 1).padStart(2, '0') + '</span>' +
            '<span class="pp-timeline__title">' + escapeHtml(title) + '</span>' +
            '<span class="pp-timeline__meta">' + escapeHtml(meta) + '</span>' +
          '</button>' +
        '</li>';
      }).join('');
    }

    if (status) {
      if (rehearsalState.active) {
        status.textContent = 'Rehearsing · total ' + formatDuration(totalRehearsalElapsedMs());
      } else if (hasRehearsalData()) {
        status.textContent = 'Paused · total ' + formatDuration(totalRehearsalElapsedMs());
      } else {
        status.textContent = plannedMs > 0 ? 'Rehearsal off · plan ' + formatDuration(plannedMs) + '/slide' : 'Rehearsal off';
      }
    }
    if (toggle) {
      toggle.textContent = rehearsalState.active ? 'Pause rehearsal' : (hasRehearsalData() ? 'Resume rehearsal' : 'Start rehearsal');
    }
  }

  // Resolve content for a slide index.
  // Priority: local DOM (PremiumSlideContent) > wire notes > wire bodyHtml.
  function resolveSlideContent(idx, wireNotes, wireBody) {
    const slide = (function () {
      try {
        const deck = document.getElementById('deck');
        if (deck) return deck.querySelectorAll('.slide')[idx] || null;
      } catch (_) {}
      return null;
    })();

    if (slide && window.PremiumSlideContent) {
      const localNotes = window.PremiumSlideContent.getNotesHtml(slide);
      if (localNotes) return localNotes;
      const localSummary = window.PremiumSlideContent.getSummaryHtml(slide);
      if (localSummary) return localSummary;
    }
    return wireNotes || wireBody || '';
  }

  function getLocalSlide(idx) {
    try {
      const deck = document.getElementById('deck');
      if (!deck) return null;
      return deck.querySelectorAll('.slide')[idx] || null;
    } catch (_) { return null; }
  }

  function computePreviewScale(container) {
    const w = container.offsetWidth || 0;
    const h = container.offsetHeight || 0;
    const sw = w / 1280;
    const sh = h / 720;
    return Math.min(sw, sh) || 0.2;
  }

  function refreshPreviews(currentIdx, nextIdx) {
    const currentWrap = document.getElementById('pp-preview-current');
    const nextWrap = document.getElementById('pp-preview-next');
    if (!currentWrap || !nextWrap) return;

    const currentSlide = getLocalSlide(currentIdx);
    const nextSlide = nextIdx != null ? getLocalSlide(nextIdx) : null;

    currentWrap.innerHTML = '';
    nextWrap.innerHTML = '';

    if (currentSlide) {
      const preview = buildSlidePreview(currentSlide);
      if (preview) {
        preview.style.setProperty('--pp-preview-scale', computePreviewScale(currentWrap));
        currentWrap.appendChild(preview);
      }
    }
    if (nextSlide) {
      const preview = buildSlidePreview(nextSlide);
      if (preview) {
        preview.style.setProperty('--pp-preview-scale', computePreviewScale(nextWrap));
        nextWrap.appendChild(preview);
      }
    }
  }

  function recomputePreviewScales() {
    document.querySelectorAll('.pp-preview').forEach((preview) => {
      const container = preview.parentElement;
      if (container) {
        preview.style.setProperty('--pp-preview-scale', computePreviewScale(container));
      }
    });
  }

  function renderSnapshot(d) {
    // Seq filter: drop stale replays.
    if (d.seq != null && d.seq <= slideSeq) return;
    if (d.seq != null) slideSeq = d.seq;

    const counter = document.getElementById('pp-counter');
    if (counter) counter.textContent = (d.index + 1) + ' / ' + d.total;
    presenterState.titles = Array.isArray(d.titles) ? d.titles.slice() : [];
    onPresenterSlideIndex(d.index, d.total);
    const list = document.getElementById('pp-list');
    if (list && d.titles) {
      list.innerHTML = d.titles.map((t, i) =>
        '<li data-index="' + i + '" class="' + (i === d.index ? 'is-active' : '') + '">' + escapeHtml(t) + '</li>'
      ).join('');
    }
    const notes = d.notes || [];
    const bodies = d.bodyHtmls || [];
    const content = resolveSlideContent(d.index, notes[d.index], bodies[d.index]);
    renderNotes(content, getLocalSlide(d.index));
    const nextTitle = document.getElementById('pp-next-title');
    if (nextTitle) nextTitle.textContent = (d.titles && d.titles[d.index + 1]) || 'End of deck';
    refreshPreviews(d.index, d.index + 1 < d.total ? d.index + 1 : null);
    if (d.timer) renderTimer(d.timer);
    updateStatus('connected');
  }

  function renderSlidechange(d) {
    // Seq filter.
    if (d.seq != null && d.seq <= slideSeq) return;
    if (d.seq != null) slideSeq = d.seq;

    const counter = document.getElementById('pp-counter');
    if (counter) counter.textContent = (d.index + 1) + ' / ' + d.total;
    onPresenterSlideIndex(d.index, d.total);
    const list = document.getElementById('pp-list');
    if (list) {
      [...list.querySelectorAll('li')].forEach((li, i) => {
        li.classList.toggle('is-active', i === d.index);
      });
    }
    const content = resolveSlideContent(d.index, d.notes, d.bodyHtml);
    renderNotes(content, getLocalSlide(d.index));
    const nextTitle = document.getElementById('pp-next-title');
    if (nextTitle) nextTitle.textContent = d.nextTitle || 'End of deck';
    // Update previews if local DOM available.
    const total = d.total || 0;
    refreshPreviews(d.index, d.index + 1 < total ? d.index + 1 : null);
    updateStatus('connected');
  }

  function renderNotes(html, slideEl) {
    const el = document.getElementById('pp-notes');
    if (!el) return;
    el.innerHTML = html || '<em class="premium-presenter__no-notes">No notes for this slide</em>';
    // Append compact Terms section when the slide has glossary entries.
    try {
      const glossary = window.PremiumGlossary;
      if (glossary && typeof glossary.getTermsForSlide === 'function' && slideEl) {
        const terms = glossary.getTermsForSlide(slideEl);
        if (terms && terms.length > 0) {
          const existing = el.querySelector('.pp-notes-terms');
          if (existing) existing.remove();
          const section = document.createElement('div');
          section.className = 'pp-notes-terms';
          section.innerHTML =
            '<p class="pp-notes-terms__label">Terms</p>' +
            '<ul class="pp-notes-terms__list">' +
            terms.map(function (t) {
              return '<li><strong>' + escapeHtml(t.key) + '</strong> — ' + escapeHtml(t.body) + '</li>';
            }).join('') +
            '</ul>';
          el.appendChild(section);
        }
      }
    } catch (_) {}
  }

  function updateStatus(state) {
    const dot = document.getElementById('pp-status-dot');
    if (dot && state === 'connected') {
      dot.dataset.state = dot.dataset.state || 'connected';
    }
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
    const startStop = document.getElementById('pp-timer-startstop');

    if (!s) {
      if (time) time.textContent = '--:--';
      if (startStop) startStop.textContent = 'Start';
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
    if (startStop) startStop.textContent = s.running ? 'Pause' : 'Start';

    // Sync settings inputs (non-focused only).
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
    // Seq filter for timer messages.
    const seq = (s && s.seq) != null ? s.seq : null;
    if (seq != null && seq <= timerSeq) return;
    if (seq != null) timerSeq = seq;

    if (s) {
      popupTimerState = Object.assign({}, s, {
        receivedAtMs: Number.isFinite(s.ts) ? s.ts : Date.now(),
      });
      paintTimer(derivePopupTimerState());
      syncPopupTimerLoop();
      renderTimeline();
      return;
    }
    popupTimerState = null;
    paintTimer(null);
    syncPopupTimerLoop();
    renderTimeline();
  }

  function onPopupMessage(e) {
    if (!e.data) return;
    if (e.data.type === 'presenter.hereIam') {
      const deckSid = e.data.deckSessionId;
      if (deckSid && deckSid !== getSessionId()) {
        document.documentElement.dataset.session = deckSid;
        // Reset seq cursors so the reloaded deck's fresh seq stream (restarting
        // at 1) is not dropped as stale by the reducer.
        slideSeq = 0;
        timerSeq = 0;
        popupTimerState = null;
        resetRehearsal();
        renderTimer(null);
        sendReady();
      }
      return;
    }
    // Single session filter: ignore messages from other sessions
    // (once adopted via hereIam our sessionId tracks the deck).
    const msgSid = e.data.sessionId;
    if (msgSid && msgSid !== getSessionId()) return;

    DIAG.recv++;
    DIAG.lastRecv = e.data.type || '?';
    updateDiag();
    if (e.data.type === 'snapshot') renderSnapshot(e.data);
    else if (e.data.type === 'slidechange') renderSlidechange(e.data);
    else if (e.data.type === 'tick') renderTimer(e.data);
    else if (e.data.type === 'bell') flashTimerOnBell();
  }

  function sendDiscover() {
    try {
      if (window.opener && !window.opener.closed) {
        window.opener.postMessage({ type: 'presenter.discover', popupSessionId: getSessionId() }, '*');
      }
    } catch (_) {}
  }

  function flashTimerOnBell() {
    const el = document.getElementById('pp-timer-bar');
    if (!el) return;
    el.classList.remove('is-bell');
    void el.offsetWidth;
    el.classList.add('is-bell');
  }

  function onPopupUnload() {
    if (rehearsalInterval) clearInterval(rehearsalInterval);
    postToPeer({ type: 'presenter.closing', sessionId: getSessionId() });
  }

  // ─── init() ────────────────────────────────────────────────────────────────

  function init() {
    const sessionId = getSessionId();
    if (!sessionId) {
      console.warn('PremiumPresenter: no sessionId, presenter view disabled');
      return;
    }
    const ch = getCh();

    if (!postTransportInstalled) {
      postTransportInstalled = true;
      window.addEventListener('message', (e) => {
        if (!e.data || typeof e.data !== 'object') return;
        if (isInPopup()) onPopupMessage(e);
        else onDeckMessage(e);
      });
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
      try { DIAG.opener = !!(window.opener && !window.opener.closed); } catch (_) {}
      try { DIAG.bcAvail = !!(typeof BroadcastChannel === 'function' && getCh()); } catch (_) {}
      try { DIAG.lsAvail = !!localStorage; } catch (_) {}
      if (ch) ch.addEventListener('message', onPopupMessage);
      buildPopupDom();
      updateDiag();
      window.addEventListener('beforeunload', onPopupUnload);
      window.addEventListener('unload', onPopupUnload);
      return;
    }

    // Deck side.
    if (ch) ch.addEventListener('message', onDeckMessage);
    document.addEventListener('keydown', (e) => {
      if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      if (e.shiftKey && e.key.toLowerCase() === 'p') {
        e.preventDefault();
        openPopup();
      }
    });

    setInterval(monitorPopup, 2000);

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
    getRehearsalState: () => Object.assign({}, rehearsalState, {
      elapsedMs: totalRehearsalElapsedMs(),
      slideMs: rehearsalState.slideMs.map((_, i) => currentSlideElapsedMs(i)),
    }),
  };
  window.PremiumPresenter = Object.assign(window.PremiumPresenter || {}, {
    postToPeer,
    nextStateSeq,
  });
})();
