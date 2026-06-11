// Test that timer controls in the popup drive the deck's PremiumTimer.
// Reproduces: popup loads, user clicks Start, deck's timer should start.

import { FakeBC, installGlobalFakeBC, loadScript, makeWindow as makeBaseWindow } from './_helpers.mjs';

installGlobalFakeBC();

function makeWindow(options) {
  return makeBaseWindow({ bc: FakeBC, ...options });
}

console.log('Test: popup Start button → deck timer starts');
const deck = makeWindow({ url: 'http://localhost/deck.html', focused: false });
loadScript(deck, 'premium-controller.js');
await new Promise((r) => setTimeout(r, 0));
loadScript(deck, 'premium-timer.js');
loadScript(deck, 'slide-engine.js');
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

// Verify popup built with controls.
// Timer bar has #pp-timer-startstop (toggle) and #pp-timer-reset.
// Settings panel has #pp-minutes (hidden in #pp-timer-settings until gear opens it,
// but exists in DOM and can be queried directly).
const startStopBtn = popup.window.document.getElementById('pp-timer-startstop');
if (!startStopBtn) throw new Error('pp-timer-startstop missing');
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

// User clicks Start (first click = Start on the startstop toggle).
startStopBtn.click();
await new Promise((r) => setTimeout(r, 100));

const state = PT.getState();
console.log('  deck PremiumTimer after Start click:', JSON.stringify(state));
if (!state.running) {
  throw new Error('expected deck timer running, got ' + JSON.stringify(state));
}

console.log('  PASS — popup Start button drives deck timer');

console.log('Test: popup Pause button stops deck timer');
// Second click on the toggle = Pause.
startStopBtn.click();
await new Promise((r) => setTimeout(r, 100));

const state2 = PT.getState();
console.log('  deck PremiumTimer after Pause click:', JSON.stringify(state2));
if (state2.running) {
  throw new Error('expected deck timer NOT running, got running');
}

console.log('  PASS — popup Pause button stops deck timer');

console.log('Test: popup Reset button stops + resets deck timer');
// Third click = Start again so we have non-zero elapsed.
startStopBtn.click();
await new Promise((r) => setTimeout(r, 200));
const resetBtn = popup.window.document.getElementById('pp-timer-reset');
resetBtn.click();
await new Promise((r) => setTimeout(r, 100));

const state3 = PT.getState();
console.log('  deck PremiumTimer after Reset click:', JSON.stringify(state3));
if (state3.running) throw new Error('expected deck timer not running after reset, got running');
if (state3.elapsedMs > 1000) throw new Error('expected elapsedMs near 0 after reset, got ' + state3.elapsedMs);

console.log('  PASS — popup Reset button stops + resets deck timer');

process.exit(0);
