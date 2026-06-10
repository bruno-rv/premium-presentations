// File:// transport regression test: simulates Chrome's file:// behavior by
// stripping BroadcastChannel and window.opener, leaving only the localStorage
// 'storage' event as a cross-window channel. Proves postToPeer still works.

import { loadScript, makeWindow } from './_helpers.mjs';

// NO BroadcastChannel install (JSDOM has none) — simulate file:// opaque-origin
// restriction. NO window.opener linkage — simulate popup opened in separate
// tab. localStorage is shared by default in JSDOM (same storage per origin).

console.log('Test: file:// simulation — localStorage transport only');
const deck = makeWindow({ url: 'http://localhost/deck.html', focused: true });
loadScript(deck, 'premium-controller.js');
await new Promise((r) => setTimeout(r, 0));
loadScript(deck, 'premium-timer.js');
loadScript(deck, 'slide-engine.js');
deck.window.eval('new SlideEngine();');
// Bridge must be installed before premium-presenter.js since it owns localStorage.
const popup = makeWindow({
  url: 'http://localhost/deck.html?presenter=1&session=PLACEHOLDER',
  focused: true,
  withSlides: false,
});
const sharedStorage = deck.window.localStorage;
const realRemove = sharedStorage.removeItem.bind(sharedStorage);
const realSet = sharedStorage.setItem.bind(sharedStorage);
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
// JSDOM's Storage prototype methods can't be overridden safely in place, so
// give each window a wrapper object whose setItem also dispatches the
// cross-window 'storage' event a real browser would fire.
function makeFakeStorage() {
  return {
    getItem: sharedStorage.getItem.bind(sharedStorage),
    setItem: wrappedSet,
    removeItem: realRemove,
    clear: sharedStorage.clear.bind(sharedStorage),
    key: sharedStorage.key.bind(sharedStorage),
    get length() { return sharedStorage.length; },
  };
}
Object.defineProperty(deck.window, 'localStorage', { value: makeFakeStorage(), configurable: true });
Object.defineProperty(popup.window, 'localStorage', { value: makeFakeStorage(), configurable: true });
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
