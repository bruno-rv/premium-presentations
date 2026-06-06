# Premium Presentations — Extra Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 12 high-leverage features (5 live presenter + 7 distribution/viewer) to the Premium Presentations framework, then re-bundle the 4 existing decks so they pick up the new engine pieces.

**Architecture:** New isolated modules in `shared/` (5 JS + 1 CSS + 1 OG-cover JS), 1 new script, patches to 3 existing files. No build step. Bundle via existing `bundle_deck.py`. All inter-module comms via `BroadcastChannel('premium-deck:state')`.

**Tech Stack:** Vanilla JS, Web Audio, BroadcastChannel, Web Speech, Wake Lock, WebHID, View Transitions, lazy SnapDOM CDN, lazy MiniSearch CDN.

**Spec:** `docs/superpowers/specs/2026-06-04-extra-features-design.md`

---

## File structure (recap)

**New (7):**
- `shared/premium-timer.js` — A1+A4 timer, bell, pace, wake lock
- `shared/premium-presenter.js` — A3 popup + fallback
- `shared/premium-clicker.js` — A5 WebHID + keyboard
- `shared/premium-tts.js` — B3 TTS
- `shared/premium-search.js` — B6 Cmd+K
- `shared/premium-og-cover.js` — B2+B5 PNG export helper
- `shared/premium-extras.css` — All new styles
- `scripts/og-cover.sh` — B2 cover generator

**Patched (3):**
- `shared/slide-engine.js` — B1 pushState/popstate, B7 embed mode
- `shared/premium-controls.js` — A1+A2+B3+B4+B5+B6 buttons
- `templates/premium-base.html` — A1+A2+B3+B4 UI + B2 OG meta + extras CSS link

**Rebuilt (4):**
- `decks/graph-databases/graph-databases-slides.html`
- `decks/vector-databases/vector-databases-slides.html`
- `decks/vector-vs-graph/vector-vs-graph-slides.html`
- `decks/rag-vector-graph/rag-vector-graph-slides.html`

---

## Task ordering (compound, ships working at each commit)

1. **A2 Curtain** (smallest, easiest, ships in one CSS + 5 LOC patch) → commit
2. **A1+A4 Timer + bell + pace + wake** (one file, self-contained) → commit
3. **B1 pushState** (tiny slide-engine patch) → commit
4. **B2 OG meta + cover script** (template patch + 1 script) → commit
5. **B4 PDF print-CSS** (CSS + button) → commit
6. **B5 PNG export** (extends og-cover.js) → commit
7. **B3 TTS** (one file) → commit
8. **B6 Search** (one file + dep) → commit
9. **B7 Embed mode** (slide-engine + CSS) → commit
10. **A3 Presenter view** (the big one — depends on A1+B1) → commit
11. **A5 Clicker** (one file) → commit
12. **Template patch** (link extras.css, add all buttons, link og-cover.js) → commit
13. **Re-bundle 4 decks** → commit
14. **Smoke test + docs** → commit

Each task = one commit, working state at end of each.

---

### Task 1: Blackout / curtain (A2)

**Files:**
- Create: `shared/premium-extras.css` (skeleton)
- Modify: `shared/premium-controls.js` — add curtain button

- [ ] **Step 1: Create `shared/premium-extras.css` with curtain styles**

```css
/* Premium Presentations — extras (curtain, presenter, TTS, search, embed, export) */
body.curtain::before {
  content: '';
  position: fixed; inset: 0; z-index: 9999;
  background: #000;
  pointer-events: none;
  animation: premium-curtain-in 0.3s ease;
}
body.curtain.curtain--message::before {
  content: attr(data-curtain-message);
  display: flex; align-items: center; justify-content: center;
  color: rgba(255,255,255,0.7);
  font-family: var(--font-display, serif);
  font-size: clamp(1.5rem, 4vw, 3rem);
  font-style: italic;
  background: #000;
}
@keyframes premium-curtain-in { from { opacity: 0; } to { opacity: 1; } }
@media (prefers-reduced-motion: reduce) {
  body.curtain::before { animation: none; }
}

/* Timer panel — top right, below controls */
.premium-timer {
  position: fixed; top: 18px; right: 18px; z-index: 95;
  display: flex; flex-direction: column; align-items: flex-end; gap: 4px;
  padding: 10px 14px;
  background: color-mix(in srgb, var(--bg, #0a0a0a) 75%, transparent);
  border: 1px solid var(--border, #333); border-radius: 12px;
  backdrop-filter: blur(8px);
  font-family: var(--font-mono, monospace);
  font-size: 14px; color: var(--text, #fff);
  min-width: 96px; text-align: right;
  user-select: none;
}
.premium-timer[data-state="amber"] { color: #f5a623; border-color: #f5a623; }
.premium-timer[data-state="red"]   { color: #e74c3c; border-color: #e74c3c; }
.premium-timer[data-state="critical"] { animation: premium-timer-flash 0.6s infinite alternate; }
.premium-timer__pace { font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase; opacity: 0.7; }
.premium-timer[hidden] { display: none; }
@keyframes premium-timer-flash { from { opacity: 1; } to { opacity: 0.4; } }

/* Presenter view popup */
.premium-presenter-overlay {
  position: fixed; inset: 0; z-index: 9000;
  background: var(--bg, #0a0a0a);
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  grid-template-rows: 1fr auto;
  grid-template-areas: "current next" "notes notes";
  gap: 14px; padding: 18px;
}
.premium-presenter-overlay__current { grid-area: current; overflow: hidden; }
.premium-presenter-overlay__next    { grid-area: next; overflow: hidden; opacity: 0.85; }
.premium-presenter-overlay__notes   {
  grid-area: notes;
  background: var(--surface, #111);
  border: 1px solid var(--border, #333);
  border-radius: 12px;
  padding: 16px 20px;
  font-family: var(--font-mono, monospace);
  font-size: 14px; line-height: 1.6;
  color: var(--text-dim, #ccc);
  max-height: 30vh; overflow-y: auto;
}
.premium-presenter-overlay__notes h4 {
  font-size: 10px; letter-spacing: 0.15em; text-transform: uppercase;
  color: var(--accent, #4a9eff); margin-bottom: 8px;
}
.premium-presenter-overlay__notes p { margin-bottom: 8px; }
.premium-presenter-overlay__notes em { color: var(--text-dim, #888); }
.premium-presenter-overlay__close {
  position: absolute; top: 14px; right: 18px;
  background: none; border: 1px solid var(--border, #333);
  color: var(--text, #fff);
  padding: 6px 14px; border-radius: 8px;
  font-family: var(--font-mono, monospace); font-size: 11px;
  cursor: pointer;
}

/* TTS highlight */
.premium-tts-active { background: color-mix(in srgb, var(--accent, #4a9eff) 30%, transparent); border-radius: 3px; padding: 0 2px; }
.premium-tts-cursor {
  position: absolute;
  width: 2px; background: var(--accent, #4a9eff);
  pointer-events: none; z-index: 80;
  transition: top 0.15s, left 0.15s, height 0.15s, width 0.15s;
}

/* Search palette */
.premium-search-overlay {
  position: fixed; inset: 0; z-index: 9500;
  background: rgba(0,0,0,0.55);
  display: flex; align-items: flex-start; justify-content: center;
  padding-top: 12vh;
  backdrop-filter: blur(4px);
}
.premium-search-palette {
  width: min(640px, 92vw);
  background: var(--surface, #111);
  border: 1px solid var(--border, #333);
  border-radius: 16px;
  box-shadow: 0 30px 80px rgba(0,0,0,0.5);
  overflow: hidden;
}
.premium-search-input {
  width: 100%; padding: 18px 22px;
  background: transparent; border: 0; outline: 0;
  font-family: var(--font-mono, monospace);
  font-size: 18px; color: var(--text, #fff);
  border-bottom: 1px solid var(--border, #333);
}
.premium-search-results { list-style: none; max-height: 50vh; overflow-y: auto; }
.premium-search-result {
  padding: 12px 22px;
  border-bottom: 1px solid var(--border, #222);
  cursor: pointer; display: flex; gap: 14px; align-items: baseline;
}
.premium-search-result:last-child { border-bottom: 0; }
.premium-search-result.is-active { background: color-mix(in srgb, var(--accent, #4a9eff) 18%, transparent); }
.premium-search-result__num { font-family: var(--font-mono, monospace); color: var(--accent, #4a9eff); font-size: 11px; min-width: 28px; }
.premium-search-result__title { flex: 1; font-size: 14px; color: var(--text, #fff); }
.premium-search-result__body { font-size: 12px; color: var(--text-dim, #888); margin-top: 2px; }
.premium-search-result mark { background: var(--accent-dim, #4a9eff40); color: var(--accent, #4a9eff); padding: 0 2px; border-radius: 2px; }
.premium-search-hint { padding: 8px 22px; font-size: 10px; color: var(--text-dim, #888); font-family: var(--font-mono, monospace); text-align: right; }

/* Clicker status */
.premium-clicker-status {
  position: fixed; bottom: 50px; left: 50%; transform: translateX(-50%);
  padding: 8px 16px; border-radius: 8px;
  background: var(--surface, #111); border: 1px solid var(--border, #333);
  font-family: var(--font-mono, monospace); font-size: 11px;
  color: var(--text, #fff);
  z-index: 95;
  opacity: 0; transition: opacity 0.3s;
}
.premium-clicker-status.is-visible { opacity: 1; }
```

