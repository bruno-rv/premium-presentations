// Direct postMessage regression test. This simulates the file:// popup path
// where popup -> deck works through window.opener.postMessage, while
// BroadcastChannel/localStorage delivery is unavailable. The deck must retain
// MessageEvent.source so it can send slidechange/timer updates back.

import { JSDOM } from 'jsdom';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHARED = join(__dirname, '..', 'assets', 'shared');

function loadScript(dom, path) {
  dom.window.eval(readFileSync(join(SHARED, path), 'utf8'));
}

function makeWindow({ url, withSlides = true, focused = true, animationFrames = true } = {}) {
  const html = `<!doctype html><html><head></head><body>
    <div id="deck">
      ${withSlides ? `
      <section class="slide" id="slide-1"><h1 class="slide__display">One</h1><aside class="notes">Talk about one.</aside></section>
      <section class="slide" id="slide-2"><h1 class="slide__display">Two</h1><aside class="notes">Talk about two.</aside></section>
      ` : ''}
    </div>
  </body></html>`;
  const dom = new JSDOM(html, {
    url,
    runScripts: 'outside-only',
    pretendToBeVisual: true,
  });
  if (!dom.window.crypto || !dom.window.crypto.randomUUID) {
    dom.window.crypto = dom.window.crypto || {};
    dom.window.crypto.randomUUID = () => 'sess-' + Math.random().toString(36).slice(2, 10);
  }
  Object.defineProperty(dom.window.document, 'hasFocus', { value: () => focused, configurable: true });
  dom.window.BroadcastChannel = undefined;
  dom.window.matchMedia = dom.window.matchMedia || (() => ({
    matches: false,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  const ioInstances = [];
  dom.window.IntersectionObserver = class {
    constructor(cb) { this.cb = cb; ioInstances.push(this); }
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  dom.window.HTMLElement.prototype.scrollIntoView = function () {
    for (const io of ioInstances) {
      try { io.cb([{ target: this, isIntersecting: true }]); } catch (_) {}
    }
  };
  dom.window.requestAnimationFrame = animationFrames ? ((cb) => setTimeout(cb, 0)) : (() => 0);
  dom.window.cancelAnimationFrame = (id) => clearTimeout(id);
  return dom;
}

function connectDirectPostMessage(deck, popup) {
  Object.defineProperty(popup.window, 'opener', {
    value: {
      closed: false,
      postMessage(data) {
        const ev = new deck.window.MessageEvent('message', {
          data,
          source: popup.window,
        });
        deck.window.dispatchEvent(ev);
      },
    },
    configurable: true,
  });
  popup.window.postMessage = function (data) {
    const ev = new popup.window.MessageEvent('message', {
      data,
      source: deck.window,
    });
    popup.window.dispatchEvent(ev);
  };
}

console.log('Test: direct window.opener postMessage transport');
const deck = makeWindow({ url: 'http://localhost/deck.html', focused: true, animationFrames: false });
loadScript(deck, 'premium-controller.js');
await new Promise((r) => setTimeout(r, 0));
loadScript(deck, 'premium-timer.js');
loadScript(deck, 'premium-controls.js');
deck.window.eval(readFileSync(join(SHARED, 'slide-engine.js'), 'utf8'));
deck.window.eval('new SlideEngine();');
loadScript(deck, 'premium-presenter.js');

const deckSession = deck.window.document.documentElement.dataset.session;
const popup = makeWindow({
  url: 'http://localhost/deck.html?presenter=1&session=' + deckSession,
  focused: true,
  withSlides: false,
});
connectDirectPostMessage(deck, popup);
loadScript(popup, 'premium-controller.js');
await new Promise((r) => setTimeout(r, 0));
loadScript(popup, 'premium-presenter.js');

await new Promise((r) => setTimeout(r, 100));

const list = popup.window.document.getElementById('pp-list');
if (!list) throw new Error('popup pp-list missing');
let items = list.querySelectorAll('li');
if (items.length !== 2) throw new Error('expected 2 rail items after direct snapshot, got ' + items.length);
console.log('  PASS — popup received initial snapshot via direct postMessage');

items[1].click();
await new Promise((r) => setTimeout(r, 100));

const deckState = deck.window.PremiumDeckControls.getState();
if (deckState.index !== 1) throw new Error('expected deck index=1, got ' + deckState.index);
const popupCounter = popup.window.document.getElementById('pp-counter').textContent;
if (!/2\s*\/\s*2/.test(popupCounter)) {
  throw new Error('expected popup counter "2 / 2" after rail click, got ' + popupCounter);
}
const notesHtml = popup.window.document.getElementById('pp-notes').innerHTML;
if (!/Talk about two/.test(notesHtml)) {
  throw new Error('expected popup notes for slide two, got ' + notesHtml);
}
console.log('  PASS — rail click updates deck and popup notes via direct postMessage');

const minutesInput = popup.window.document.getElementById('pp-minutes');
minutesInput.value = '5';
minutesInput.dispatchEvent(new popup.window.Event('input', { bubbles: true }));
await new Promise((r) => setTimeout(r, 500));

const startBtn = popup.window.document.getElementById('pp-start');
startBtn.click();
await new Promise((r) => setTimeout(r, 150));

const timerState = deck.window.PremiumTimer.getState();
if (!timerState.running) throw new Error('expected deck timer running after Start');
const timerText = popup.window.document.getElementById('pp-timer-time').textContent;
if (!/^5:\d{2}$/.test(timerText)) {
  throw new Error('expected popup timer display to reflect 5-minute running timer, got ' + timerText);
}
console.log('  PASS — Start updates popup timer via direct postMessage');

await new Promise((r) => setTimeout(r, 1250));
const tickingText = popup.window.document.getElementById('pp-timer-time').textContent;
if (tickingText === timerText || !/^4:5[89]$/.test(tickingText)) {
  throw new Error('expected popup timer to keep counting down without deck animation frames; started at ' + timerText + ', got ' + tickingText);
}
console.log('  PASS — presenter timer counts down locally when deck rAF is paused');

const pauseBtn = popup.window.document.getElementById('pp-pause');
pauseBtn.click();
await new Promise((r) => setTimeout(r, 150));
const pausedText = popup.window.document.getElementById('pp-timer-time').textContent;
await new Promise((r) => setTimeout(r, 1100));
const stillPausedText = popup.window.document.getElementById('pp-timer-time').textContent;
if (stillPausedText !== pausedText) {
  throw new Error('expected Pause to freeze popup timer at ' + pausedText + ', got ' + stillPausedText);
}
console.log('  PASS — Pause freezes presenter timer');

startBtn.click();
await new Promise((r) => setTimeout(r, 150));
const resetBtn = popup.window.document.getElementById('pp-reset');
resetBtn.click();
await new Promise((r) => setTimeout(r, 150));
const resetText = popup.window.document.getElementById('pp-timer-time').textContent;
if (resetText !== '5:00') {
  throw new Error('expected Reset to restore popup timer to 5:00, got ' + resetText);
}
console.log('  PASS — Reset restores presenter timer display');

deck.window.PremiumPresentations.setControlsHidden(true);
popup.window.document.documentElement.dataset.controller = 'none';
const beforeHidden = deck.window.document.documentElement.dataset.controlsHidden || 'off';
popup.window.document.dispatchEvent(new popup.window.KeyboardEvent('keydown', {
  key: 'h',
  code: 'KeyH',
  bubbles: true,
}));
await new Promise((r) => setTimeout(r, 100));
const afterHidden = deck.window.document.documentElement.dataset.controlsHidden || 'off';
if (beforeHidden !== 'on' || afterHidden !== 'off') {
  throw new Error('expected popup H shortcut to reopen deck controls after focus churn, before=' + beforeHidden + ' after=' + afterHidden);
}
const shell = deck.window.document.querySelector('.premium-controls-shell');
if (!shell || !shell.classList.contains('is-open') || shell.classList.contains('is-hidden')) {
  throw new Error('expected popup H shortcut to show the deck controls menu');
}
console.log('  PASS — popup H shortcut shows deck controls after focus churn');

popup.window.document.documentElement.dataset.controller = 'none';
const beforeParallax = deck.window.document.documentElement.dataset.parallax || 'off';
popup.window.document.dispatchEvent(new popup.window.KeyboardEvent('keydown', {
  key: '3',
  code: 'Digit3',
  bubbles: true,
}));
await new Promise((r) => setTimeout(r, 100));
const afterParallax = deck.window.document.documentElement.dataset.parallax || 'off';
if (beforeParallax === afterParallax || afterParallax !== 'on') {
  throw new Error('expected popup 3 shortcut to toggle deck parallax on after focus churn, before=' + beforeParallax + ' after=' + afterParallax);
}
console.log('  PASS — popup 3 shortcut toggles deck parallax after focus churn');

process.exit(0);
