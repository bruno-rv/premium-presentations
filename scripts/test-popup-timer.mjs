// Test that timer controls in the popup drive the deck's PremiumTimer.
// Reproduces: popup loads, user clicks Start, deck's timer should start.

import { JSDOM } from 'jsdom';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHARED = join(__dirname, '..', 'shared');

class FakeBC {
  constructor(name) {
    this.name = name;
    FakeBC.channels.set(name, FakeBC.channels.get(name) || []);
    FakeBC.channels.get(name).push(this);
    this.listeners = [];
  }
  postMessage(data) {
    const peers = FakeBC.channels.get(this.name) || [];
    for (const p of peers) {
      if (p === this) continue;
      for (const l of p.listeners) try { l({ data }); } catch (e) { console.error('BC handler err', e); }
    }
  }
  addEventListener(_, l) { this.listeners.push(l); }
  close() {}
}
FakeBC.channels = new Map();
globalThis.BroadcastChannel = FakeBC;

function makeWindow({ url, withSlides = true, focused = true } = {}) {
  const html = `<!doctype html><html><head></head><body>
    <div id="deck">
      ${withSlides ? `
      <section class="slide" id="slide-1"><h1 class="slide__display">One</h1></section>
      <section class="slide" id="slide-2"><h1 class="slide__display">Two</h1></section>
      ` : ''}
    </div>
  </body></html>`;
  const dom = new JSDOM(html, {
    url, runScripts: 'outside-only', pretendToBeVisual: true,
  });
  if (!dom.window.crypto || !dom.window.crypto.randomUUID) {
    dom.window.crypto = dom.window.crypto || {};
    dom.window.crypto.randomUUID = () => 'sess-' + Math.random().toString(36).slice(2, 10);
  }
  Object.defineProperty(dom.window.document, 'hasFocus', { value: () => focused, configurable: true });
  const ioInstances = [];
  dom.window.IntersectionObserver = class {
    constructor(cb) { this.cb = cb; ioInstances.push(this); }
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  dom.window.HTMLElement.prototype.scrollIntoView = function () {
    for (const io of ioInstances) try { io.cb([{ target: this, isIntersecting: true }]); } catch (_) {}
  };
  dom.window.requestAnimationFrame = (cb) => setTimeout(cb, 0);
  dom.window.BroadcastChannel = FakeBC;
  dom.window.matchMedia = dom.window.matchMedia || (() => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }));
  return dom;
}

function loadScript(dom, path) {
  dom.window.eval(readFileSync(join(SHARED, path), 'utf8'));
}

console.log('Test: popup Start button → deck timer starts');
const deck = makeWindow({ url: 'http://localhost/deck.html', focused: false });
loadScript(deck, 'premium-controller.js');
await new Promise((r) => setTimeout(r, 0));
loadScript(deck, 'premium-timer.js');
const slideEngineJs = readFileSync(join(SHARED, 'slide-engine.js'), 'utf8');
deck.window.eval(slideEngineJs);
deck.window.eval('new SlideEngine();');
loadScript(deck, 'premium-presenter.js');

const deckSession = deck.window.document.documentElement.dataset.session;
console.log('  deck session:', deckSession);

// Popup on the SAME session.
const popup = makeWindow({ url: 'http://localhost/deck.html?presenter=1&session=' + deckSession, focused: true, withSlides: false });
loadScript(popup, 'premium-controller.js');
await new Promise((r) => setTimeout(r, 0));
loadScript(popup, 'premium-presenter.js');

await new Promise((r) => setTimeout(r, 100));

// Verify popup built with controls
const startBtn = popup.window.document.getElementById('pp-start');
if (!startBtn) throw new Error('pp-start missing');
const minutesInput = popup.window.document.getElementById('pp-minutes');
if (!minutesInput) throw new Error('pp-minutes missing');

// Verify deck has PremiumTimer
const PT = deck.window.PremiumTimer;
if (!PT) throw new Error('deck PremiumTimer missing');
console.log('  deck PremiumTimer before start:', JSON.stringify(PT.getState()));

// User sets minutes to 5
minutesInput.value = '5';
// Simulate input event to fire debounce
const inputEvent = new popup.window.Event('input', { bubbles: true });
minutesInput.dispatchEvent(inputEvent);
await new Promise((r) => setTimeout(r, 500));

console.log('  deck PremiumTimer after setMinutes(5):', JSON.stringify(PT.getState()));

// User clicks Start
startBtn.click();
await new Promise((r) => setTimeout(r, 100));

const state = PT.getState();
console.log('  deck PremiumTimer after Start click:', JSON.stringify(state));
if (!state.running) {
  throw new Error('expected deck timer running, got ' + JSON.stringify(state));
}

console.log('  PASS — popup Start button drives deck timer');

console.log('Test: popup Pause button stops deck timer');
const pauseBtn = popup.window.document.getElementById('pp-pause');
pauseBtn.click();
await new Promise((r) => setTimeout(r, 100));

const state2 = PT.getState();
console.log('  deck PremiumTimer after Pause click:', JSON.stringify(state2));
if (state2.running) {
  throw new Error('expected deck timer NOT running, got running');
}

console.log('  PASS — popup Pause button stops deck timer');

console.log('Test: popup Reset button stops + resets deck timer');
// First restart so we have non-zero elapsed.
startBtn.click();
await new Promise((r) => setTimeout(r, 200));
const resetBtn = popup.window.document.getElementById('pp-reset');
resetBtn.click();
await new Promise((r) => setTimeout(r, 100));

const state3 = PT.getState();
console.log('  deck PremiumTimer after Reset click:', JSON.stringify(state3));
if (state3.running) throw new Error('expected deck timer not running after reset, got running');
if (state3.elapsedMs > 1000) throw new Error('expected elapsedMs near 0 after reset, got ' + state3.elapsedMs);

console.log('  PASS — popup Reset button stops + resets deck timer');

process.exit(0);