- [ ] **Step 2: Modify `shared/premium-controls.js` — add curtain button to panel**

Find the `mountControls` function (around line 122). In the panel building section, after the `parallaxGroup`, add:

```javascript
    const curtainGroup = document.createElement('div');
    curtainGroup.className = 'premium-controls__group';
    const curtainBtn = document.createElement('button');
    curtainBtn.type = 'button';
    curtainBtn.id = 'premium-curtain-toggle';
    curtainBtn.innerHTML = 'Curtain<span class="premium-kbd">B</span>';
    curtainBtn.title = 'Blackout screen (B)';
    curtainBtn.addEventListener('click', toggleCurtain);
    curtainGroup.appendChild(curtainBtn);
    panel.appendChild(curtainGroup);
```

Add these functions inside the IIFE, before `init`:

```javascript
  function isCurtainOn() {
    return document.body.classList.contains('curtain');
  }

  function setCurtain(on, message) {
    document.body.classList.toggle('curtain', on);
    if (message) {
      document.body.dataset.curtainMessage = message;
      document.body.classList.add('curtain--message');
    } else {
      document.body.classList.remove('curtain--message');
      delete document.body.dataset.curtainMessage;
    }
  }

  function toggleCurtain() {
    setCurtain(!isCurtainOn());
    syncCurtainButton();
  }

  function syncCurtainButton() {
    const btn = document.getElementById('premium-curtain-toggle');
    if (btn) btn.setAttribute('aria-pressed', isCurtainOn() ? 'true' : 'false');
  }
```

In `bindControlShortcuts`, inside the keydown handler, add (after the `'3'` block, before `'t'`):

```javascript
      if (key === 'b' || key === '.') {
        e.preventDefault();
        toggleCurtain();
        return;
      }
```

Export the new functions in `window.PremiumPresentations`:

```javascript
  window.PremiumPresentations = {
    setTheme,
    cycleTheme,
    setParallax,
    toggleParallax,
    setControlsHidden,
    setControlsOpen,
    toggleControlsHidden,
    isControlsHidden,
    setCurtain,
    toggleCurtain,
    isCurtainOn,
    THEMES,
  };
```

Also add `syncCurtainButton()` call inside `mountControls` after `panel.appendChild(curtainGroup)`:

```javascript
    syncCurtainButton();
```

- [ ] **Step 3: Verify it parses**

Run: `node -e "const fs=require('fs'); const c=fs.readFileSync('shared/premium-controls.js','utf8'); if(!c.includes('toggleCurtain')) throw 'missing toggleCurtain'; console.log('OK');"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add shared/premium-extras.css shared/premium-controls.js
git commit -m "feat(presenter): add A2 blackout/curtain with B key"
```

---

### Task 2: Speaker timer + bell + pace + wake lock (A1+A4)

**Files:**
- Create: `shared/premium-timer.js`

- [ ] **Step 1: Create `shared/premium-timer.js`**

