// Direct postMessage regression test. This simulates the file:// popup path
// where popup -> deck works through window.opener.postMessage, while
// BroadcastChannel/localStorage delivery is unavailable. The deck must retain
// MessageEvent.source so it can send slidechange/timer updates back.

import { loadScript, makeWindow as makeBaseWindow } from './_helpers.mjs';

const TWO_SLIDES_WITH_NOTES = `
      <section class="slide" id="slide-1"><h1 class="slide__display">One</h1><aside class="notes">Talk about one.</aside></section>
      <section class="slide" id="slide-2"><h1 class="slide__display">Two</h1><aside class="notes">Talk about two.</aside></section>
`;

function makeWindow(options) {
  // No BroadcastChannel — simulate the file:// opaque-origin restriction.
  return makeBaseWindow({ slides: TWO_SLIDES_WITH_NOTES, bc: 'none', ...options });
}

function connectDirectPostMessage(deck, popup) {
  const targets = { deck: [], popup: [] };
  deck.window.postMessage = function (data, targetOrigin) {
    targets.deck.push(targetOrigin);
    const ev = new deck.window.MessageEvent('message', {
      data,
      source: popup.window,
      origin: popup.window.location.origin,
    });
    deck.window.dispatchEvent(ev);
  };
  Object.defineProperty(popup.window, 'opener', {
    value: deck.window,
    configurable: true,
  });
  popup.window.postMessage = function (data, targetOrigin) {
    targets.popup.push(targetOrigin);
    const ev = new popup.window.MessageEvent('message', {
      data,
      source: deck.window,
      origin: deck.window.location.origin,
    });
    popup.window.dispatchEvent(ev);
  };
  return { deckPeer: deck.window, targets };
}

console.log('Test: direct window.opener postMessage transport');
const deck = makeWindow({ url: 'http://localhost/deck.html', focused: true, animationFrames: false });
loadScript(deck, 'premium-controller.js');
await new Promise((r) => setTimeout(r, 0));
loadScript(deck, 'premium-timer.js');
loadScript(deck, 'premium-controls.js');
loadScript(deck, 'slide-engine.js');
deck.window.eval('new SlideEngine();');
loadScript(deck, 'premium-presenter.js');

const deckSession = deck.window.document.documentElement.dataset.session;
const rogueReplies = [];
const rogueSource = {
  closed: false,
  opener: deck.window,
  location: { search: '?viewer=1' },
  postMessage(data) { rogueReplies.push(data); },
};
deck.window.dispatchEvent(new deck.window.MessageEvent('message', {
  data: { type: 'presenter.discover', popupSessionId: deckSession },
  source: rogueSource,
  origin: deck.window.location.origin,
}));
if (rogueReplies.length !== 0) {
  throw new Error('same-origin non-presenter source received deck adoption reply');
}
deck.window.dispatchEvent(new deck.window.MessageEvent('message', {
  data: {
    type: 'control', sessionId: deckSession, commandId: 'rogue-before-adoption',
    action: 'jump', index: 1,
  },
  source: rogueSource,
  origin: deck.window.location.origin,
}));
if (deck.window.PremiumDeckControls.getState().index !== 0) {
  throw new Error('same-origin non-presenter source gained control before adoption');
}
console.log('  PASS — same-origin non-presenter source cannot win initial adoption');

const popup = makeWindow({
  url: 'http://localhost/deck.html?presenter=1&session=' + deckSession,
  focused: true,
  withSlides: false,
});
const transport = connectDirectPostMessage(deck, popup);
loadScript(popup, 'premium-controller.js');
await new Promise((r) => setTimeout(r, 0));
loadScript(popup, 'premium-presenter.js');

await new Promise((r) => setTimeout(r, 100));

const list = popup.window.document.getElementById('pp-list');
if (!list) throw new Error('popup pp-list missing');
let items = list.querySelectorAll('li');
if (items.length !== 2) throw new Error('expected 2 rail items after direct snapshot, got ' + items.length);
console.log('  PASS — popup received initial snapshot via direct postMessage');

if (transport.targets.deck.some((target) => target !== deck.window.location.origin) ||
    transport.targets.popup.some((target) => target !== popup.window.location.origin)) {
  throw new Error('HTTP(S) direct postMessage must target location.origin, never wildcard');
}
console.log('  PASS — HTTP(S) direct postMessage uses an exact target origin');

function dispatchDeckMessage({ data, source = popup.window, origin = popup.window.location.origin }) {
  deck.window.dispatchEvent(new deck.window.MessageEvent('message', { data, source, origin }));
}

const beforeAttack = deck.window.PremiumDeckControls.getState().index;
dispatchDeckMessage({
  origin: 'https://evil.example',
  data: { type: 'control', sessionId: deckSession, commandId: 'evil-origin', action: 'jump', index: 1 },
});
if (deck.window.PremiumDeckControls.getState().index !== beforeAttack) {
  throw new Error('deck accepted a direct control message from a foreign origin');
}

const unexpectedSource = { postMessage() {}, closed: false };
dispatchDeckMessage({
  source: unexpectedSource,
  data: { type: 'control', sessionId: deckSession, commandId: 'evil-source', action: 'jump', index: 1 },
});
if (deck.window.PremiumDeckControls.getState().index !== beforeAttack) {
  throw new Error('deck accepted a direct control message from an unexpected source window');
}

