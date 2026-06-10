// BC transport regression test: validates that popup rail click drives the
// deck AND deck slidechange updates the popup, using BroadcastChannel only
// (no localStorage, no window.opener). Complements test-popup-storage.mjs
// which tests the localStorage transport.

import { installWindowRouterBC, loadScript, makeWindow as makeBaseWindow } from './_helpers.mjs';

// Window-scoped BroadcastChannel router shared by all windows in this test.
const windows = [];
function makeWindow(options) {
  const dom = makeBaseWindow(options);
  installWindowRouterBC(dom.window, windows);
  windows.push(dom.window);
  return dom;
}

console.log('Test: BroadcastChannel transport only');
const deck = makeWindow({ url: 'http://localhost/deck.html', focused: true });
loadScript(deck, 'premium-controller.js');
loadScript(deck, 'premium-timer.js');
loadScript(deck, 'slide-engine.js');
deck.window.eval('new SlideEngine();');

const popup = makeWindow({
  url: 'http://localhost/deck.html?presenter=1&session=PLACEHOLDER',
  focused: true,
  withSlides: false,
});
loadScript(popup, 'premium-controller.js');
loadScript(popup, 'premium-presenter.js');
const deckSession = deck.window.document.documentElement.dataset.session;
console.log('  deck session:', deckSession);
popup.window.history.replaceState(null, '', 'http://localhost/deck.html?presenter=1&session=' + deckSession);

loadScript(deck, 'premium-presenter.js');

// Wait for handshake
await new Promise((r) => setTimeout(r, 300));

const list = popup.window.document.getElementById('pp-list');
if (!list) throw new Error('popup pp-list missing after handshake');
const items = list.querySelectorAll('li');
if (items.length !== 2) throw new Error('expected 2 rail items, got ' + items.length);
console.log('  PASS — popup received snapshot via BroadcastChannel');

// Test popup→deck: rail click drives deck
items[0].click();
await new Promise((r) => setTimeout(r, 200));
const state = deck.window.PremiumDeckControls.getState();
if (state.index !== 0) throw new Error('expected deck index=0 after popup click on first item, got ' + state.index);
console.log('  PASS — popup rail click drove deck via BC (item 0)');

items[1].click();
await new Promise((r) => setTimeout(r, 200));
const state2 = deck.window.PremiumDeckControls.getState();
if (state2.index !== 1) throw new Error('expected deck index=1 after popup click on second item, got ' + state2.index);
console.log('  PASS — popup rail click drove deck via BC (item 1)');

// Test deck→popup: trigger deck slidechange and verify popup receives
deck.window.PremiumDeckControls.goTo(0);
await new Promise((r) => setTimeout(r, 200));
const counter = popup.window.document.getElementById('pp-counter');
const counterText = counter ? counter.textContent : '(no counter)';
console.log('  popup counter after deck.goTo(0):', counterText);
if (!counterText.startsWith('1 /')) throw new Error('popup did not receive slidechange from deck; counter=' + counterText);
console.log('  PASS — deck slidechange drove popup counter via BC');

process.exit(0);
