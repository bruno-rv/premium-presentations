/**
 * Premium Presentations — speaker timer with audio bell, pace estimate, wake lock.
 *
 * Config precedence (highest wins), evaluated in `init()`:
 *   1. sessionStorage['premium-timer']            — running-talk state restore
 *   2. localStorage['premium-timer-override:...'] — per-deck URL override (popup writes)
 *   3. <meta name="premium-timer" content="N">    — per-deck default
 *   4. 30 min                                     — built-in
 *
 * End-time mode: stores `targetEndAtMs` (absolute wall clock). `getState()`
 * branches on `mode === 'endAt'` to derive remaining from `target - now`.
 * Delayed starts, midnight rollover, DST, and pause/resume are all handled
 * by recomputing from wall clock + target.
 *
 * Throttled `tick` broadcasts: at most once per 500 ms. Immediate flush on
 * start/pause/reset/setMinutes/setEndAt.
 *
 * Usage: <script src=".../premium-timer.js" defer></script>
 */
(function () {
  const SESSION_KEY = 'premium-timer';
  const OVERRIDE_PREFIX = 'premium-timer-override:';
  const META_SELECTOR = 'meta[name="premium-timer"]';
  const TICK_THROTTLE_MS = 500;
  const WARN_THRESHOLDS_MS = [5 * 60 * 1000, 2 * 60 * 1000, 60 * 1000, 30 * 1000];
  const PACE_WINDOW = 5;
  const DEFAULT_DURATION_MS = 30 * 60 * 1000;

  let mode = 'duration';      // 'duration' | 'endAt'
  let totalMs = DEFAULT_DURATION_MS;
  let targetEndAtMs = 0;      // wall-clock target, used in 'endAt' mode
  let startTs = 0;            // performance.now() at last start()
  let pausedAt = 0;
  let elapsedAtPause = 0;
  let runStartWall = 0;       // wall-clock ms when the run started (for endAt elapsed calc)
  let running = false;
  let raf = 0;
  let paceHistory = [];
  let lastSlideChangeTs = 0;
  let wakeLock = null;
  let audioCtx = null;
  let bellAt = new Set();
  let panel = null;
  let timeEl = null;
  let paceEl = null;
  let channel = null;
  let paceStatus = 'on-pace';
  let flashTimer = 0;
  let hidden = true;
  let lastTickPost = 0;

  function getCh() {
    if (!channel) {
      // Use the SAME global channel name as premium-presenter. Per-session
      // channels were the bug: the popup listens on `premium-deck` (global)
      // so `premium-deck:<sid>` ticks never reached it. Fallback name
      // `premium-deck:state` kept for safety when no session is set.
      const sid = document.documentElement.dataset.session || '';
      try { channel = new BroadcastChannel(sid ? 'premium-deck' : 'premium-deck:state'); } catch (_) {}
    }
    return channel;
  }

  function post(type, detail) {
    const sessionId = document.documentElement.dataset.session || '';
    const seq = window.PremiumPresenter && typeof window.PremiumPresenter.nextStateSeq === 'function'
      ? window.PremiumPresenter.nextStateSeq() : undefined;
    const payload = Object.assign({ type, ts: Date.now(), sessionId }, seq != null ? { seq } : {}, detail || {});
    if (window.PremiumPresenter && typeof window.PremiumPresenter.postToPeer === 'function') {
      try { window.PremiumPresenter.postToPeer(payload); return; } catch (_) {}
    }
    const ch = getCh();
    if (ch) ch.postMessage(payload);
  }

  function postTick(state, immediate) {
    if (!immediate && (Date.now() - lastTickPost) < TICK_THROTTLE_MS) return;
    lastTickPost = Date.now();
    post('tick', {
      running: state.running,
      totalMs: state.totalMs,
      elapsedMs: state.elapsedMs,
      remainingMs: state.remainingMs,
      mode: state.mode,
      targetEndAtMs: state.targetEndAtMs,
      state: panel?.dataset?.state || 'ok',
    });
  }

  function fmt(ms) {
    if (ms < 0) ms = 0;
    const totalSec = Math.ceil(ms / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return m + ':' + (s < 10 ? '0' + s : s);
  }

  function getState() {
    if (mode === 'endAt') {
      const remainingMs = Math.max(0, targetEndAtMs - Date.now());
      const elapsedMs = running
        ? (pausedAt ? elapsedAtPause : (Date.now() - runStartWall + elapsedAtPause))
        : elapsedAtPause;
      return {
        running, mode, totalMs: targetEndAtMs - (runStartWall || targetEndAtMs),
        elapsedMs, remainingMs, targetEndAtMs,
      };
    }
    if (!running) {
      return { running: false, mode, totalMs, elapsedMs: elapsedAtPause, remainingMs: totalMs - elapsedAtPause, targetEndAtMs: 0 };
    }
    const elapsed = elapsedAtPause + (performance.now() - startTs);
    return { running: true, mode, totalMs, elapsedMs: elapsed, remainingMs: totalMs - elapsed, targetEndAtMs: 0 };
  }

  function updatePanel() {
    if (!panel) return;
    const s = getState();
    timeEl.textContent = fmt(s.remainingMs);
    paceEl.textContent = paceStatus.replace('-', ' ');
    let state = 'ok';
    if (s.remainingMs < 30 * 1000) state = 'critical';
    else if (s.remainingMs < 2 * 60 * 1000) state = 'red';
    else if (s.remainingMs < 5 * 60 * 1000) state = 'amber';
    panel.dataset.state = state;
    if (state !== 'ok' && hidden) {
      setHidden(false);
      if (flashTimer) { clearTimeout(flashTimer); flashTimer = 0; }
    }
  }

  function playBell(pattern) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    } catch (_) { return; }
    const t0 = audioCtx.currentTime;
    pattern.forEach((freq, i) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0, t0 + i * 0.3);
      gain.gain.linearRampToValueAtTime(0.25, t0 + i * 0.3 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + i * 0.3 + 0.25);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(t0 + i * 0.3);
      osc.stop(t0 + i * 0.3 + 0.3);
    });
  }

  const BELL_PATTERNS = {
    [5 * 60 * 1000]: [440, 660],
    [2 * 60 * 1000]: [660, 440],
    [60 * 1000]: [660, 880, 660],
    [30 * 1000]: [880, 880, 880],
  };

  function checkBell(s) {
    WARN_THRESHOLDS_MS.forEach((t) => {
      if (s.remainingMs <= t && !bellAt.has(t) && s.running) {
        bellAt.add(t);
        playBell(BELL_PATTERNS[t] || [880]);
        post('bell', { threshold: t });
      }
    });
  }

  function recomputePace() {
    if (paceHistory.length < 2) { paceStatus = 'gathering'; return; }
    const avg = paceHistory.reduce((a, b) => a + b, 0) / paceHistory.length;
    const totalSlides = document.querySelectorAll('#deck .slide').length || 1;
    const slidesLeft = Math.max(1, totalSlides - (paceHistory.length));
    const projectedTotal = getState().elapsedMs + avg * slidesLeft;
    if (projectedTotal > totalMs * 1.1) paceStatus = 'behind';
    else if (projectedTotal < totalMs * 0.9) paceStatus = 'ahead';
    else paceStatus = 'on-pace';
  }

  function tick() {
    if (!running) return;
    const s = getState();
    updatePanel();
    postTick(s, false);
    checkBell(s);
    if (s.remainingMs <= 0) {
      stop();
      return;
    }
    raf = requestAnimationFrame(tick);
  }

  function mount() {
    if (isInPopup()) return;
    if (panel || document.getElementById('premium-timer-panel')) {
      panel = document.getElementById('premium-timer-panel');
      timeEl = panel.querySelector('.premium-timer__time');
      paceEl = panel.querySelector('.premium-timer__pace');
      return;
    }
    panel = document.createElement('div');
    panel.className = 'premium-timer';
    panel.id = 'premium-timer-panel';
    panel.dataset.hidden = 'true';
    panel.innerHTML =
      '<div class="premium-timer__time">--:--</div>' +
      '<div class="premium-timer__pace">ready</div>';
    document.body.appendChild(panel);
    timeEl = panel.querySelector('.premium-timer__time');
    paceEl = panel.querySelector('.premium-timer__pace');
    panel.addEventListener('click', () => running ? pause() : start());
  }

  function setHidden(next) {
    hidden = !!next;
    if (panel) panel.dataset.hidden = hidden ? 'true' : 'false';
  }

  function flash(durationMs) {
    if (!panel) return;
    setHidden(false);
    if (flashTimer) clearTimeout(flashTimer);
    flashTimer = setTimeout(() => {
      flashTimer = 0;
      if (!panel) return;
      const urgent = panel.dataset.state === 'amber'
        || panel.dataset.state === 'red'
        || panel.dataset.state === 'critical';
      setHidden(!(running || urgent));
    }, durationMs || 3000);
  }

  async function requestWakeLock() {
    if (!('wakeLock' in navigator)) return;
    try {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLock.addEventListener('release', () => { wakeLock = null; });
    } catch (_) {}
  }

  function releaseWakeLock() {
    if (wakeLock) { wakeLock.release().catch(() => {}); wakeLock = null; }
  }

  function start() {
    if (isInPopup()) return;
    if (running) return;
    mount();
    if (mode === 'endAt' && targetEndAtMs <= Date.now()) {
      // Target already passed (e.g. tab was backgrounded for hours). Bail out cleanly.
      stop();
      return;
    }
    startTs = performance.now();
    pausedAt = 0;
    runStartWall = Date.now();
    running = true;
    lastSlideChangeTs = performance.now();
    requestWakeLock();
    save();
    if (flashTimer) { clearTimeout(flashTimer); flashTimer = 0; }
    setHidden(false);
    updatePanel();
    postTick(getState(), true);  // immediate flush on lifecycle
    raf = requestAnimationFrame(tick);
  }

  function pause() {
    if (isInPopup()) return;
    if (!running) return;
    elapsedAtPause = elapsedAtPause + (performance.now() - startTs);
    pausedAt = performance.now();
    running = false;
    releaseWakeLock();
    if (raf) cancelAnimationFrame(raf);
    if (flashTimer) { clearTimeout(flashTimer); flashTimer = 0; }
    setHidden(true);
    save();
    postTick(getState(), true);
  }

  function stop() {
    if (isInPopup()) return;
    running = false;
    releaseWakeLock();
    if (raf) cancelAnimationFrame(raf);
    bellAt = new Set();
    updatePanel();
    postTick(getState(), true);
  }

  function reset(minutes) {
    if (isInPopup()) return;
    if (minutes) totalMs = minutes * 60 * 1000;
    elapsedAtPause = 0;
    pausedAt = 0;
    paceHistory = [];
    bellAt = new Set();
    running = false;
    startTs = 0;
    save();
    if (panel) updatePanel();
    postTick(getState(), true);
  }

  function setMinutes(m) {
    if (isInPopup()) return;
    if (!Number.isFinite(m) || m <= 0) throw new Error('Invalid minutes: ' + m);
    mode = 'duration';
    totalMs = m * 60 * 1000;
    targetEndAtMs = 0;
    elapsedAtPause = 0;
    pausedAt = 0;
    paceHistory = [];
    bellAt = new Set();
    startTs = performance.now();
    save();
    if (panel) updatePanel();
    postTick(getState(), true);
  }

  function setEndAt(timestampMs) {
    if (isInPopup()) return;
    if (!Number.isFinite(timestampMs) || timestampMs <= Date.now()) {
      throw new Error('Invalid end timestamp: must be a finite future timestamp');
    }
    mode = 'endAt';
    targetEndAtMs = timestampMs;
    elapsedAtPause = 0;
    pausedAt = 0;
    paceHistory = [];
    bellAt = new Set();
    startTs = performance.now();
    runStartWall = Date.now();
    save();
    if (panel) updatePanel();
    postTick(getState(), true);
  }

  function save() {
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({
        mode, totalMs, targetEndAtMs, elapsedAtPause, startTs, running, savedAt: Date.now(),
      }));
    } catch (_) {}
  }

  function restore() {
    try {
      const raw = sessionStorage.getItem(SESSION_KEY);
      if (!raw) return;
      const s = JSON.parse(raw);
      mode = s.mode === 'endAt' ? 'endAt' : 'duration';
      if (mode === 'endAt' && Number.isFinite(s.targetEndAtMs)) {
        targetEndAtMs = s.targetEndAtMs;
      }
      if (Number.isFinite(s.totalMs)) totalMs = s.totalMs;
      elapsedAtPause = s.elapsedAtPause || 0;
      mount();
      if (s.running) {
        const gap = Date.now() - (s.savedAt || Date.now());
        if (gap < 5 * 60 * 1000 && (mode !== 'endAt' || targetEndAtMs > Date.now())) {
          startTs = performance.now() - gap;
          runStartWall = Date.now() - gap;
          running = true;
          lastSlideChangeTs = performance.now();
          requestWakeLock();
          setHidden(false);
          raf = requestAnimationFrame(tick);
        } else {
          running = false;
        }
      }
      updatePanel();
    } catch (_) {}
  }

  function onSlideChange() {
    const now = performance.now();
    if (running) {
      if (lastSlideChangeTs) {
        const dwell = now - lastSlideChangeTs;
        paceHistory.push(dwell);
        if (paceHistory.length > PACE_WINDOW) paceHistory.shift();
        recomputePace();
      }
      lastSlideChangeTs = now;
    }
    if (!panel) mount();
    if (panel) flash(3000);
  }

  function readConfig() {
    // 1) session restore (handled separately by restore(); that's the top precedence)
    // 2) per-deck URL override written by popup
    try {
      const raw = localStorage.getItem(OVERRIDE_PREFIX + location.pathname);
      if (raw) {
        const o = JSON.parse(raw);
        if (o && o.mode === 'endAt' && Number.isFinite(o.targetEndAtMs) && o.targetEndAtMs > Date.now()) {
          mode = 'endAt';
          targetEndAtMs = o.targetEndAtMs;
          return;
        }
        if (o && Number.isFinite(o.minutes) && o.minutes > 0) {
          mode = 'duration';
          totalMs = o.minutes * 60 * 1000;
          return;
        }
      }
    } catch (_) {}
    // 3) <meta name="premium-timer" content="N"> in <head>
    try {
      const meta = document.querySelector(META_SELECTOR);
      if (meta) {
        const minutes = parseFloat(meta.getAttribute('content'));
        if (Number.isFinite(minutes) && minutes > 0) {
          mode = 'duration';
          totalMs = minutes * 60 * 1000;
          return;
        }
      }
    } catch (_) {}
    // 4) built-in default
    mode = 'duration';
    totalMs = DEFAULT_DURATION_MS;
  }

  function writeOverride(minutes, endAtTimestamp) {
    try {
      if (endAtTimestamp) {
        localStorage.setItem(OVERRIDE_PREFIX + location.pathname, JSON.stringify({ mode: 'endAt', targetEndAtMs: endAtTimestamp }));
      } else {
        localStorage.setItem(OVERRIDE_PREFIX + location.pathname, JSON.stringify({ mode: 'duration', minutes }));
      }
    } catch (_) {}
  }

  function isInPopup() {
    return new URLSearchParams(location.search).get('presenter') === '1';
  }

  function init() {
    // In the popup the timer is driven by tick messages from the deck.
    // No local restore, no RAF, no wake lock, no bell audio, no postTick.
    if (isInPopup()) return;

    readConfig();
    restore();
    const ch = getCh();
    if (ch) {
      ch.addEventListener('message', (e) => {
        if (!e.data) return;
        // Drop slidechange from other sessions. Legacy unstamped messages pass.
        const msgSid = e.data.sessionId;
        if (msgSid && msgSid !== document.documentElement.dataset.session) return;
        if (e.data.type === 'slidechange') onSlideChange();
      });
    }
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible' && running && !wakeLock) requestWakeLock();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumTimer = {
    start, pause, stop, reset, setMinutes, setEndAt,
    set: setMinutes,
    mount,
    getState,
    writeOverride,  // popup calls this to persist its UI state for reload
  };
})();
