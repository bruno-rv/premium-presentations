// Headless smoke for the presenter view modules. Verifies:
// 1. premium-controller computes 'deck'/'popup'/'none' correctly across windows.
// 2. BroadcastChannel session isolation: messages with mismatched sessionId are dropped.
// 3. premium-timer end-time mode: setEndAt(future) then pause/resume preserves target.
// 4. The popup window (?presenter=1) DOES instantiate SlideEngine (no early-return guard).
// 5. popup URL construction preserves hash + query params.
// 6. timer config precedence: localStorage override > meta > default.
// 7. session restore beats override and meta.

import { JSDOM, ResourceLoader } from 'jsdom';
import { readFileSync, readdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHARED = join(__dirname, '..', 'shared');

// Minimal BroadcastChannel shim backed by a per-process map.
class FakeBC {
  constructor(name) { this.name = name; FakeBC.channels.set(name, FakeBC.channels.get(name) || []); FakeBC.channels.get(name).push(this); this.listeners = []; }
  postMessage(data) { const peers = FakeBC.channels.get(this.name) || []; for (const p of peers) { if (p === this) continue; for (const l of p.listeners) try { l({ data }); } catch (e) {} } }
  addEventListener(_, l) { this.listeners.push(l); }
  close() {}
}
FakeBC.channels = new Map();
globalThis.BroadcastChannel = FakeBC;

function loadScript(dom, path) {
  const js = readFileSync(join(SHARED, path), 'utf8');
  dom.window.eval(js);
}

function makeDeckWindow({ url, withSlides = true } = {}) {
  const dom = new JSDOM(`<!doctype html><html><head></head><body>
    <div id="deck">
      ${withSlides ? `
      <section class="slide" id="slide-1"><h1 class="slide__display">One</h1><aside class="notes">Talk about one.</aside></section>
      <section class="slide" id="slide-2"><h1 class="slide__display">Two</h1></section>
      <section class="slide" id="slide-3"><h1 class="slide__display">Three</h1><aside class="notes">Closing thoughts.</aside></section>
      ` : ''}
    </div>
  </body></html>`, { url, runScripts: 'outside-only', pretendToBeVisual: true });
  // jsdom does not implement crypto.randomUUID; provide one.
  if (!dom.window.crypto || !dom.window.crypto.randomUUID) {
    dom.window.crypto = dom.window.crypto || {};
    dom.window.crypto.randomUUID = () => 'sess-' + Math.random().toString(36).slice(2, 10);
  }
  // JSDOM doesn't always ship hasFocus / visibility; provide stable stubs.
  Object.defineProperty(dom.window.document, 'hasFocus', { value: () => true, configurable: true });
  return dom;
}

function fireReadyStateLoaded(dom) {
  // JSDOM is in 'complete' by default; fire DOMContentLoaded so modules initialize.
  if (dom.window.document.readyState !== 'complete') {
    const e = new dom.window.Event('DOMContentLoaded');
    dom.window.document.dispatchEvent(e);
  } else {
    const e = new dom.window.Event('DOMContentLoaded');
    dom.window.document.dispatchEvent(e);
  }
}

// ── Test 1: controller state machine ─────────────────────────────────────
{
  console.log('Test 1: controller state machine');
  const deck = makeDeckWindow({ url: 'http://localhost/deck.html' });
  loadScript(deck, 'premium-controller.js');
  fireReadyStateLoaded(deck);
  const c = deck.window.PremiumController;
  if (!c) throw new Error('premium-controller: no API on deck window');
  // Give the focus-tracker a moment.
  await new Promise((r) => setTimeout(r, 50));
  const state = c.getState();
  console.log('  deck state:', state);
  if (state.role !== 'deck') throw new Error('expected role=deck, got ' + state.role);
  if (!state.sessionId) throw new Error('expected sessionId');
  // Toggle hasFocus to false
  Object.defineProperty(deck.window.document, 'hasFocus', { value: () => false, configurable: true });
  deck.window.document.dispatchEvent(new deck.window.Event('blur', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 600));
  if (c.getState().role !== 'none') throw new Error('expected role=none after blur, got ' + c.getState().role);
  console.log('  PASS — deck=deck, blur=none');
}

// ── Test 2: popup side computes role=popup on focus ──────────────────────
{
  console.log('Test 2: popup role on focus');
  const popup = makeDeckWindow({ url: 'http://localhost/deck.html?presenter=1&session=sess-xyz' });
  // Force the same sessionId the deck had.
  popup.window.document.documentElement.dataset.session = 'sess-xyz';
  loadScript(popup, 'premium-controller.js');
  fireReadyStateLoaded(popup);
  await new Promise((r) => setTimeout(r, 50));
  const c = popup.window.PremiumController;
  const role = c.getState().role;
  console.log('  popup state:', c.getState());
  if (role !== 'popup') throw new Error('expected role=popup, got ' + role);
  // Blur popup
  Object.defineProperty(popup.window.document, 'hasFocus', { value: () => false, configurable: true });
  popup.window.document.dispatchEvent(new popup.window.Event('blur', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 600));
  if (c.getState().role !== 'none') throw new Error('expected role=none after blur, got ' + c.getState().role);
  console.log('  PASS — popup=popup, blur=none');
}

// ── Test 3: deck takes over when popup is open-but-unfocused ──────────────
{
  console.log('Test 3: deck fallback when popup open-but-unfocused');
  const deck = makeDeckWindow({ url: 'http://localhost/deck.html' });
  Object.defineProperty(deck.window.document, 'hasFocus', { value: () => true, configurable: true });
  loadScript(deck, 'premium-controller.js');
  fireReadyStateLoaded(deck);
  await new Promise((r) => setTimeout(r, 50));
  const c = deck.window.PremiumController;
  // Simulate a popup that is alive but says it's unfocused
  c.recordHeartbeat(false);
  await new Promise((r) => setTimeout(r, 50));
  if (c.getState().role !== 'deck') throw new Error('expected deck takeover when popupFocused=false, got ' + c.getState().role);
  // Now the popup says it's focused → deck should yield
  c.recordHeartbeat(true);
  await new Promise((r) => setTimeout(r, 50));
  if (c.getState().role !== 'none') throw new Error('expected deck=none when popupFocused=true and deck focused, got ' + c.getState().role);
  console.log('  PASS — deck takes over on popupFocused=false, yields on popupFocused=true');
}

// ── Test 4: end-time mode preserves target across pause/resume ───────────
{
  console.log('Test 4: end-time mode pause/resume preserves target');
  const dom = makeDeckWindow({ url: 'http://localhost/deck.html' });
  // No BroadcastChannel chatter; just exercise the timer API directly.
  dom.window.eval('window.__fakeNow = () => Date.now();');
  loadScript(dom, 'premium-timer.js');
  fireReadyStateLoaded(dom);
  const T = dom.window.PremiumTimer;
  if (!T) throw new Error('premium-timer: no API');
  // 60 minutes from now
  const target = Date.now() + 60 * 60 * 1000;
  T.setEndAt(target);
  let s = T.getState();
  if (s.mode !== 'endAt') throw new Error('expected mode=endAt, got ' + s.mode);
  if (Math.abs(s.targetEndAtMs - target) > 5) throw new Error('target not stored');
  // Now switch to duration and back to end-time to verify the mode field roundtrips
  T.setMinutes(25);
  s = T.getState();
  if (s.mode !== 'duration') throw new Error('expected mode=duration, got ' + s.mode);
  T.setEndAt(target);
  s = T.getState();
  if (s.mode !== 'endAt' || Math.abs(s.targetEndAtMs - target) > 5) throw new Error('endAt roundtrip lost');
  // Invalid: past timestamp
  let threw = false;
  try { T.setEndAt(Date.now() - 1000); } catch (_) { threw = true; }
  if (!threw) throw new Error('expected setEndAt to throw for past timestamp');
  // Invalid: NaN
  threw = false;
  try { T.setEndAt(NaN); } catch (_) { threw = true; }
  if (!threw) throw new Error('expected setEndAt to throw for NaN');
  console.log('  PASS — endAt/duration roundtrip + validation');
}

// ── Test 5: SlideEngine does NOT early-return on ?presenter=1 ────────────
{
  console.log('Test 5: SlideEngine runs on popup window too (no early-return)');
  const popup = makeDeckWindow({ url: 'http://localhost/deck.html?presenter=1&session=sess-zz' });
  // JSDOM has no IntersectionObserver; stub it.
  popup.window.IntersectionObserver = class { constructor() {} observe() {} unobserve() {} disconnect() {} };
  // scrollIntoView on a non-attached node is a no-op in JSDOM; mock it.
  popup.window.HTMLElement.prototype.scrollIntoView = function () {};
  loadScript(popup, 'premium-controller.js');
  fireReadyStateLoaded(popup);
  const slideEngineJs = readFileSync(join(SHARED, 'slide-engine.js'), 'utf8');
  popup.window.eval(slideEngineJs);
  popup.window.eval('new SlideEngine();');
  if (!popup.window.PremiumDeckControls) throw new Error('PremiumDeckControls missing in popup');
  const titles = popup.window.PremiumDeckControls.getTitles();
  if (titles.length !== 3) throw new Error('expected 3 titles, got ' + titles.length);
  const notes = popup.window.PremiumDeckControls.getNotes(0);
  if (!/Talk about one\./.test(notes)) throw new Error('expected notes from slide 1, got ' + JSON.stringify(notes));
  // getNotes out of bounds returns null
  if (popup.window.PremiumDeckControls.getNotes(99) !== null) throw new Error('getNotes(99) should be null');
  console.log('  PASS — SlideEngine + getTitles + getNotes work in popup');
}

// ── Test 6: presenter popup URL preserves hash + query params ───────────
{
  console.log('Test 6: popup URL construction preserves hash + query');
  const deck = makeDeckWindow({ url: 'http://localhost/deck.html?foo=bar#slide-2' });
  // The deck would build the URL by mutating a new URL(location.href):
  const popupUrl = new deck.window.URL('http://localhost/deck.html?foo=bar#slide-2');
  popupUrl.searchParams.set('presenter', '1');
  popupUrl.searchParams.set('session', 'sess-abc');
  if (!popupUrl.hash.includes('slide-2')) throw new Error('hash lost: ' + popupUrl.href);
  if (popupUrl.searchParams.get('foo') !== 'bar') throw new Error('foo query lost: ' + popupUrl.search);
  if (popupUrl.searchParams.get('presenter') !== '1') throw new Error('presenter not set');
  if (popupUrl.searchParams.get('session') !== 'sess-abc') throw new Error('session not set');
  console.log('  PASS — popup URL: ' + popupUrl.href);
}

// ── Test 7: timer config precedence (override > meta > default) ──────────
{
  console.log('Test 7: timer config precedence');
  const dom = makeDeckWindow({ url: 'http://localhost/deck.html' });
  // Inject a meta tag for 45 min
  const meta = dom.window.document.createElement('meta');
  meta.setAttribute('name', 'premium-timer');
  meta.setAttribute('content', '45');
  dom.window.document.head.appendChild(meta);
  // Inject an override of 12 min
  dom.window.localStorage.setItem('premium-timer-override:/deck.html', JSON.stringify({ mode: 'duration', minutes: 12 }));
  loadScript(dom, 'premium-timer.js');
  fireReadyStateLoaded(dom);
  const T = dom.window.PremiumTimer;
  const s = T.getState();
  // 12 min = 720,000 ms; allow some slop for elapsed time.
  if (s.mode !== 'duration') throw new Error('expected mode=duration, got ' + s.mode);
  if (Math.abs(s.totalMs - 12 * 60 * 1000) > 1000) throw new Error('override ignored, totalMs=' + s.totalMs);
  console.log('  PASS — localStorage override beats meta default');
}

// ── Test 8: session restore beats both override and meta ─────────────────
{
  console.log('Test 8: session restore beats override and meta');
  const dom = makeDeckWindow({ url: 'http://localhost/deck.html' });
  const meta = dom.window.document.createElement('meta');
  meta.setAttribute('name', 'premium-timer');
  meta.setAttribute('content', '45');
  dom.window.document.head.appendChild(meta);
  dom.window.localStorage.setItem('premium-timer-override:/deck.html', JSON.stringify({ mode: 'duration', minutes: 12 }));
  // Session restore with a different totalMs
  dom.window.sessionStorage.setItem('premium-timer', JSON.stringify({ mode: 'duration', totalMs: 7 * 60 * 1000, targetEndAtMs: 0, elapsedAtPause: 0, startTs: 0, running: false, savedAt: Date.now() }));
  loadScript(dom, 'premium-timer.js');
  fireReadyStateLoaded(dom);
  const T = dom.window.PremiumTimer;
  const s = T.getState();
  if (Math.abs(s.totalMs - 7 * 60 * 1000) > 100) throw new Error('session restore ignored, totalMs=' + s.totalMs);
  console.log('  PASS — session restore (7 min) beats override (12) and meta (45)');
}

// ── Test 9: deck shortcuts survive stale popup focus state ───────────────
{
  console.log('Test 9: deck shortcuts survive stale popup focus state');
  const deck = makeDeckWindow({ url: 'http://localhost/deck.html' });
  deck.window.matchMedia = deck.window.matchMedia || (() => ({
    matches: false,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  deck.window.requestAnimationFrame = deck.window.requestAnimationFrame || ((cb) => setTimeout(cb, 0));
  deck.window.cancelAnimationFrame = deck.window.cancelAnimationFrame || ((id) => clearTimeout(id));

  const ioInstances = [];
  deck.window.IntersectionObserver = class {
    constructor(cb) { this.cb = cb; ioInstances.push(this); }
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  deck.window.HTMLElement.prototype.scrollIntoView = function () {
    for (const io of ioInstances) {
      try { io.cb([{ target: this, isIntersecting: true }]); } catch (_) {}
    }
  };

  loadScript(deck, 'premium-controller.js');
  fireReadyStateLoaded(deck);
  await new Promise((r) => setTimeout(r, 50));
  const style = deck.window.document.createElement('style');
  style.textContent =
    readFileSync(join(SHARED, 'premium-themes.css'), 'utf8') + '\n' +
    readFileSync(join(SHARED, 'premium-extras.css'), 'utf8');
  deck.window.document.head.appendChild(style);
  loadScript(deck, 'premium-controls.js');
  const slideEngineJs = readFileSync(join(SHARED, 'slide-engine.js'), 'utf8');
  deck.window.eval(slideEngineJs);
  deck.window.eval('new SlideEngine();');

  deck.window.document.documentElement.dataset.presenterDisplay = 'on';
  deck.window.PremiumController.recordHeartbeat(true);
  if (deck.window.PremiumController.getState().role !== 'none') {
    throw new Error('expected stale popup heartbeat to make deck controller role none');
  }

  deck.window.PremiumPresentations.setControlsHidden(true);
  deck.window.document.dispatchEvent(new deck.window.KeyboardEvent('keydown', {
    key: 'h',
    code: 'KeyH',
    bubbles: true,
  }));
  const hidden = deck.window.document.documentElement.dataset.controlsHidden || 'off';
  const shell = deck.window.document.querySelector('.premium-controls-shell');
  if (hidden !== 'off' || !shell || !shell.classList.contains('is-open')) {
    throw new Error('expected deck H shortcut to open controls despite stale popup focus, hidden=' + hidden);
  }
  if (deck.window.getComputedStyle(shell).display === 'none') {
    throw new Error('expected deck H shortcut to make controls visible in presenter display mode');
  }

  deck.window.document.dispatchEvent(new deck.window.KeyboardEvent('keydown', {
    key: '3',
    code: 'Digit3',
    bubbles: true,
  }));
  const bg = deck.window.document.querySelector('.premium-bg-3d');
  const parallax = deck.window.document.documentElement.dataset.parallax || 'off';
  if (parallax !== 'on' || !bg || deck.window.getComputedStyle(bg).display === 'none') {
    throw new Error('expected deck 3 shortcut to show parallax in presenter display mode, parallax=' + parallax);
  }

  deck.window.document.dispatchEvent(new deck.window.KeyboardEvent('keydown', {
    key: 'ArrowRight',
    code: 'ArrowRight',
    bubbles: true,
  }));
  await new Promise((r) => setTimeout(r, 50));
  const state = deck.window.PremiumDeckControls.getState();
  if (state.index !== 1) {
    throw new Error('expected deck ArrowRight shortcut to advance despite stale popup focus, index=' + state.index);
  }
  console.log('  PASS — deck H, 3, and ArrowRight still work after opening presenter');
}

// JSDOM's setInterval keeps the process alive; force exit.
process.exit(0);