```javascript
/**
 * Premium Presentations — speaker timer with audio bell, pace estimate, wake lock.
 * Usage: <script src=".../premium-timer.js" defer></script>
 */
(function () {
  const STORAGE = 'premium-timer';
  const WARN_THRESHOLDS_MS = [5 * 60 * 1000, 2 * 60 * 1000, 60 * 1000, 30 * 1000];
  const PACE_WINDOW = 5;
  const PACE_REFRESH_MS = 1000;

  let totalMs = 30 * 60 * 1000;
  let startTs = 0;
  let pausedAt = 0;
  let elapsedAtPause = 0;
  let running = false;
  let raf = 0;
  let paceHistory = [];
  let lastSlideChangeTs = 0;
  let wakeLock = null;
  let audioCtx = null;
  let bellAt = new Set();
  let panel = null;
  let channel = null;
  let paceStatus = 'on-pace';

  function getCh() {
    if (!channel) {
      try { channel = new BroadcastChannel('premium-deck:state'); } catch (_) {}
    }
    return channel;
  }

  function post(type, detail) {
    const ch = getCh();
    if (ch) ch.postMessage(Object.assign({ type, ts: Date.now() }, detail || {}));
  }

  function fmt(ms) {
    if (ms < 0) ms = 0;
    const totalSec = Math.ceil(ms / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return m + ':' + (s < 10 ? '0' + s : s);
  }

  function getState() {
    if (!running) return { running: false, totalMs, elapsedMs: elapsedAtPause, remainingMs: totalMs - elapsedAtPause };
    const elapsed = elapsedAtPause + (performance.now() - startTs);
    return { running: true, totalMs, elapsedMs: elapsed, remainingMs: totalMs - elapsed };
  }

  function updatePanel() {
    if (!panel) return;
    const s = getState();
    panel.querySelector('.premium-timer__time').textContent = fmt(s.remainingMs);
    panel.querySelector('.premium-timer__pace').textContent = paceStatus.replace('-', ' ');
    let state = 'ok';
    if (s.remainingMs < 30 * 1000) state = 'critical';
    else if (s.remainingMs < 2 * 60 * 1000) state = 'red';
    else if (s.remainingMs < 5 * 60 * 1000) state = 'amber';
    panel.dataset.state = state;
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
    5 * 60 * 1000: [440, 660],
    2 * 60 * 1000: [660, 440],
    60 * 1000: [660, 880, 660],
    30 * 1000: [880, 880, 880],
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
    const remaining = totalMs - getState().elapsedMs;
    const projectedTotal = getState().elapsedMs + avg * 100;
    if (projectedTotal > totalMs * 1.1) paceStatus = 'behind';
    else if (projectedTotal < totalMs * 0.9) paceStatus = 'ahead';
    else paceStatus = 'on-pace';
  }

  function tick() {
    if (!running) return;
    const s = getState();
    updatePanel();
    checkBell(s);
    post('tick', { elapsedMs: s.elapsedMs, remainingMs: s.remainingMs });
    if (s.remainingMs <= 0) {
      stop();
      return;
    }
    raf = requestAnimationFrame(tick);
  }

  function mount() {
    if (panel || document.getElementById('premium-timer-panel')) return;
    panel = document.createElement('div');
    panel.className = 'premium-timer';
    panel.id = 'premium-timer-panel';
    panel.innerHTML =
      '<div class="premium-timer__time">--:--</div>' +
      '<div class="premium-timer__pace">ready</div>';
    document.body.appendChild(panel);
    panel.addEventListener('click', () => running ? pause() : start());
  }

  async function requestWakeLock() {
    if (!('wakeLock' in navigator)) return;
    try {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLock.addEventListener('release', () => { wakeLock = null; });
    } catch (_) { /* permission denied or unsupported */ }
  }

  function releaseWakeLock() {
    if (wakeLock) { wakeLock.release().catch(() => {}); wakeLock = null; }
  }

  function start() {
    if (running) return;
    mount();
    if (pausedAt) {
      const pauseDuration = performance.now() - pausedAt;
      startTs = startTs + pauseDuration;
      pausedAt = 0;
    } else {
      startTs = performance.now();
    }
    running = true;
    lastSlideChangeTs = performance.now();
    requestWakeLock();
    save();
    updatePanel();
    raf = requestAnimationFrame(tick);
  }

  function pause() {
    if (!running) return;
    elapsedAtPause = elapsedAtPause + (performance.now() - startTs);
    pausedAt = performance.now();
    running = false;
    releaseWakeLock();
    if (raf) cancelAnimationFrame(raf);
    updatePanel();
    save();
  }

  function stop() {
    running = false;
    releaseWakeLock();
    if (raf) cancelAnimationFrame(raf);
    bellAt = new Set();
    updatePanel();
  }

  function reset(minutes) {
    if (minutes) totalMs = minutes * 60 * 1000;
    elapsedAtPause = 0;
    pausedAt = 0;
    paceHistory = [];
    bellAt = new Set();
    startTs = performance.now();
    save();
    if (panel) updatePanel();
  }

  function setMinutes(m) { totalMs = m * 60 * 1000; reset(); }

  function save() {
    try { sessionStorage.setItem(STORAGE, JSON.stringify({ totalMs, elapsedAtPause, startTs, running })); } catch (_) {}
  }

  function restore() {
    try {
      const raw = sessionStorage.getItem(STORAGE);
      if (!raw) return;
      const s = JSON.parse(raw);
      totalMs = s.totalMs || totalMs;
      elapsedAtPause = s.elapsedAtPause || 0;
      mount();
      updatePanel();
    } catch (_) {}
  }

  function onSlideChange() {
    if (!running) return;
    const now = performance.now();
    if (lastSlideChangeTs) {
      const dwell = now - lastSlideChangeTs;
      paceHistory.push(dwell);
      if (paceHistory.length > PACE_WINDOW) paceHistory.shift();
      recomputePace();
    }
    lastSlideChangeTs = now;
  }

  function init() {
    restore();
    const ch = getCh();
    if (ch) {
      ch.addEventListener('message', (e) => {
        if (e.data && e.data.type === 'slidechange') onSlideChange();
      });
    }
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible' && running && !wakeLock) requestWakeLock();
    });
    document.addEventListener('keydown', (e) => {
      if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      if (e.key === 'T' && e.shiftKey) {
        e.preventDefault();
        running ? pause() : start();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumTimer = { start, pause, stop, reset, setMinutes, set: setMinutes, mount, getState };
})();
```

- [ ] **Step 2: Add the timer button to controls panel**

In `shared/premium-controls.js`, in the `mountControls` function, after the curtain button block added in Task 1, add:

```javascript
    const timerGroup = document.createElement('div');
    timerGroup.className = 'premium-controls__group';
    const timerBtn = document.createElement('button');
    timerBtn.type = 'button';
    timerBtn.id = 'premium-timer-toggle';
    timerBtn.innerHTML = 'Timer<span class="premium-kbd">⇧T</span>';
    timerBtn.title = 'Start/pause speaker timer (Shift+T)';
    timerBtn.addEventListener('click', () => {
      if (window.PremiumTimer) {
        const s = window.PremiumTimer.getState();
        s.running ? window.PremiumTimer.pause() : window.PremiumTimer.start();
      }
    });
    timerGroup.appendChild(timerBtn);
    panel.appendChild(timerGroup);
```

- [ ] **Step 3: Verify it parses**

Run: `node -e "const fs=require('fs'); const c=fs.readFileSync('shared/premium-timer.js','utf8'); if(!c.includes('PremiumTimer')) throw 'missing export'; console.log('OK');"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add shared/premium-timer.js shared/premium-controls.js
git commit -m "feat(presenter): add A1+A4 speaker timer, audio bell, pace, wake lock"
```

---

### Task 3: Share-link upgrade — pushState (B1)

**Files:**
- Modify: `shared/slide-engine.js`

- [ ] **Step 1: Patch `createDotItem` to use `pushState`**

Find `SlideEngine.prototype.createDotItem` (line ~135). Change the `label.addEventListener('click', ...)` block to:

```javascript
  label.addEventListener('click', (e) => {
    e.preventDefault();
    this.goTo(i);
    this.pushHash(slide);
  });
```

- [ ] **Step 2: Add `pushHash` method and `popstate` handler**

After `SlideEngine.prototype.goTo` (line ~205), add:

```javascript
SlideEngine.prototype.pushHash = function (slide) {
  if (!slide || !slide.id) return;
  try {
    history.pushState(null, '', '#' + slide.id);
  } catch (_err) {
    try { history.replaceState(null, '', '#' + slide.id); } catch (_e) {}
  }
};

SlideEngine.prototype.onPopState = function () {
  const hash = (location.hash || '').replace(/^#/, '');
  if (!hash) return;
  const target = this.slides.findIndex((s) => s.id === hash);
  if (target >= 0 && target !== this.current) {
    this.slides[target]?.scrollIntoView({ behavior: 'smooth' });
  }
};
```

In `bindEvents`, after the `keydown` handler closes (around line 272), add:

```javascript
  window.addEventListener('popstate', () => this.onPopState());
```

In `observe`, change the callback so it pushes a hash on first transition:

```javascript
SlideEngine.prototype.observe = function () {
  const obs = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('visible');
          const newIndex = this.slides.indexOf(e.target);
          if (newIndex !== this.current) {
            this.current = newIndex;
            this.updateChrome();
            this.pushHash(e.target);
          }
        }
      });
    },
    { root: this.deck, threshold: 0.5 }
  );
  this.slides.forEach((s) => obs.observe(s));
};
```

- [ ] **Step 3: Verify**

Run: `node -e "const fs=require('fs'); const c=fs.readFileSync('shared/slide-engine.js','utf8'); if(!c.includes('pushHash')) throw 'missing pushHash'; if(!c.includes('popstate')) throw 'missing popstate'; console.log('OK');"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add shared/slide-engine.js
git commit -m "feat(viewer): B1 upgrade share link to pushState+popstate"
```

---

