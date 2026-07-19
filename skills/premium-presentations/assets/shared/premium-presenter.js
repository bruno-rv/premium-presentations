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
  let rehearsalRunTs = 0;   // identity of the in-progress run; 0 = none open
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

  function directTargetOrigin() {
    return location.protocol === 'http:' || location.protocol === 'https:'
      ? location.origin
      : '*';
  }

  function hasTrustedDirectOrigin(e) {
    if (location.protocol !== 'http:' && location.protocol !== 'https:') return true;
    return !!e && e.origin === location.origin;
  }

  function getOpener() {
    try { return window.opener && !window.opener.closed ? window.opener : null; }
    catch (_) { return null; }
  }

  function isPresenterChildSource(source) {
    try {
      if (!source || source.opener !== window) return false;
    } catch (_) { return false; }
    try {
      if (!source.location || typeof source.location.search !== 'string') return false;
      return new URLSearchParams(source.location.search).get('presenter') === '1';
    } catch (_) {
      // Opaque file:// WindowProxy access can reject location inspection even
      // when opener identity is available; source/session checks still apply.
      return true;
    }
  }

  // ─── Deck-side message handling ────────────────────────────────────────────

  function onDeckMessage(e, transport) {
    if (!e.data) return;
    const type = e.data.type;
    if (!type) return;

    // Direct-window adoption is the sole session-boundary exception. It must
    // come from the same origin (when origins exist) and from a real child
    // WindowProxy. Once a popup is known, a different source cannot replace it.
    if (type === 'presenter.discover') {
      if (transport !== 'window' || !hasTrustedDirectOrigin(e)) return;
      try {
        if (!e.source || e.source === window || typeof e.source.postMessage !== 'function') return;
        const knownPopup = popup && !popup.closed ? popup : null;
        if (knownPopup && knownPopup !== e.source) return;
        if (!knownPopup && !isPresenterChildSource(e.source)) return;
        popup = e.source;
      } catch (_) { return; }
      try {
        const reply = { type: 'presenter.hereIam', deckSessionId: getSessionId() };
        e.source.postMessage(reply, directTargetOrigin());
      } catch (_) {}
      return;
    }

    const msgSid = e.data.sessionId || '';
    const ourSid = getSessionId();
    if (!msgSid || !ourSid || msgSid !== ourSid) return;
    if (transport === 'window') {
      if (!hasTrustedDirectOrigin(e)) return;
      try {
        if (!popup || popup.closed || e.source !== popup) return;
      } catch (_) { return; }
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
        <div class="premium-presenter__budgets" id="pp-budget-block" data-empty="true">
          <div class="pp-budget__head">Suggested budgets (median of your runs)
            <button type="button" class="pp-budget__copy">Copy</button></div>
          <pre></pre>
        </div>
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
        <button type="button" id="pp-rehearsal-export" class="pp-timer-btn">Export JSON</button>
        <button type="button" id="pp-rehearsal-clear-history" class="pp-timer-btn">Clear history</button>
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
    loadTeleprompterSettings();
    renderSuggestedBudgets();
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

  function sanitizeNotesHtml(html) {
    const template = document.createElement('template');
    template.innerHTML = String(html == null ? '' : html);
    const allowedTags = new Set([
      'A', 'B', 'BLOCKQUOTE', 'BR', 'CODE', 'DD', 'DL', 'DT', 'EM',
      'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'I', 'LI', 'MARK', 'OL',
      'P', 'PRE', 'SMALL', 'SPAN', 'STRONG', 'SUB', 'SUP', 'U', 'UL',
    ]);
    const dangerous = template.content.querySelectorAll(
      'script, style, iframe, object, embed, svg, math, form, input, button, ' +
      'textarea, select, link, meta, base'
    );
    dangerous.forEach((el) => el.remove());

    Array.from(template.content.querySelectorAll('*')).forEach((el) => {
      if (!allowedTags.has(el.tagName)) {
        const parent = el.parentNode;
        if (!parent) return;
        while (el.firstChild) parent.insertBefore(el.firstChild, el);
        el.remove();
        return;
      }

      Array.from(el.attributes).forEach((attr) => {
        const name = attr.name.toLowerCase();
        const allowed = name === 'class' || name === 'title' || (
          el.tagName === 'A' && (name === 'href' || name === 'target' || name === 'rel')
        );
        if (!allowed || name.startsWith('on')) el.removeAttribute(attr.name);
      });

      if (el.tagName === 'A' && el.hasAttribute('href')) {
        const href = el.getAttribute('href').trim();
        if (!/^(?:#|https?:|mailto:)/i.test(href)) el.removeAttribute('href');
      }
      if (el.tagName === 'A' && (el.getAttribute('target') || '').toLowerCase() === '_blank') {
        el.setAttribute('target', '_blank');
        el.setAttribute('rel', 'noopener noreferrer');
      }
    });
    return template.innerHTML;
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
        const opener = getOpener();
        if (opener) opener.postMessage(payload, directTargetOrigin());
      } else if (popup && !popup.closed) {
        popup.postMessage(payload, directTargetOrigin());
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
    const rehearsalExport = document.getElementById('pp-rehearsal-export');
    const rehearsalClearHistory = document.getElementById('pp-rehearsal-clear-history');
    if (rehearsalToggle) rehearsalToggle.addEventListener('click', toggleRehearsal);
    if (rehearsalReset) rehearsalReset.addEventListener('click', resetRehearsal);
    if (rehearsalExport) rehearsalExport.addEventListener('click', exportRehearsalJson);
    if (rehearsalClearHistory) rehearsalClearHistory.addEventListener('click', clearRehearsalHistory);

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
      if (key === 'm') { e.preventDefault(); toggleTeleprompterMode(); return; }
      if (key === 'p') { e.preventDefault(); toggleTeleprompterScroll(); return; }
      if (e.code === 'BracketRight') { e.preventDefault(); nudgeTeleprompterRate(+1); return; }
      if (e.code === 'BracketLeft')  { e.preventDefault(); nudgeTeleprompterRate(-1); return; }
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
    persistRun();     // primary commit boundary (ADR-2)
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
    rehearsalRunTs = 0;
    rehearsalState.active = false;
    rehearsalState.currentIndex = presenterState.index || 0;
    rehearsalState.currentSince = 0;
    rehearsalState.elapsedMs = 0;
    rehearsalState.slideMs = [];
    rehearsalState.visited = [];
    ensureRehearsalSize();
    renderTimeline();
  }

  // ─── Rehearsal persistence (R1) ─────────────────────────────────────────────
  // A run is the full contents of rehearsalState for one start→stop session,
  // identified by rehearsalRunTs (assigned on the first start after a reset).
  // Committed on pauseRehearsal (primary boundary) and onPopupUnload
  // (crash-safety); upsert-by-ts makes pause→resume→pause and
  // beforeunload+unload double-fire idempotent (ADR-2).

  const REHEARSAL_PREFIX = 'premium-rehearsal:';
  const REHEARSAL_MAX_RUNS = 10;

  function rehearsalKey() { return REHEARSAL_PREFIX + location.pathname; }

  // A run is well-formed only if every field downstream code dereferences
  // without a guard is present and of the right shape: {ts, totalMs, slideMs[]}.
  // Malformed entries (hand-edited localStorage, storage corruption, a future
  // schema mismatch) are dropped silently at read time so persistRun's
  // `r.ts === ts` and eligibleRuns'/medianOf's `r.slideMs[...]` never see them.
  function isValidRehearsalRun(r) {
    if (!r || typeof r !== 'object' || Array.isArray(r)) return false;
    if (!Number.isFinite(r.ts) || !Number.isFinite(r.totalMs)) return false;
    if (!Array.isArray(r.slideMs)) return false;
    return r.slideMs.every((ms) => Number.isFinite(ms) && ms >= 0);
  }

  function readRehearsalStore() {
    try {
      const raw = localStorage.getItem(rehearsalKey());
      if (!raw) return { version: 1, slideCount: presenterState.total || 0, runs: [] };
      const o = JSON.parse(raw);
      if (!o || o.version !== 1 || !Array.isArray(o.runs)) throw 0;
      o.runs = o.runs.filter(isValidRehearsalRun);   // sanitize: drop malformed runs, keep valid ones
      return o;
    } catch (_) {
      return { version: 1, slideCount: presenterState.total || 0, runs: [] };
    }
  }

  function writeRehearsalStore(store) {
    try {
      store.slideCount = presenterState.total || store.slideCount || 0;
      if (store.runs.length > REHEARSAL_MAX_RUNS) {
        store.runs = store.runs.slice(-REHEARSAL_MAX_RUNS);   // evict oldest
      }
      localStorage.setItem(rehearsalKey(), JSON.stringify(store));
    } catch (_) {}   // localStorage unavailable → degrade to in-memory (assumption logged)
  }

  function pinnedTimerTotalMs() {
    const s = derivePopupTimerState() || popupTimerState;
    return (s && Number.isFinite(s.totalMs)) ? s.totalMs : 0;
  }

  // Upsert-by-ts: pause→resume→pause and beforeunload+unload are idempotent.
  function persistRun() {
    commitCurrentRehearsalSegment(Date.now());
    if (!hasRehearsalData()) return;                 // pollution guard
    const store = readRehearsalStore();
    if (!rehearsalRunTs) {
      let ts = Date.now();
      // Same-ms collision with a DIFFERENT run (stubbed clocks, fast automation):
      // bump until unique so the second run appends instead of replacing the first.
      while (store.runs.some((r) => r.ts === ts)) ts++;
      rehearsalRunTs = ts;
    }
    const run = {
      ts: rehearsalRunTs,
      totalMs: pinnedTimerTotalMs(),                 // planned basis at commit
      slideMs: rehearsalState.slideMs.slice(),
    };
    const at = store.runs.findIndex((r) => r.ts === rehearsalRunTs);
    if (at >= 0) store.runs[at] = run; else store.runs.push(run);
    writeRehearsalStore(store);
  }

  function clearRehearsalHistory() {                 // "Clear history" (R1.5)
    try { localStorage.removeItem(rehearsalKey()); } catch (_) {}
    renderTimeline();
  }

  function eligibleRuns(store) {
    const n = presenterState.total || 0;
    return (store.runs || []).filter((r) => Array.isArray(r.slideMs) && r.slideMs.length === n);
  }

  function medianOf(values) {                        // integer ms; even → round of mid-pair
    const v = values.slice().sort((a, b) => a - b);
    const n = v.length;
    if (n === 0) return 0;
    const mid = n >> 1;
    return (n % 2) ? v[mid] : Math.round((v[mid - 1] + v[mid]) / 2);
  }

  function perSlideMedians(store) {
    const runs = eligibleRuns(store);
    const n = presenterState.total || 0;
    if (!runs.length) return null;                   // caller renders the fallback note
    const out = new Array(n);
    for (let j = 0; j < n; j++) out[j] = medianOf(runs.map((r) => r.slideMs[j] || 0));
    return out;
  }

  // Per-slide actual for a slide index, sourced from live rehearsal if active
  // (or paused-with-data), else from the most-recent persisted run eligible
  // for THIS deck's slide count (ADR-2/ADR-3).
  function displayedSlideMs(index) {
    if (rehearsalState.active || hasRehearsalData()) return currentSlideElapsedMs(index);
    const runs = eligibleRuns(readRehearsalStore());
    const last = runs[runs.length - 1];
    return (last && last.slideMs[index]) || 0;
  }

  function formatSignedDuration(ms) {
    return (ms < 0 ? '-' : '+') + formatDuration(Math.abs(ms || 0));
  }

  // ─── Slide Budget grammar (Tier 2, PLAN.md Workstream A) ───────────────────
  // The single JS counterpart to slide_spec.py's Python serializer — both
  // agree on every vector in scripts/tests/budget-vectors.json. Budget (ms)
  // is authoritative: decimal integer, no sign/whitespace, min 1000, max
  // 7200000, JS safe-integer. Budget (mm:ss) is the derived display and must
  // equal floor(ms/1000) zero-padded.
  const BUDGET_MS_MIN = 1000;
  const BUDGET_MS_MAX = 7200000;
  const BUDGET_MS_RE = /^[0-9]+$/;
  const BUDGET_MMSS_RE = /^[0-9]{2,}:[0-5][0-9]$/;

  function formatBudgetMmss(ms) {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
  }

  function validateBudgetMs(value) {                 // throws on any grammar violation
    if (typeof value !== 'string' || !BUDGET_MS_RE.test(value)) {
      throw new Error('invalid_budget_ms: not a decimal integer with no sign/whitespace: ' + JSON.stringify(value));
    }
    const ms = Number(value);
    if (!Number.isSafeInteger(ms)) {
      throw new Error('invalid_budget_ms: exceeds JS safe-integer range: ' + value);
    }
    if (ms < BUDGET_MS_MIN || ms > BUDGET_MS_MAX) {
      throw new Error('invalid_budget_ms: out of range [' + BUDGET_MS_MIN + ', ' + BUDGET_MS_MAX + ']: ' + ms);
    }
    return ms;
  }

  function validateBudgetMmss(value, ms) {           // throws on grammar or mm:ss/ms disagreement
    if (typeof value !== 'string' || !BUDGET_MMSS_RE.test(value)) {
      throw new Error('invalid_budget_mmss: does not match ^\\d{2,}:[0-5]\\d$: ' + JSON.stringify(value));
    }
    const expected = formatBudgetMmss(ms);
    if (value !== expected) {
      throw new Error('budget_mismatch: ' + value + ' != floor(ms/1000) ' + expected + ' for ' + ms + ' ms');
    }
  }

  // readSlideBudgets() — the single runtime reader, on the normalized DOM
  // (duplicate source attributes are invisible post-parse by construction;
  // catching those is the Python validator's raw-markup-scan job). Accepts
  // only a complete, valid, uniquely-identified data-budget vector; anything
  // else — including the common all-absent budgetless case — atomically
  // returns null so every consumer falls back to vs-average/manual-scroll.
  // Exactly one console diagnostic fires, only for a genuine partial/invalid
  // authoring error (never for a plain budgetless deck).
  function readSlideBudgets() {
    const nodes = Array.prototype.slice.call(document.querySelectorAll('#deck > .slide'));
    if (!nodes.length) return null;
    let present = 0;
    let valid = true;
    const vector = [];
    const ids = [];
    const seenIds = new Set();
    for (let i = 0; i < nodes.length; i++) {
      const node = nodes[i];
      const raw = node.getAttribute('data-budget');
      const id = node.getAttribute('id') || '';
      if (raw != null) present++;
      if (!id || seenIds.has(id)) valid = false; else seenIds.add(id);
      if (raw == null) { valid = false; continue; }
      try {
        vector.push(validateBudgetMs(raw));
        ids.push(id);
      } catch (_) {
        valid = false;
      }
    }
    if (present === 0) return null;                  // budgetless — expected, no diagnostic
    if (!valid || present !== nodes.length) {
      console.warn('PremiumPresenter: readSlideBudgets() found an incomplete or invalid data-budget vector; falling back to vs-average/manual-scroll.');
      return null;
    }
    return { vector, ids };
  }

  // readSlideIdentities() — stable Slide Map IDs read off the same normalized
  // DOM, independent of budget validity (a deck can have stable IDs without
  // budgets). null means legacy: no ID, or a duplicate ID, somewhere.
  function readSlideIdentities() {
    const nodes = Array.prototype.slice.call(document.querySelectorAll('#deck > .slide'));
    if (!nodes.length) return null;
    const ids = nodes.map((node) => node.getAttribute('id') || '');
    if (ids.some((id) => !id) || new Set(ids).size !== ids.length) return null;
    return ids;
  }

  // ─── Centralized planned-time vector + comparison-label helper ────────────
  // One computation, memoized (readSlideBudgets' DOM scan is cheap but this
  // keeps the "one console diagnostic" contract exact). ALL consumers —
  // timeline deltas, the status line, getLastRunDeltas(), and export labels —
  // route through budgetPlan()/plannedTimeFor()/comparisonLabel() so "vs
  // plan" (budgeted) vs "vs average" (fallback) can never disagree.
  let budgetPlanCache;                                // undefined until first computed
  function budgetPlan() {
    if (budgetPlanCache === undefined) budgetPlanCache = readSlideBudgets();
    return budgetPlanCache;
  }

  function plannedTimeFor(index) {
    const plan = budgetPlan();
    if (plan && Number.isInteger(index) && index >= 0 && index < plan.vector.length) {
      return plan.vector[index];
    }
    return getPlannedSlideMs();                       // uniform-average fallback
  }

  function comparisonLabel() {
    return budgetPlan() ? 'vs plan' : 'vs average';
  }

  // ─── Rehearsal suggested-budget export (ID-keyed, sample-gated) ───────────
  function escapeMarkdownCell(value) {
    return String(value == null ? '' : value)
      .replace(/\\/g, '\\\\')
      .replace(/\|/g, '\\|')
      .replace(/\r\n|\r|\n/g, '<br>');
  }

  function slideEligibility(store) {                  // per-slide: >=1 in-range observation?
    const runs = eligibleRuns(store);
    const total = presenterState.total || 0;
    const out = new Array(total);
    for (let i = 0; i < total; i++) {
      out[i] = runs.some((r) => {
        const ms = r.slideMs[i] || 0;
        return ms >= BUDGET_MS_MIN && ms <= BUDGET_MS_MAX;
      });
    }
    return out;
  }

  function buildSuggestedBudgetExport() {
    const store = readRehearsalStore();
    const medians = perSlideMedians(store);
    if (!medians) {
      return { ok: false, reason: 'no_runs', message: 'No comparable runs for this deck length yet.' };
    }
    const identities = readSlideIdentities();
    const titles = presenterState.titles;
    const labelFor = (i) => identities ? identities[i] : ((i + 1) + ' — ' + (titles[i] || 'Slide ' + (i + 1)));
    const eligible = slideEligibility(store);
    const offending = [];
    eligible.forEach((ok, i) => { if (!ok) offending.push(labelFor(i)); });
    if (offending.length) {
      return {
        ok: false,
        reason: 'insufficient_samples',
        message: 'Refusing export — no in-range observation (1,000–7,200,000 ms) for: ' + offending.join(', '),
      };
    }
    const identityMode = identities ? 'id' : 'ordinal';
    const rows = medians.map((ms, i) => ({
      id: identities ? identities[i] : null,
      ordinal: i + 1,
      title: titles[i] || ('Slide ' + (i + 1)),
      mmss: formatBudgetMmss(ms),
      ms,
    }));
    return { ok: true, identityMode, rows };
  }

  function buildBudgetMarkdown(result) {
    if (!result.ok) return result.message;
    if (result.identityMode === 'id') {
      const rows = result.rows.map((r) =>
        '| ' + escapeMarkdownCell(r.id) + ' | ' + r.mmss + ' | ' + r.ms + ' |');
      return '| ID | Budget (mm:ss) | Budget (ms) |\n' +
             '|----|----------------|-------------|\n' + rows.join('\n');
    }
    const rows = result.rows.map((r) =>
      '| ' + r.ordinal + ' | ' + escapeMarkdownCell(r.title) + ' | ' + r.mmss + ' | ' + r.ms + ' |');
    return '| # | Title | Budget (mm:ss) | Budget (ms) |\n' +
           '|---|-------|----------------|-------------|\n' + rows.join('\n') +
           '\n\n_Legacy deck without stable Slide Map IDs — initialize stable IDs before merging._';
  }

  function renderSuggestedBudgets() {                // R1.4, ADR-5 (superseded by PLAN.md Workstream A)
    const host = document.getElementById('pp-budget-block');
    if (!host) return;
    const pre = host.querySelector('pre');
    const result = buildSuggestedBudgetExport();
    host.dataset.empty = result.ok ? 'false' : 'true';
    const md = buildBudgetMarkdown(result);
    if (pre) pre.textContent = md;
    const copyBtn = host.querySelector('.pp-budget__copy');
    if (copyBtn) {
      copyBtn.onclick = () => {
        try { navigator.clipboard.writeText(md); } catch (_) {}
      };
    }
  }

  function exportRehearsalJson() {                   // "Export JSON" (R1.5)
    const result = buildSuggestedBudgetExport();
    const payload = JSON.stringify(
      result.ok
        ? {
            v: 2,
            identity: result.identityMode,
            rows: result.rows.map((r) => (
              result.identityMode === 'id'
                ? { id: r.id, mmss: r.mmss, ms: r.ms }
                : { ordinal: r.ordinal, title: r.title, mmss: r.mmss, ms: r.ms }
            )),
          }
        : { v: 2, error: result.reason, message: result.message },
      null,
      2
    );
    try { navigator.clipboard.writeText(payload); } catch (_) {}
    return payload;
  }

  // ─── Teleprompter mode (R2 + PLAN.md Workstream B) ────────────────────────
  // Distance-reading mode toggle (`m`, CSS class only, no motion). `p` is the
  // one and only play-intent gesture (start/pause/resume) — reduced-motion
  // invariant (AT2): nothing else may ever start motion (mode toggle, slide
  // change, load, or state restoration).
  //
  // Engage rule (step 7): a deck with a complete valid budgetPlan() gets
  // TIMED scroll; otherwise the manual constant-px/s path is untouched.
  //
  // Timed progress model (step 8): progress = accumulatedProgress +
  // (performance.now() - epoch) * multiplier / budgetMs, clamped [0,1];
  // scrollTop = progress * (scrollHeight - clientHeight). setInterval below
  // only drives repaint — position is always derived from performance.now(),
  // never accumulated tick-by-tick. Target distance (scrollHeight -
  // clientHeight) is read live on every tick, so it is automatically
  // "remeasured" after notes render, mode toggle, glossary/font settle, and
  // resize — no separate cache/invalidation is needed. No overflow -> no
  // motion, no division.
  //
  // State machine (step 9): pause commits elapsed progress into
  // accumulatedProgress and clears only the epoch (position holds); resume
  // keeps accumulatedProgress and sets a fresh epoch (continues, no restart,
  // no jump). A genuine slide change zeroes accumulatedProgress and — while
  // play intent is on — sets a fresh epoch, so motion continues without a new
  // keypress. A multiplier change ([`/`]`) commits progress under the OLD
  // multiplier, then rebases the epoch, so the new rate never applies
  // retroactively. Popup close/reopen clears everything (fresh module state).

  const TELEPROMPTER_KEY = 'premium-teleprompter';
  const RATE_MIN = 10, RATE_MAX = 240, RATE_STEP = 10, TP_TICK_MS = 50;
  const MULT_MIN = 5, MULT_MAX = 20, MULT_STEP = 1;    // integer tenths; 10 = x1.0 (step 10)
  const teleprompterState = {
    mode: false,
    scrolling: false,          // play intent
    rate: 40,                  // manual px/s
    multiplierTenths: 10,      // timed speed multiplier, clamped [5,20] = x0.5-x2.0
    timer: 0,
    accumulatedProgress: 0,    // timed mode only, clamped [0,1]
    epoch: null,                // performance.now() at last (re)start; null while paused
  };
  let lastTeleprompterSlideIndex = null;

  function prefersReducedMotion() {
    try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
    catch (_) { return false; }
  }

  function clampRate(r) { return Math.min(RATE_MAX, Math.max(RATE_MIN, r)); }
  function clampMultiplierTenths(m) { return Math.min(MULT_MAX, Math.max(MULT_MIN, m)); }
  function clampProgress(p) { return Math.min(1, Math.max(0, p)); }

  function isTimedEngaged() {                          // step 7 engage rule
    return !!budgetPlan();
  }

  function currentBudgetMs() {
    const plan = budgetPlan();
    const idx = presenterState.index;
    if (!plan || !Number.isInteger(idx) || idx < 0 || idx >= plan.vector.length) return 0;
    return plan.vector[idx];
  }

  function loadTeleprompterSettings() {
    try {
      const raw = localStorage.getItem(TELEPROMPTER_KEY);
      if (raw == null) return;
      let parsed;
      try { parsed = JSON.parse(raw); } catch (_) { parsed = null; }
      if (parsed && typeof parsed === 'object' && parsed.v === 2) {
        if (Number.isFinite(parsed.manualRate) && parsed.manualRate > 0) {
          teleprompterState.rate = clampRate(parsed.manualRate);
        }
        if (Number.isInteger(parsed.multiplierTenths)) {
          teleprompterState.multiplierTenths = clampMultiplierTenths(parsed.multiplierTenths);
        }
        return;
      }
      const legacy = parseFloat(raw);                  // legacy plain-numeric-string schema
      if (Number.isFinite(legacy) && legacy > 0) teleprompterState.rate = clampRate(legacy);
    } catch (_) {}
  }

  function saveTeleprompterSettings() {                 // always writes the v2 schema — migrates
    try {                                                //  the legacy string on first write
      localStorage.setItem(TELEPROMPTER_KEY, JSON.stringify({
        v: 2,
        manualRate: teleprompterState.rate,
        multiplierTenths: teleprompterState.multiplierTenths,
      }));
    } catch (_) {}
  }

  function toggleTeleprompterMode() {                // key 'm' — NO motion here (AT2)
    teleprompterState.mode = !teleprompterState.mode;
    const notes = document.getElementById('pp-notes');
    if (notes) notes.classList.toggle('pp-notes--teleprompter', teleprompterState.mode);
    if (!teleprompterState.mode) stopTeleprompterScroll();
  }

  function commitTimedProgress() {                    // freeze elapsed-since-epoch into accumulatedProgress
    if (teleprompterState.epoch == null) return;
    const budgetMs = currentBudgetMs();
    if (budgetMs > 0) {
      const elapsed = performance.now() - teleprompterState.epoch;
      const multiplier = teleprompterState.multiplierTenths / 10;
      teleprompterState.accumulatedProgress = clampProgress(
        teleprompterState.accumulatedProgress + elapsed * multiplier / budgetMs
      );
    }
  }

  function teleprompterTick(notes) {
    if (isTimedEngaged()) {
      const distance = notes.scrollHeight - notes.clientHeight;
      if (distance <= 0 || teleprompterState.epoch == null) return; // no overflow -> no motion, no division
      const budgetMs = currentBudgetMs();
      if (!(budgetMs > 0)) return;
      const elapsed = performance.now() - teleprompterState.epoch;
      const multiplier = teleprompterState.multiplierTenths / 10;
      const progress = clampProgress(
        teleprompterState.accumulatedProgress + elapsed * multiplier / budgetMs
      );
      notes.scrollTop = progress * distance;
    } else {
      notes.scrollTop += teleprompterState.rate * (TP_TICK_MS / 1000);
    }
  }

  function startTeleprompterScroll() {                // key 'p' — the EXPLICIT start (or resume)
    if (teleprompterState.scrolling) return;
    const notes = document.getElementById('pp-notes');
    if (!notes) return;
    teleprompterState.scrolling = true;                // explicit user gesture; allowed even
                                                         //  under reduced-motion (never AUTO)
    if (isTimedEngaged()) teleprompterState.epoch = performance.now(); // resume keeps accumulatedProgress
    teleprompterState.timer = setInterval(() => teleprompterTick(notes), TP_TICK_MS);
  }

  function stopTeleprompterScroll() {
    if (teleprompterState.scrolling && isTimedEngaged()) commitTimedProgress();
    teleprompterState.scrolling = false;
    teleprompterState.epoch = null;                    // clear only the epoch; accumulatedProgress holds
    if (teleprompterState.timer) { clearInterval(teleprompterState.timer); teleprompterState.timer = 0; }
  }

  function toggleTeleprompterScroll() {               // key 'p'
    if (teleprompterState.scrolling) stopTeleprompterScroll(); else startTeleprompterScroll();
  }

  function nudgeTeleprompterRate(dir) {                // keys '[' / ']'
    if (isTimedEngaged()) {
      commitTimedProgress();                           // freeze progress under the OLD multiplier
      teleprompterState.multiplierTenths = clampMultiplierTenths(
        teleprompterState.multiplierTenths + dir * MULT_STEP
      );
      if (teleprompterState.scrolling) teleprompterState.epoch = performance.now(); // rebase — no jump
    } else {
      teleprompterState.rate = clampRate(teleprompterState.rate + dir * RATE_STEP);
    }
    saveTeleprompterSettings();
  }

  function resetTeleprompterForSlideChange(index) {    // step 9 — zero on every genuine slide change
    if (index === lastTeleprompterSlideIndex) return;
    lastTeleprompterSlideIndex = index;
    if (!isTimedEngaged()) return;
    teleprompterState.accumulatedProgress = 0;
    teleprompterState.epoch = teleprompterState.scrolling ? performance.now() : null;
  }

  function onPresenterSlideIndex(index, total) {
    presenterState.index = Number.isInteger(index) ? index : 0;
    presenterState.total = Number.isInteger(total) && total > 0 ? total : presenterState.total;
    resetTeleprompterForSlideChange(presenterState.index);
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
    const titles = presenterState.titles.length ? presenterState.titles : Array.from({ length: total }, (_, i) => 'Slide ' + (i + 1));

    const timelineItemState = (i) => {
      const state = i === presenterState.index ? 'current' : (i < presenterState.index ? 'past' : 'upcoming');
      const actualMs = displayedSlideMs(i);       // live if rehearsing, else restored (ADR-2)
      let rehearsal = 'idle';
      if (rehearsalState.active && i === rehearsalState.currentIndex) rehearsal = 'active';
      else if (rehearsalState.visited[i] || actualMs > 0) rehearsal = 'visited';
      // Per-slide planned time — the Slide Budget when the deck is budgeted,
      // else the uniform average — routed through the one centralized helper
      // (PLAN.md Workstream A step 4) so every consumer agrees.
      const plannedMs = plannedTimeFor(i);
      const meta = actualMs > 0
        ? 'actual ' + formatDuration(actualMs)
        : (plannedMs > 0 ? 'plan ' + formatDuration(plannedMs) : 'not timed');
      // Delta vs plan/average (R1.3/R1.6). Rendered only inside this <li>'s
      // own delta span — #pp-timer-pace (the timer's live pace pill) is never
      // read or written here (ADR-6).
      const deltaMs = (plannedMs > 0 && actualMs > 0) ? Math.round(actualMs - plannedMs) : 0;
      const delta = deltaMs !== 0 ? formatSignedDuration(deltaMs) + ' ' + comparisonLabel() : '';
      return { state, rehearsal, meta, delta };
    };

    // Update existing <li> nodes in place when the slide count is unchanged —
    // a full innerHTML rebuild every second (during rehearsal) resets scroll
    // position and drops focus/hover on the timeline list.
    const existing = list.querySelectorAll('li');
    if (existing.length === titles.length) {
      titles.forEach((_, i) => {
        const li = existing[i];
        const { state, rehearsal, meta, delta } = timelineItemState(i);
        li.dataset.state = state;
        li.dataset.rehearsal = rehearsal;
        const metaEl = li.querySelector('.pp-timeline__meta');
        if (metaEl) metaEl.textContent = meta;
        let deltaEl = li.querySelector('.pp-timeline__delta');
        if (!deltaEl && metaEl) {
          deltaEl = document.createElement('span');
          deltaEl.className = 'pp-timeline__delta';
          metaEl.insertAdjacentElement('afterend', deltaEl);
        }
        if (deltaEl) deltaEl.textContent = delta;
      });
    } else {
      list.innerHTML = titles.map((title, i) => {
        const { state, rehearsal, meta, delta } = timelineItemState(i);
        return '<li data-index="' + i + '" data-state="' + state + '" data-rehearsal="' + rehearsal + '">' +
          '<button type="button">' +
            '<span class="pp-timeline__num">' + String(i + 1).padStart(2, '0') + '</span>' +
            '<span class="pp-timeline__title">' + escapeHtml(title) + '</span>' +
            '<span class="pp-timeline__meta">' + escapeHtml(meta) + '</span>' +
            '<span class="pp-timeline__delta">' + escapeHtml(delta) + '</span>' +
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
        // Route through the centralized helper: a real per-slide "plan" when
        // budgeted, an honestly-labeled uniform "average" otherwise — never
        // claim a uniform figure is a "plan" (PLAN.md Workstream A step 4).
        const currentPlanMs = plannedTimeFor(presenterState.index);
        const label = budgetPlan() ? 'plan' : 'average';
        status.textContent = currentPlanMs > 0
          ? 'Rehearsal off · ' + label + ' ' + formatDuration(currentPlanMs) + '/slide'
          : 'Rehearsal off';
      }
    }
    if (toggle) {
      toggle.textContent = rehearsalState.active ? 'Pause rehearsal' : (hasRehearsalData() ? 'Resume rehearsal' : 'Start rehearsal');
    }
    renderSuggestedBudgets();
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
    const content = html || '<em class="premium-presenter__no-notes">No notes for this slide</em>';
    el.innerHTML = sanitizeNotesHtml(content);
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

  function onPopupMessage(e, transport) {
    if (!e.data) return;
    if (e.data.type === 'presenter.hereIam') {
      if (transport !== 'window' || !hasTrustedDirectOrigin(e)) return;
      const opener = getOpener();
      if (!opener || e.source !== opener) return;
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
      }
      if (deckSid) sendReady();
      return;
    }
    const msgSid = e.data.sessionId || '';
    if (!msgSid || msgSid !== getSessionId()) return;
    if (transport === 'window') {
      const opener = getOpener();
      if (!hasTrustedDirectOrigin(e) || !opener || e.source !== opener) return;
    }

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
      const opener = getOpener();
      if (opener) opener.postMessage(
        { type: 'presenter.discover', popupSessionId: getSessionId() },
        directTargetOrigin()
      );
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
    // Crash-safety net (ADR-2): beforeunload+unload double-fire is harmless —
    // persistRun() upserts by rehearsalRunTs. Don't precheck hasRehearsalData()
    // here — the in-flight segment (time on the CURRENT slide) isn't reflected
    // in elapsedMs/slideMs until persistRun's own commitCurrentRehearsalSegment()
    // runs, so a rehearsal that never paused/changed slides would look empty
    // and get silently dropped. persistRun() commits first, THEN applies the
    // pollution guard, so a genuinely-empty run (active but zero dwell) still
    // won't be persisted.
    if (rehearsalState.active) persistRun();
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
        if (isInPopup()) onPopupMessage(e, 'window');
        else onDeckMessage(e, 'window');
      });
      window.addEventListener('storage', (e) => {
        if (e.key !== STORAGE_KEY) return;
        if (!e.newValue) return;
        let parsed;
        try { parsed = JSON.parse(e.newValue); } catch (_) { return; }
        const payload = parsed && parsed.payload;
        if (!payload) return;
        if (isInPopup()) onPopupMessage({ data: payload }, 'storage');
        else onDeckMessage({ data: payload }, 'storage');
      });
    }

    if (isInPopup()) {
      try { DIAG.opener = !!(window.opener && !window.opener.closed); } catch (_) {}
      try { DIAG.bcAvail = !!(typeof BroadcastChannel === 'function' && getCh()); } catch (_) {}
      try { DIAG.lsAvail = !!localStorage; } catch (_) {}
      if (ch) ch.addEventListener('message', (e) => onPopupMessage(e, 'broadcast'));
      buildPopupDom();
      updateDiag();
      window.addEventListener('beforeunload', onPopupUnload);
      window.addEventListener('unload', onPopupUnload);
      return;
    }

    // Deck side.
    if (ch) ch.addEventListener('message', (e) => onDeckMessage(e, 'broadcast'));
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
    getRehearsalStore: () => readRehearsalStore(),
    getSuggestedBudgets: () => perSlideMedians(readRehearsalStore()),
    readSlideBudgets: () => readSlideBudgets(),
    readSlideIdentities: () => readSlideIdentities(),
    validateBudgetMs: (value) => validateBudgetMs(value),
    formatBudgetMmss: (ms) => formatBudgetMmss(ms),
    validateBudgetMmss: (value, ms) => validateBudgetMmss(value, ms),
    getComparisonLabel: () => comparisonLabel(),
    getPlannedTimeFor: (index) => plannedTimeFor(index),
    getSuggestedBudgetExport: () => buildSuggestedBudgetExport(),
    exportRehearsalJson: () => exportRehearsalJson(),
    getLastRunDeltas: () => {                        // routed through the centralized planned-time helper
      const total = presenterState.total || 0;
      const runs = eligibleRuns(readRehearsalStore());
      const last = runs[runs.length - 1];
      if (!last || !total) return null;
      const plan = budgetPlan();
      if (plan) {
        if (plan.vector.length !== total) return null;   // atomic: vector must match this deck
        return Array.from({ length: total }, (_, i) => (last.slideMs[i] || 0) - plan.vector[i]);
      }
      const plannedMs = getPlannedSlideMs();
      if (plannedMs <= 0) return null;
      return Array.from({ length: total }, (_, i) => (last.slideMs[i] || 0) - plannedMs);
    },
    getTeleprompterState: () => Object.assign({}, teleprompterState, {
      reducedMotion: prefersReducedMotion(),
      timedEngaged: isTimedEngaged(),
    }),
  };
  window.PremiumPresenter = Object.assign(window.PremiumPresenter || {}, {
    postToPeer,
    nextStateSeq,
  });
})();