dispatchDeckMessage({
  data: { type: 'control', commandId: 'missing-session', action: 'jump', index: 1 },
});
if (deck.window.PremiumDeckControls.getState().index !== beforeAttack) {
  throw new Error('deck accepted a sessionless direct control message');
}
console.log('  PASS — direct controls require exact origin, peer source, and session');

popup.window.dispatchEvent(new popup.window.MessageEvent('message', {
  origin: deck.window.location.origin,
  source: transport.deckPeer,
  data: {
    type: 'slidechange',
    sessionId: deckSession,
    index: 0,
    total: 2,
    notes: '<p onclick="window.__hit=1">Keep <strong>formatting</strong>.</p><img src=x onerror="window.__hit=1"><script>window.__hit=1</script><a href="javascript:window.__hit=1">bad</a><a href="https://example.com" target="_BLANK">safe</a>',
    bodyHtml: '',
  },
}));
const sanitizedNotes = popup.window.document.getElementById('pp-notes');
if (!sanitizedNotes.querySelector('strong') || !/Keep/.test(sanitizedNotes.textContent)) {
  throw new Error('safe authored note formatting was not preserved');
}
if (sanitizedNotes.querySelector('script, img') || /onerror|onclick|javascript:/i.test(sanitizedNotes.innerHTML)) {
  throw new Error('remote notes were rendered without sanitization: ' + sanitizedNotes.innerHTML);
}
const safeRemoteLink = sanitizedNotes.querySelector('a[href="https://example.com"]');
if (!safeRemoteLink || !/noopener/.test(safeRemoteLink.getAttribute('rel') || '')) {
  throw new Error('remote note link with _blank target did not receive noopener protection');
}
console.log('  PASS — remote note HTML is allowlist-sanitized before rendering');

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

// Timer settings live in #pp-timer-settings (hidden until gear opens it),
// but the inputs exist in DOM and can be queried directly.
const minutesInput = popup.window.document.getElementById('pp-minutes');
minutesInput.value = '5';
minutesInput.dispatchEvent(new popup.window.Event('input', { bubbles: true }));
await new Promise((r) => setTimeout(r, 500));

// #pp-timer-startstop is the toggle (Start / Pause); #pp-timer-reset is reset.
const startStopBtn = popup.window.document.getElementById('pp-timer-startstop');
startStopBtn.click();  // first click → Start
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

startStopBtn.click();  // second click → Pause (toggle)
await new Promise((r) => setTimeout(r, 150));
const pausedText = popup.window.document.getElementById('pp-timer-time').textContent;
await new Promise((r) => setTimeout(r, 1100));
const stillPausedText = popup.window.document.getElementById('pp-timer-time').textContent;
if (stillPausedText !== pausedText) {
  throw new Error('expected Pause to freeze popup timer at ' + pausedText + ', got ' + stillPausedText);
}
console.log('  PASS — Pause freezes presenter timer');

startStopBtn.click();  // third click → Start again
await new Promise((r) => setTimeout(r, 150));
const resetBtn = popup.window.document.getElementById('pp-timer-reset');
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

const reloadedSession = 'reloaded-session-id';
deck.window.document.documentElement.dataset.session = reloadedSession;
dispatchDeckMessage({
  data: { type: 'presenter.discover', popupSessionId: deckSession },
});
await new Promise((r) => setTimeout(r, 100));
if (popup.window.document.documentElement.dataset.session !== reloadedSession) {
  throw new Error('popup did not adopt the reloaded deck session');
}
console.log('  PASS — same-origin opener handshake re-adopts a reloaded deck session');

console.log('Test: file:// direct transport remains source/session-bound');
const fileDeck = makeWindow({ url: 'file:///tmp/deck.html', focused: true, animationFrames: false });
const fileSession = 'file-session-id';
let fileJumpIndex = 0;
fileDeck.window.document.documentElement.dataset.session = fileSession;
fileDeck.window.PremiumDeckControls = {
  getTitles: () => ['One', 'Two'],
  getState: () => ({ index: fileJumpIndex, total: 2 }),
  getNotes: (index) => index === 0 ? 'One note' : 'Two note',
  getSummary: () => '',
  goTo: (index) => { fileJumpIndex = index; },
  next: () => {},
  prev: () => {},
};
loadScript(fileDeck, 'premium-presenter.js');
const filePopup = makeWindow({
  url: 'file:///tmp/deck.html?presenter=1&session=' + fileSession,
  focused: true,
  withSlides: false,
});
const fileTransport = connectDirectPostMessage(fileDeck, filePopup);
filePopup.window.document.documentElement.dataset.session = fileSession;
loadScript(filePopup, 'premium-presenter.js');
await new Promise((r) => setTimeout(r, 100));
if (filePopup.window.document.querySelectorAll('#pp-list li').length !== 2) {
  throw new Error('file:// popup did not receive its direct snapshot');
}
if (fileTransport.targets.deck.some((target) => target !== '*') ||
    fileTransport.targets.popup.some((target) => target !== '*')) {
  throw new Error('file:// direct postMessage should use wildcard targetOrigin');
}
const fileBefore = fileJumpIndex;
fileDeck.window.dispatchEvent(new fileDeck.window.MessageEvent('message', {
  data: { type: 'control', commandId: 'file-missing-session', action: 'jump', index: 1 },
  source: filePopup.window,
  origin: 'null',
}));
if (fileJumpIndex !== fileBefore) {
  throw new Error('file:// deck accepted a sessionless direct control');
}
console.log('  PASS — file:// uses wildcard delivery but still requires peer source and session');

process.exit(0);