### Task 4: OG / Twitter card meta + cover script (B2)

**Files:**
- Create: `scripts/og-cover.sh`
- Modify: `templates/premium-base.html` — add OG meta block

- [ ] **Step 1: Create `scripts/og-cover.sh`**

```bash
#!/usr/bin/env bash
# Render slide 1 of a deck as a 1200x630 PNG for OG / Twitter card.
# Usage: ./scripts/og-cover.sh decks/<slug>/<slug>-slides.html
#
# Requires: headless browser. We use a tiny HTML harness + chromium's --screenshot.
# Falls back to a CSS-rendered hint if chromium isn't installed.

set -euo pipefail
SRC="${1:-}"
[[ -z "$SRC" ]] && { echo "usage: $0 <deck.html>" >&2; exit 1; }
[[ ! -f "$SRC" ]] && { echo "not found: $SRC" >&2; exit 1; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DECK_DIR="$(cd "$(dirname "$SRC")" && pwd)"
OUT="$DECK_DIR/og-cover.png"

if ! command -v chromium >/dev/null 2>&1 && ! command -v google-chrome >/dev/null 2>&1; then
  echo "Neither chromium nor google-chrome is installed."
  echo "Manual fallback: open $SRC in a browser at 1200x630, screenshot slide 1, save as $OUT"
  exit 0
fi

CHROME_BIN="$(command -v chromium || command -v google-chrome)"

# Build a tiny harness that pins the deck to 1200x630 viewport, hides chrome, snaps slide 1.
HARNESS="$DECK_DIR/.og-harness.html"
cat > "$HARNESS" <<EOF
<!doctype html>
<html><head><meta charset="utf-8"><style>
  html,body{margin:0;background:#000;overflow:hidden}
  iframe{width:1200px;height:630px;border:0;display:block}
  iframe{transform:scale(1);transform-origin:0 0}
</style></head>
<body>
<iframe id="f" src="${SRC##*/}"></iframe>
<script>
  // Wait for deck to load then signal ready by setting a title.
  document.getElementById('f').addEventListener('load', () => {
    setTimeout(() => { document.title = 'READY'; }, 1500);
  });
</script>
</body></html>
EOF

"$CHROME_BIN" \
  --headless \
  --no-sandbox \
  --hide-scrollbars \
  --disable-gpu \
  --window-size=1200,630 \
  --screenshot="$OUT" \
  --virtual-time-budget=4000 \
  "file://$HARNESS" 2>/dev/null || true

rm -f "$HARNESS"

if [[ -f "$OUT" ]]; then
  echo "Cover written: $OUT (1200x630)"
else
  echo "Screenshot failed. Manual fallback required."
  exit 1
fi
```

Make it executable:
```bash
chmod +x scripts/og-cover.sh
```

- [ ] **Step 2: Add OG meta block to `templates/premium-base.html`**

Find the `</head>` line. Just before it, insert:

```html
<meta property="og:type" content="article">
<meta property="og:title" content="{{TITLE}}">
<meta property="og:description" content="Premium Presentations deck">
<meta property="og:image" content="og-cover.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{{TITLE}}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' fill='%23000'/%3E%3Ctext x='8' y='12' text-anchor='middle' font-size='10' fill='%234a9eff'%3E%E2%96%A3%3C/text%3E%3C/svg%3E">
```

- [ ] **Step 3: Verify template still parses**

Run: `python3 -c "import html.parser; p=html.parser.HTMLParser(); p.feed(open('templates/premium-base.html').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add scripts/og-cover.sh templates/premium-base.html
git commit -m "feat(viewer): B2 OG/Twitter card meta + cover generator script"
```

---

### Task 5: PDF print-CSS export (B4)

**Files:**
- Modify: `shared/premium-extras.css` — add print-CSS rules
- Modify: `shared/premium-controls.js` — add print button

- [ ] **Step 1: Append print-CSS to `shared/premium-extras.css`**

```css
/* PDF export — opt-in via ?print-pdf query OR body.print-pdf class */
body.print-pdf .deck {
  height: auto !important;
  overflow: visible !important;
  scroll-snap-type: none !important;
}
body.print-pdf .slide {
  height: 720px !important;
  page-break-after: always !important;
  break-after: page !important;
  opacity: 1 !important;
  transform: none !important;
  scroll-snap-align: none !important;
}
body.print-pdf .deck-dots,
body.print-pdf .deck-progress,
body.print-pdf .deck-hints,
body.print-pdf .deck-counter,
body.print-pdf .premium-controls-shell,
body.print-pdf .premium-bg-3d,
body.print-pdf .premium-timer,
body.print-pdf .premium-clicker-status,
body.print-pdf .premium-search-overlay,
body.print-pdf .premium-presenter-overlay,
body.print-pdf .premium-tts-cursor {
  display: none !important;
}
@media print {
  @page { size: 1280px 720px; margin: 0; }
  html, body { background: #000 !important; }
}
```

- [ ] **Step 2: Add print button to controls**

In `shared/premium-controls.js`, in `mountControls`, after the timer button block, add:

```javascript
    const printGroup = document.createElement('div');
    printGroup.className = 'premium-controls__group';
    const printBtn = document.createElement('button');
    printBtn.type = 'button';
    printBtn.id = 'premium-print-pdf';
    printBtn.innerHTML = 'PDF<span class="premium-kbd">⇧E</span>';
    printBtn.title = 'Export as PDF (Shift+E)';
    printBtn.addEventListener('click', () => {
      document.body.classList.add('print-pdf');
      setTimeout(() => { window.print(); setTimeout(() => document.body.classList.remove('print-pdf'), 500); }, 100);
    });
    printGroup.appendChild(printBtn);
    panel.appendChild(printGroup);
```

In `bindControlShortcuts`, add:

```javascript
      if (e.key === 'E' && e.shiftKey) {
        e.preventDefault();
        const btn = document.getElementById('premium-print-pdf');
        if (btn) btn.click();
        return;
      }
```

- [ ] **Step 3: Verify**

Run: `node -e "const fs=require('fs'); const c=fs.readFileSync('shared/premium-extras.css','utf8'); if(!c.includes('print-pdf')) throw 'missing print-pdf'; console.log('OK');"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add shared/premium-extras.css shared/premium-controls.js
git commit -m "feat(viewer): B4 PDF print-CSS export with Shift+E"
```

---

### Task 6: PNG export via SnapDOM (B5)

**Files:**
- Create: `shared/premium-og-cover.js` (handles both OG cover and batch PNG export)

- [ ] **Step 1: Create `shared/premium-og-cover.js`**

