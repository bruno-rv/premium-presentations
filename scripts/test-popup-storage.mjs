// File:// transport regression test: simulates Chrome's file:// behavior by
// stripping BroadcastChannel and window.opener, leaving only the localStorage
// 'storage' event as a cross-window channel. Proves postToPeer still works.

import { JSDOM } from 'jsdom';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHARED = join(__dirname, '..', 'assets', 'shared');

function makeWindow({ url, withSlides = true, focused = true } = {}) {
  const html = `<!doctype html><html><head></head><body>
    <div id="deck">
      ${withSlides ? `
      <section class="slide" id="slide-1"><h1 class="slide__display">One</h1><aside class="notes">Talk about one.</aside></section>
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
  // NO BroadcastChannel — simulate file:// opaque-origin restriction.
  // NO window.opener linkage — simulate popup opened in separate tab.
  // localStorage is shared by default in JSDOM (same storage per origin).
  return dom;
}

function loadScript(dom, path) {
  dom.window.eval(readFileSync(join(SHARED, path), 'utf8'));
}

console.log('Test: file:// simulation — localStorage transport only');
const deck = makeWindow({ url: 'http://localhost/deck.html', focused: true });
loadScript(deck, 'premium-controller.js');
await new Promise((r) => setTimeout(r, 0));
loadScript(deck, 'premium-timer.js');
const slideEngineJs = readFileSync(join(SHARED, 'slide-engine.js'), 'utf8');
deck.window.eval(slideEngineJs);
deck.window.eval('new SlideEngine();');
// Bridge must be installed before premium-presenter.js since it owns localStorage.
const popup = makeWindow({
  url: 'http://localhost/deck.html?presenter=1&session=PLACEHOLDER',
  focused: true,
  withSlides: false,
});
const sharedStorage = deck.window.localStorage;
const realSet = sharedStorage.setItem.bind(sharedStorage);
const realRemove = sharedStorage.removeItem.bind(sharedStorage);
const wrappedSet = function (key, value) {
  realSet(key, value);
  for (const target of [deck.window, popup.window]) {
    try {
      const ev = new target.Event('storage');
      ev.key = key;
      ev.newValue = value;
      ev.oldValue = null;
      ev.storageArea = sharedStorage;
      target.dispatchEvent(ev);
    } catch (_) {}
  }
};
const fakeStorage = {
  getItem: realSet.bind ? sharedStorage.getItem.bind(sharedStorage) : sharedStorage.getItem.bind(sharedStorage),
  setItem: wrappedSet,
  removeItem: realRemove,
  clear: sharedStorage.clear.bind(sharedStorage),
  key: sharedStorage.key.bind(sharedStorage),
  get length() { return sharedStorage.length; },
};
// Replace deck's setItem too via a Proxy-free approach: wrap sharedStorage
// methods in place. sharedStorage from JSDOM is a Storage; we cannot override
// its prototype methods safely. Instead, also define on deck.window.
const deckFakeStorage = {
  getItem: sharedStorage.getItem.bind(sharedStorage),
  setItem: wrappedSet,
  removeItem: realRemove,
  clear: sharedStorage.clear.bind(sharedStorage),
  key: sharedStorage.key.bind(sharedStorage),
  get length() { return sharedStorage.length; },
};
Object.defineProperty(deck.window, 'localStorage', { value: deckFakeStorage, configurable: true });
Object.defineProperty(popup.window, 'localStorage', { value: fakeStorage, configurable: true });
loadScript(deck, 'premium-presenter.js');
const deckSession = deck.window.document.documentElement.dataset.session;
console.log('  deck session:', deckSession);
// Re-set the popup URL with the real session id now that the deck has one.
popup.window.history.replaceState(null, '', 'http://localhost/deck.html?presenter=1&session=' + deckSession);
loadScript(popup, 'premium-controller.js');
await new Promise((r) => setTimeout(r, 0));
loadScript(popup, 'premium-presenter.js');

// Wait for the popup's presenter.ready (sent via localStorage) to reach deck
// and for the deck's replyWithSnapshot (also via localStorage) to come back.
await new Promise((r) => setTimeout(r, 300));

const list = popup.window.document.getElementById('pp-list');
if (!list) throw new Error('popup pp-list missing after handshake');
const items = list.querySelectorAll('li');
if (items.length !== 2) throw new Error('expected 2 rail items, got ' + items.length);
console.log('  PASS — popup received snapshot via localStorage');
console.log('  PASS — popup received snapshot via localStorage');

items[0].click();
await new Promise((r) => setTimeout(r, 200));

const state = deck.window.PremiumDeckControls.getState();
if (state.index !== 0) throw new Error('expected deck index=0 after popup click on first item, got ' + state.index);
console.log('  PASS — popup rail click drove deck via localStorage');

// Now jump to the second slide
items[1].click();
await new Promise((r) => setTimeout(r, 200));
const state2 = deck.window.PremiumDeckControls.getState();
if (state2.index !== 1) throw new Error('expected deck index=1 after popup click on second item, got ' + state2.index);
console.log('  PASS — popup rail click on second item drove deck to index 1');

process.exit(0);