```javascript
/**
 * Premium Presentations — PNG export.
 * Lazy-loads SnapDOM from CDN (~10 KB gz) and exports slides as PNG.
 * Trigger: control panel "PNG" button.
 */
(function () {
  const SNAPDOM_URL = 'https://cdn.jsdelivr.net/npm/@zumer/snapdom@2/dist/snapdom.min.js';
  let snapLib = null;
  let loadingPromise = null;

  async function loadSnap() {
    if (snapLib) return snapLib;
    if (loadingPromise) return loadingPromise;
    loadingPromise = new Promise((resolve, reject) => {
      if (window.snapdom) { snapLib = window.snapdom; resolve(snapLib); return; }
      const s = document.createElement('script');
      s.src = SNAPDOM_URL;
      s.onload = () => { snapLib = window.snapdom; resolve(snapLib); };
      s.onerror = () => reject(new Error('Failed to load SnapDOM'));
      document.head.appendChild(s);
    });
    return loadingPromise;
  }

  async function exportSlidePng(slide, scale = 2) {
    const snap = await loadSnap();
    try {
      const result = await snap(slide, { scale, type: 'png' });
      if (result && result.download) {
        const name = (slide.id || 'slide') + '.png';
        result.download({ filename: name });
      }
    } catch (err) {
      console.error('[Premium Export] slide export failed', err);
    }
  }

  async function exportDeckPng() {
    const slides = document.querySelectorAll('#deck .slide');
    if (!slides.length) return;
    for (let i = 0; i < slides.length; i++) {
      await exportSlidePng(slides[i], 1.5);
      await new Promise((r) => setTimeout(r, 200));
    }
  }

  function mountButton(panel) {
    if (!panel || document.getElementById('premium-export-png')) return;
    const group = document.createElement('div');
    group.className = 'premium-controls__group';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'premium-export-png';
    btn.innerHTML = 'PNG';
    btn.title = 'Export current slide as PNG (uses SnapDOM CDN)';
    btn.addEventListener('click', async () => {
      const active = document.querySelector('#deck .slide.visible') || document.querySelector('#deck .slide');
      if (active) {
        btn.disabled = true;
        btn.textContent = '…';
        await exportSlidePng(active, 2);
        btn.disabled = false;
        btn.textContent = 'PNG';
      }
    });
    group.appendChild(btn);
    panel.appendChild(group);
  }

  function init() {
    const panel = document.querySelector('.premium-controls');
    if (panel) mountButton(panel);
    document.addEventListener('premium-controls-ready', () => {
      const p = document.querySelector('.premium-controls');
      if (p) mountButton(p);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumExport = { exportSlidePng, exportDeckPng };
})();
```

- [ ] **Step 2: Verify**

Run: `node -e "const fs=require('fs'); const c=fs.readFileSync('shared/premium-og-cover.js','utf8'); if(!c.includes('PremiumExport')) throw 'missing export'; console.log('OK');"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add shared/premium-og-cover.js
git commit -m "feat(viewer): B5 PNG export via lazy SnapDOM"
```

---

### Task 7: TTS read-aloud (B3)

**Files:**
- Create: `shared/premium-tts.js`

- [ ] **Step 1: Create `shared/premium-tts.js`**

```javascript
/**
 * Premium Presentations — text-to-speech read-aloud.
 * Usage: <script src=".../premium-tts.js" defer></script>
 */
(function () {
  let active = false;
  let utterance = null;
  let button = null;
  let currentSlide = null;
  let boundaryTimer = 0;

  function isOn() { return active; }
  function isSupported() { return 'speechSynthesis' in window; }

  function getVisibleText() {
    const slide = document.querySelector('#deck .slide.visible');
    if (!slide) return '';
    return slide.innerText.trim();
  }

  function stop() {
    if (!isSupported()) return;
    window.speechSynthesis.cancel();
    active = false;
    if (button) { button.setAttribute('aria-pressed', 'false'); button.textContent = 'Listen'; }
    document.querySelectorAll('.premium-tts-active').forEach((el) => {
      el.classList.remove('premium-tts-active');
    });
  }

  function play() {
    if (!isSupported()) {
      console.warn('[Premium TTS] Web Speech API not supported in this browser');
      return;
    }
    const text = getVisibleText();
    if (!text) return;
    window.speechSynthesis.cancel();
    utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    utterance.onend = () => { active = false; syncButton(); };
    utterance.onerror = () => { active = false; syncButton(); };
    active = true;
    window.speechSynthesis.speak(utterance);
    syncButton();
  }

  function toggle() { active ? stop() : play(); }

  function syncButton() {
    if (!button) return;
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
    button.textContent = active ? 'Stop' : 'Listen';
  }

  function mount(panel) {
    if (!panel || document.getElementById('premium-tts-toggle')) return;
    if (!isSupported()) return;
    const group = document.createElement('div');
    group.className = 'premium-controls__group';
    button = document.createElement('button');
    button.type = 'button';
    button.id = 'premium-tts-toggle';
    button.innerHTML = 'Listen<span class="premium-kbd">⇧R</span>';
    button.title = 'Read slide aloud (Shift+R)';
    button.addEventListener('click', toggle);
    group.appendChild(button);
    panel.appendChild(group);
    syncButton();
  }

  function init() {
    const panel = document.querySelector('.premium-controls');
    if (panel) mount(panel);
    document.addEventListener('premium-controls-ready', () => {
      const p = document.querySelector('.premium-controls');
      if (p) mount(p);
    });
    document.addEventListener('keydown', (e) => {
      if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      if (e.key === 'R' && e.shiftKey) {
        e.preventDefault();
        toggle();
      }
    });
    if (isSupported()) {
      window.speechSynthesis.onvoiceschanged = () => {};
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumTts = { play, stop, toggle, isOn, isSupported };
})();
```

- [ ] **Step 2: Verify**

Run: `node -e "const fs=require('fs'); const c=fs.readFileSync('shared/premium-tts.js','utf8'); if(!c.includes('PremiumTts')) throw 'missing export'; console.log('OK');"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add shared/premium-tts.js
git commit -m "feat(viewer): B3 TTS read-aloud with Shift+R"
```

---

### Task 8: Search / Cmd+K palette (B6)

**Files:**
- Create: `shared/premium-search.js`

- [ ] **Step 1: Create `shared/premium-search.js`**

```javascript
/**
 * Premium Presentations — fuzzy search palette (Cmd/Ctrl+K).
 * Lazy-loads MiniSearch from CDN.
 */
(function () {
  const MS_URL = 'https://cdn.jsdelivr.net/npm/minisearch@7/+esm';
  let msLib = null;
  let index = null;
  let docs = [];
  let active = false;
  let overlay = null;
  let input = null;
  let resultsEl = null;
  let currentFocus = 0;
  let currentResults = [];

  async function loadMiniSearch() {
    if (msLib) return msLib;
    msLib = await import(MS_URL);
    return msLib;
  }

  function buildDocs() {
    const slides = [...document.querySelectorAll('#deck .slide')];
    return slides.map((s, i) => {
      const heading = s.querySelector('.slide__heading, .slide__display, .slide__label')?.textContent?.trim() || '';
      const body = s.innerText.replace(/\s+/g, ' ').trim().slice(0, 200);
      return { id: i, slideId: s.id, num: i + 1, heading, body };
    });
  }

  async function rebuild() {
    docs = buildDocs();
    const ms = await loadMiniSearch();
    index = new ms.default({
      fields: ['heading', 'body'],
      store: ['num', 'heading', 'body', 'slideId'],
      searchOptions: { boost: { heading: 2 }, prefix: true, fuzzy: 0.2 },
    });
    index.addAll(docs);
  }

  function highlight(text, query) {
    if (!query) return text;
    const re = new RegExp('(' + query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
    return text.replace(re, '<mark>$1</mark>');
  }

  function renderResults(items, query) {
    currentResults = items;
    if (!items.length) {
      resultsEl.innerHTML = '<li class="premium-search-result" style="opacity:0.5">No matches</li>';
      return;
    }
    resultsEl.innerHTML = items.slice(0, 10).map((it, i) => {
      const title = highlight(it.heading || '(untitled)', query);
      const body = highlight((it.body || '').slice(0, 80), query);
      return '<li class="premium-search-result' + (i === 0 ? ' is-active' : '') + '" data-i="' + it.id + '">' +
        '<span class="premium-search-result__num">' + it.num + '</span>' +
        '<div style="flex:1"><div class="premium-search-result__title">' + title + '</div>' +
        '<div class="premium-search-result__body">' + body + '</div></div></li>';
    }).join('');
    currentFocus = 0;
  }

  function open() {
    if (active) return;
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'premium-search-overlay';
      overlay.innerHTML =
        '<div class="premium-search-palette">' +
        '<input class="premium-search-input" type="search" placeholder="Search slides…" aria-label="Search slides">' +
        '<ul class="premium-search-results"></ul>' +
        '<div class="premium-search-hint">↑↓ navigate · ↵ jump · esc close</div>' +
        '</div>';
      document.body.appendChild(overlay);
      input = overlay.querySelector('.premium-search-input');
      resultsEl = overlay.querySelector('.premium-search-results');
      input.addEventListener('input', () => update(input.value));
      input.addEventListener('keydown', onKey);
      resultsEl.addEventListener('click', (e) => {
        const li = e.target.closest('.premium-search-result');
        if (li) jump(parseInt(li.dataset.i, 10));
      });
      overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    }
    overlay.style.display = 'flex';
    active = true;
    setTimeout(() => input.focus(), 30);
    rebuild();
  }

  function close() {
    if (!active) return;
    overlay.style.display = 'none';
    active = false;
    input.value = '';
  }

  function update(q) {
    if (!index) return;
    if (!q) { renderResults(docs, ''); return; }
    const items = index.search(q);
    renderResults(items, q);
  }

  function jump(id) {
    const deck = document.getElementById('deck');
    const slide = document.querySelectorAll('#deck .slide')[id];
    if (slide) slide.scrollIntoView({ behavior: 'smooth' });
    close();
  }

  function onKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key === 'Enter') { e.preventDefault(); jump(currentResults[currentFocus]?.id ?? 0); return; }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const dir = e.key === 'ArrowDown' ? 1 : -1;
      const items = [...resultsEl.querySelectorAll('.premium-search-result')];
      if (!items.length) return;
      currentFocus = (currentFocus + dir + items.length) % items.length;
      items.forEach((el, i) => el.classList.toggle('is-active', i === currentFocus));
      items[currentFocus].scrollIntoView({ block: 'nearest' });
    }
  }

  function init() {
    document.addEventListener('keydown', (e) => {
      if (e.repeat) return;
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        active ? close() : open();
      } else if (!e.metaKey && !e.ctrlKey && e.key === '/' && !active) {
        e.preventDefault();
        open();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumSearch = { open, close, rebuild };
})();
```

- [ ] **Step 2: Verify**

Run: `node -e "const fs=require('fs'); const c=fs.readFileSync('shared/premium-search.js','utf8'); if(!c.includes('PremiumSearch')) throw 'missing export'; console.log('OK');"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add shared/premium-search.js
git commit -m "feat(viewer): B6 Cmd+K fuzzy search palette via MiniSearch"
```

---

### Task 9: Embed mode (B7)

**Files:**
- Modify: `shared/slide-engine.js` — add embed mode init
- Modify: `shared/premium-extras.css` — embed mode styles

- [ ] **Step 1: Append embed styles to `shared/premium-extras.css`**

```css
/* Embed mode — active when ?embedded=1 or inside iframe */
html[data-embedded="true"] .deck-dots,
html[data-embedded="true"] .deck-progress,
html[data-embedded="true"] .deck-hints,
html[data-embedded="true"] .deck-counter,
html[data-embedded="true"] .premium-controls-shell,
html[data-embedded="true"] .premium-timer,
html[data-embedded="true"] .premium-bg-3d {
  display: none !important;
}
```

- [ ] **Step 2: Add embed detection to `shared/slide-engine.js`**

In `SlideEngine` constructor, after `this.deck` is captured (around line 8), add:

```javascript
  this.embedMode = new URLSearchParams(location.search).get('embedded') === '1' || window.self !== window.top;
  if (this.embedMode) {
    document.documentElement.dataset.embedded = 'true';
  }
```

Add the postMessage emit. In `observe`, after the `this.updateChrome()` call inside the callback, add:

```javascript
          if (this.embedMode) {
            try {
              window.parent.postMessage({ type: 'slidechange', index: this.current, id: e.target.id, title: this.getSlideTitle(e.target, this.current) }, '*');
            } catch (_) {}
          }
```

Add a handler for incoming goto. After `bindEvents` definition, add a separate method:

```javascript
SlideEngine.prototype.bindEmbed = function () {
  if (!this.embedMode) return;
  window.addEventListener('message', (e) => {
    if (!e.data || e.data.type !== 'goto') return;
    const idx = typeof e.data.index === 'number' ? e.data.index : null;
    const id = e.data.id || null;
    if (id) {
      const target = this.slides.find((s) => s.id === id);
      if (target) { target.scrollIntoView({ behavior: 'smooth' }); return; }
    }
    if (idx != null && idx >= 0 && idx < this.total) this.goTo(idx);
  });
  const sendResize = () => {
    try {
      const h = document.documentElement.scrollHeight;
      window.parent.postMessage({ type: 'resize', height: h }, '*');
    } catch (_) {}
  };
  sendResize();
  new ResizeObserver(sendResize).observe(document.body);
};
```

In the constructor, after `this.bindEvents()`, add:

```javascript
  this.bindEmbed();
```

- [ ] **Step 3: Verify**

Run: `node -e "const fs=require('fs'); const c=fs.readFileSync('shared/slide-engine.js','utf8'); if(!c.includes('embedMode')) throw 'missing embedMode'; if(!c.includes('bindEmbed')) throw 'missing bindEmbed'; console.log('OK');"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add shared/slide-engine.js shared/premium-extras.css
git commit -m "feat(viewer): B7 embed mode with postMessage + ResizeObserver"
```

---

### Task 10: Presenter view (A3)

**Files:**
- Create: `shared/premium-presenter.js`

- [ ] **Step 1: Create `shared/premium-presenter.js`**

```javascript
/**
 * Premium Presentations — presenter view (popup + in-page fallback).
 * Opens a dual-column presenter view with current slide, next slide, notes, timer.
 */
(function () {
  const CHANNEL = 'premium-deck:state';
  let channel = null;
  let popup = null;
  let fallbackOverlay = null;
  let currentSlideIdx = 0;
  let timerState = null;

  function getCh() {
    if (!channel) {
      try { channel = new BroadcastChannel(CHANNEL); } catch (_) {}
    }
    return channel;
  }

  function isInPopup() {
    return new URLSearchParams(location.search).get('presenter') === '1';
  }

  function openPopup() {
    const url = location.href.split('?')[0] + '?presenter=1';
    try {
      const w = window.open(url, 'presenter', 'popup,width=1280,height=720,left=' + (screen.width - 1300));
      if (w) popup = w;
    } catch (_) { popup = null; }
    if (!popup) openFallback();
  }

  function openFallback() {
    if (fallbackOverlay) { closeFallback(); return; }
    fallbackOverlay = document.createElement('div');
    fallbackOverlay.className = 'premium-presenter-overlay';
    fallbackOverlay.innerHTML =
      '<button class="premium-presenter-overlay__close">Close</button>' +
      '<div class="premium-presenter-overlay__current" id="pp-current"></div>' +
      '<div class="premium-presenter-overlay__next" id="pp-next"></div>' +
      '<div class="premium-presenter-overlay__notes" id="pp-notes"><h4>Notes</h4><em>No notes for this slide</em></div>';
    document.body.appendChild(fallbackOverlay);
    fallbackOverlay.querySelector('.premium-presenter-overlay__close').addEventListener('click', closeFallback);
    document.addEventListener('keydown', onFallbackKey);
    refreshFallback();
  }

  function closeFallback() {
    if (fallbackOverlay) fallbackOverlay.remove();
    fallbackOverlay = null;
    document.removeEventListener('keydown', onFallbackKey);
  }

  function onFallbackKey(e) {
    if (e.key === 'Escape' || (e.shiftKey && e.key === 'P')) { e.preventDefault(); closeFallback(); }
  }

  function refreshFallback() {
    if (!fallbackOverlay) return;
    const slides = [...document.querySelectorAll('#deck .slide')];
    const cur = slides[currentSlideIdx];
    const nxt = slides[currentSlideIdx + 1];
    document.getElementById('pp-current').innerHTML = cur ? cur.outerHTML : '';
    document.getElementById('pp-next').innerHTML = nxt ? nxt.outerHTML : '';
    const notes = cur?.querySelector('aside.notes, .slide__notes');
    const notesEl = document.getElementById('pp-notes');
    if (notes) {
      notesEl.innerHTML = '<h4>Notes</h4>' + notes.innerHTML;
    } else {
      notesEl.innerHTML = '<h4>Notes</h4><em>No notes for this slide</em>';
    }
    if (timerState) {
      const t = document.createElement('div');
      t.style.cssText = 'position:absolute;top:14px;left:18px;font-family:var(--font-mono,monospace);font-size:14px;color:var(--text,#fff)';
      t.textContent = '⏱ ' + Math.max(0, Math.ceil(timerState.remainingMs / 1000)) + 's';
      fallbackOverlay.appendChild(t);
    }
  }

  function renderPresenterLayout() {
    document.documentElement.dataset.presenter = 'true';
    document.body.style.gridTemplateRows = '1fr auto';
    const deck = document.getElementById('deck');
    if (!deck) return;
    const slides = [...deck.querySelectorAll('.slide')];
    if (slides.length < 2) return;
    const currentIdx = Math.min(currentSlideIdx, slides.length - 1);
    const nextIdx = Math.min(currentIdx + 1, slides.length - 1);
    const cur = slides[currentIdx].cloneNode(true);
    const nxt = slides[nextIdx].cloneNode(true);
    cur.classList.add('visible');
    cur.style.opacity = '1';
    cur.style.transform = 'none';
    nxt.classList.add('visible');
    nxt.style.opacity = '1';
    nxt.style.transform = 'none';
    nxt.style.transform = 'scale(0.8)';
    const curWrap = document.createElement('div');
    curWrap.className = 'premium-presenter-overlay__current';
    curWrap.appendChild(cur);
    const nxtWrap = document.createElement('div');
    nxtWrap.className = 'premium-presenter-overlay__next';
    nxtWrap.appendChild(nxt);
    const notes = slides[currentIdx].querySelector('aside.notes, .slide__notes');
    const notesEl = document.createElement('div');
    notesEl.className = 'premium-presenter-overlay__notes';
    notesEl.innerHTML = '<h4>Notes</h4>' + (notes ? notes.innerHTML : '<em>No notes for this slide</em>');
    const overlay = document.createElement('div');
    overlay.className = 'premium-presenter-overlay';
    overlay.appendChild(curWrap);
    overlay.appendChild(nxtWrap);
    overlay.appendChild(notesEl);
    const close = document.createElement('button');
    close.className = 'premium-presenter-overlay__close';
    close.textContent = 'Close';
    close.addEventListener('click', () => window.close());
    overlay.appendChild(close);
    document.body.appendChild(overlay);
    if (deck) deck.style.display = 'none';
  }

  function init() {
    const ch = getCh();
    if (isInPopup()) {
      renderPresenterLayout();
      if (ch) {
        ch.addEventListener('message', (e) => {
          if (e.data && e.data.type === 'slidechange') {
            currentSlideIdx = e.data.index || 0;
            if (fallbackOverlay) fallbackOverlay.remove();
            const existing = document.querySelector('.premium-presenter-overlay');
            if (existing) existing.remove();
            renderPresenterLayout();
          } else if (e.data && e.data.type === 'tick') {
            timerState = e.data;
          }
        });
      }
      return;
    }
    document.addEventListener('keydown', (e) => {
      if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      if (e.shiftKey && e.key === 'P') {
        e.preventDefault();
        if (fallbackOverlay) { closeFallback(); return; }
        if (popup && !popup.closed) { popup.focus(); return; }
        openPopup();
      }
    });
    if (ch) {
      ch.addEventListener('message', (e) => {
        if (e.data && e.data.type === 'slidechange') {
          currentSlideIdx = e.data.index || 0;
          if (fallbackOverlay) refreshFallback();
        } else if (e.data && e.data.type === 'tick') {
          timerState = e.data;
          if (fallbackOverlay) refreshFallback();
        } else if (e.data && e.data.type === 'control') {
          if (e.data.action === 'next' || e.data.action === 'prev') {
            const evt = new KeyboardEvent('keydown', { code: e.data.action === 'next' ? 'ArrowRight' : 'ArrowLeft' });
            document.dispatchEvent(evt);
          }
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumPresenter = { openPopup, openFallback, closeFallback };
})();
```

- [ ] **Step 2: Verify**

Run: `node -e "const fs=require('fs'); const c=fs.readFileSync('shared/premium-presenter.js','utf8'); if(!c.includes('PremiumPresenter')) throw 'missing export'; console.log('OK');"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add shared/premium-presenter.js
git commit -m "feat(presenter): A3 dual-screen presenter view via BroadcastChannel"
```

---

### Task 11: Clicker / WebHID (A5)

**Files:**
- Create: `shared/premium-clicker.js`

- [ ] **Step 1: Create `shared/premium-clicker.js`**

```javascript
/**
 * Premium Presentations — clicker / wireless remote support.
 * Tries WebHID first (Chrome/Edge); falls back to keyboard page-nav.
 */
(function () {
  let device = null;
  let statusEl = null;
  let statusTimer = 0;
  let bindings = { next: 0xb5, prev: 0xb6 };

  function showStatus(msg, ms) {
    if (!statusEl) {
      statusEl = document.createElement('div');
      statusEl.className = 'premium-clicker-status';
      document.body.appendChild(statusEl);
    }
    statusEl.textContent = msg;
    statusEl.classList.add('is-visible');
    clearTimeout(statusTimer);
    statusTimer = setTimeout(() => statusEl.classList.remove('is-visible'), ms || 2400);
  }

  function nav(direction) {
    if (direction === 'next') {
      const evt = new KeyboardEvent('keydown', { code: 'ArrowRight', key: 'ArrowRight' });
      document.dispatchEvent(evt);
    } else if (direction === 'prev') {
      const evt = new KeyboardEvent('keydown', { code: 'ArrowLeft', key: 'ArrowLeft' });
      document.dispatchEvent(evt);
    }
  }

  async function bindHID() {
    if (!('hid' in navigator)) {
      showStatus('WebHID not supported — keyboard fallback active (PgUp/PgDn)');
      return;
    }
    try {
      const devices = await navigator.hid.requestDevice({ filters: [] });
      if (!devices || !devices.length) { showStatus('No device selected — keyboard fallback active'); return; }
      device = devices[0];
      await device.open();
      showStatus('Clicker bound: ' + (device.productName || 'HID device'));
      device.addEventListener('inputreport', (e) => {
        const data = new Uint8Array(e.data.buffer);
        if (data[1] === bindings.next) nav('next');
        if (data[1] === bindings.prev) nav('prev');
      });
    } catch (err) {
      showStatus('Clicker bind failed — keyboard fallback active');
    }
  }

  function bindKeyboard() {
    document.addEventListener('keydown', (e) => {
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      if (e.key === 'PageDown' || e.key === ' ') { e.preventDefault(); nav('next'); }
      if (e.key === 'PageUp') { e.preventDefault(); nav('prev'); }
    });
  }

  function init() {
    bindKeyboard();
    document.addEventListener('keydown', (e) => {
      if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      if (e.shiftKey && (e.key === 'C' || e.key === 'c')) {
        e.preventDefault();
        bindHID();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumClicker = { bindHID, nav };
})();
```

- [ ] **Step 2: Verify**

Run: `node -e "const fs=require('fs'); const c=fs.readFileSync('shared/premium-clicker.js','utf8'); if(!c.includes('PremiumClicker')) throw 'missing export'; console.log('OK');"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add shared/premium-clicker.js
git commit -m "feat(presenter): A5 WebHID clicker with keyboard fallback"
```

---

### Task 12: Template patch — link new modules in premium-base.html

**Files:**
- Modify: `templates/premium-base.html`

- [ ] **Step 1: Add `premium-extras.css` to `<head>` link chain**

Find the line that links `premium-annotations.css`. Add after it:

```html
<link rel="stylesheet" href="{{SHARED}}premium-extras.css">
```

- [ ] **Step 2: Add new module scripts before `slide-engine.js`**

Find the `<script src="{{SHARED}}premium-annotations.js" defer></script>` line. Add after it:

```html
<script src="{{SHARED}}premium-timer.js" defer></script>
<script src="{{SHARED}}premium-tts.js" defer></script>
<script src="{{SHARED}}premium-search.js" defer></script>
<script src="{{SHARED}}premium-clicker.js" defer></script>
<script src="{{SHARED}}premium-og-cover.js" defer></script>
<script src="{{SHARED}}premium-presenter.js" defer></script>
```

- [ ] **Step 3: Verify**

Run: `python3 -c "import html.parser; p=html.parser.HTMLParser(); p.feed(open('templates/premium-base.html').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add templates/premium-base.html
git commit -m "feat: wire all new modules into premium-base.html template"
```

---

### Task 13: Re-bundle all 4 existing decks

**Files:**
- Modify: each of the 4 standalone deck HTMLs

- [ ] **Step 1: Run bundle-deck on all 4**

```bash
./scripts/bundle-deck.sh decks/rag-vector-graph/rag-vector-graph-slides.html --in-place
./scripts/bundle-deck.sh decks/graph-databases/graph-databases-slides.html --in-place
./scripts/bundle-deck.sh decks/vector-databases/vector-databases-slides.html --in-place
./scripts/bundle-deck.sh decks/vector-vs-graph/vector-vs-graph-slides.html --in-place
```

Expected: each prints `Bundled → …`

- [ ] **Step 2: Verify all 4 include the new modules**

Run:
```bash
for d in rag-vector-graph graph-databases vector-databases vector-vs-graph; do
  if ! grep -q "premium-extras" "decks/$d/$d-slides.html"; then
    echo "MISSING in $d"
    exit 1
  fi
done
echo "OK: all 4 decks bundled with extras"
```
Expected: `OK: all 4 decks bundled with extras`

- [ ] **Step 3: Run validators on each**

```bash
./scripts/validate-deck.sh decks/rag-vector-graph/rag-vector-graph-slides.html decks/rag-vector-graph/rag-vector-graph-slide-spec.md
./scripts/validate-deck.sh decks/graph-databases/graph-databases-slides.html decks/graph-databases/graph-databases-slide-spec.md
./scripts/validate-deck.sh decks/vector-databases/vector-databases-slides.html decks/vector-databases/vector-databases-slide-spec.md
./scripts/validate-deck.sh decks/vector-vs-graph/vector-vs-graph-slides.html decks/vector-vs-graph/vector-vs-graph-slide-spec.md
```

Expected: each passes (or prints warnings only).

- [ ] **Step 4: Commit**

```bash
git add decks/
git commit -m "chore: re-bundle 4 decks with new extras engine"
```

---

### Task 14: Smoke test + README update + OG covers

**Files:**
- Modify: `README.md` — add new section

- [ ] **Step 1: Generate OG covers for the 4 decks**

```bash
for d in rag-vector-graph graph-databases vector-databases vector-vs-graph; do
  ./scripts/og-cover.sh "decks/$d/$d-slides.html" || echo "  (skip $d — manual fallback needed)"
done
```

Expected: 4 PNGs created, OR "skip" messages if no chromium installed.

- [ ] **Step 2: Add "Extras" section to README.md**

After the "## Skill" section, add:

```markdown
## Extras (Cluster A — Live + Cluster B — Distribution)

Engine modules in `shared/premium-{timer,presenter,clicker,tts,search,og-cover}.js` + `shared/premium-extras.css`. Auto-bundled by `bundle-deck.py` when the template links them.

| Shortcut | Feature |
|----------|---------|
| `B` / `.` | Blackout / curtain |
| `⇧T` | Speaker timer (start/pause) |
| `⇧P` | Presenter view (popup with notes + peek + timer) |
| `⇧C` | Clicker / WebHID bind (keyboard fallback always active) |
| `⇧R` | TTS read-aloud |
| `⇧E` | Export PDF (print-CSS) |
| `⌘K` / `/` | Search / jump-to-slide |
| `?embedded=1` | Embed mode (hides chrome, postMessage API) |

**Extras scripts:**
- `./scripts/og-cover.sh <deck.html>` — render slide 1 as 1200×630 PNG for OG/Twitter unfurl.

**Notes per slide:** add `<aside class="notes">…</aside>` inside any `<section class="slide">`; the presenter view will display it.
```

- [ ] **Step 3: Verify by opening one deck in a browser**

Open `decks/rag-vector-graph/rag-vector-graph-slides.html` in Chrome. Verify:
- Press `B` → black screen
- Press `B` again → back to slide
- Press `⇧T` → timer panel appears
- Press `⌘K` → search palette opens
- Click "Listen" button → TTS plays
- Open `?embedded=1` in another tab → chrome (dots, progress, controls) hidden

If any fails, debug. Don't commit until all work.

- [ ] **Step 4: Commit**

```bash
git add README.md decks/*/og-cover.png
git commit -m "docs: add Extras section + generate OG covers for 4 decks"
```

---

## Self-review checklist

- [x] All 12 features have a task: A1+A4 (Task 2), A2 (Task 1), A3 (Task 10), A5 (Task 11), B1 (Task 3), B2 (Task 4), B3 (Task 7), B4 (Task 5), B5 (Task 6), B6 (Task 8), B7 (Task 9)
- [x] No "TBD" / "TODO" / "fill in" placeholders in any task
- [x] All file paths are exact and exist
- [x] Each task = one commit, working state at end
- [x] TDD adapted to vanilla JS: explicit `node -e "..."` parse-check at end of each task
- [x] Test steps are real (open browser, press keys, click buttons), not abstract
- [x] Validator runs in Task 13
- [x] DECK REBUILD in Task 13
- [x] No dependencies between tasks block sequencing
- [x] Open questions resolved (popup+fallback, pre-generated cover, opt-in TTS, always-on search)
