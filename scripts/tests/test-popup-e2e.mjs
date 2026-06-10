// End-to-end presenter popup test: deck + popup with shared BroadcastChannel.
// Verifies: (1) sessionId alignment between deck and popup; (2) popup rail click
// delivers a jump control to the deck; (3) deck applies the jump and re-broadcasts
// snapshot; (4) popup notes panel updates.

import { FakeBC, installGlobalFakeBC, loadScript, makeWindow as makeBaseWindow } from './_helpers.mjs';

installGlobalFakeBC();

const FOUR_SLIDES = `
      <section class="slide" id="slide-1"><h1 class="slide__display">One</h1><aside class="notes">Talk about one.</aside></section>
      <section class="slide" id="slide-2"><h1 class="slide__display">Two</h1><aside class="notes">Talk about two.</aside></section>
      <section class="slide" id="slide-3"><h1 class="slide__display">Three</h1><aside class="notes">Talk about three.</aside></section>
      <section class="slide" id="slide-4"><h1 class="slide__display">Four</h1><div class="slide__body">
        <p>First sentence about four. Second sentence with detail. Third sentence that should be cut off.</p>
        <ul><li>Bullet one</li><li>Bullet two</li><li>Bullet three</li></ul>
      </div></section>
`;

function makeWindow(options) {
  // BroadcastChannel must be visible on the window, not just globalThis.
  return makeBaseWindow({ slides: FOUR_SLIDES, bc: FakeBC, ...options });
}

function fireLoaded(dom) {
  // JSDOM dispatches DOMContentLoaded automatically when parsing completes
  // (synchronously, before `new JSDOM()` returns for simple documents). The
  // controller's `if (readyState === 'loading')` branch registers a handler
  // that fires once, when parsing finishes.
  // We just wait a microtask to let JSDOM finish its parse + dispatch.
  return new Promise((r) => setTimeout(r, 0));
}

console.log('Test: popup rail click → deck jump');
const deck = makeWindow({ url: 'http://localhost/deck.html', focused: true });
loadScript(deck, 'premium-controller.js');
await fireLoaded(deck);
// Now load SlideEngine
loadScript(deck, 'slide-engine.js');
deck.window.eval('new SlideEngine();');
const D = deck.window.PremiumDeckControls;
if (!D) throw new Error('deck PremiumDeckControls missing');
const deckSession = deck.window.document.documentElement.dataset.session;
console.log('  deck session:', deckSession);

// Build popup window with the SAME sessionId
const popup = makeWindow({ url: 'http://localhost/deck.html?presenter=1&session=' + deckSession, focused: true, withSlides: false });
loadScript(popup, 'premium-controller.js');
await fireLoaded(popup);
const popupSession = popup.window.document.documentElement.dataset.session;
if (popupSession !== deckSession) throw new Error('SESSION MISMATCH: deck=' + deckSession + ' popup=' + popupSession);
console.log('  popup session:', popupSession, '(matches deck)');

// Load presenter module into both sides. Deck side must be loaded BEFORE the
// popup so the deck is ready to reply to the popup's `presenter.ready` with
// a snapshot — otherwise the popup would have to wait for the next event.
loadScript(deck, 'premium-presenter.js');
loadScript(popup, 'premium-presenter.js');

await new Promise((r) => setTimeout(r, 100));

// Verify popup received a snapshot with titles
const list = popup.window.document.getElementById('pp-list');
if (!list) throw new Error('popup pp-list missing');
const items = list.querySelectorAll('li');
if (items.length !== 4) throw new Error('expected 4 rail items, got ' + items.length);
const titles = [...items].map((li) => li.textContent);
if (!titles[0]) throw new Error('first item empty title');

// Click the second rail item (index 1) — should send jump(1) and jump to
// slide 2 (the "Two" slide) which has notes "Talk about two."
items[1].click();
await new Promise((r) => setTimeout(r, 100));

// Deck should now be on slide index 1 (the stubbed IntersectionObserver
// fires the callback synchronously on scrollIntoView, so this.current
// updates the same way it would in a real browser).
const state = D.getState();
if (state.index !== 1) throw new Error('expected deck index=1, got ' + state.index);

// Popup should reflect the new slide (slidechange broadcast)
const counter = popup.window.document.getElementById('pp-counter').textContent;
if (!/2\s*\/\s*4/.test(counter)) throw new Error('expected popup counter "2 / 4", got ' + counter);

// Notes panel should update — slide 2 has "Talk about two."
const notesHtml = popup.window.document.getElementById('pp-notes').innerHTML;
if (!/Talk about two/.test(notesHtml)) throw new Error('expected notes "Talk about two." in popup');

console.log('  PASS — popup rail click → deck jump + popup reflects new state');

console.log('Test: deck-side next() → popup notes refresh (slidechange path)');
// Now drive the deck from the DECK side (e.g. user pressing → on the deck
// window). This exercises the slidechange broadcast, not the snapshot
// replay that the first test relied on.
D.next();
await new Promise((r) => setTimeout(r, 100));

const state2 = D.getState();
if (state2.index !== 2) throw new Error('expected deck index=2 after next(), got ' + state2.index);

const counter2 = popup.window.document.getElementById('pp-counter').textContent;
if (!/3\s*\/\s*4/.test(counter2)) throw new Error('expected popup counter "3 / 4" after deck next(), got ' + counter2);

const notesHtml2 = popup.window.document.getElementById('pp-notes').innerHTML;
if (!/Talk about three/.test(notesHtml2)) throw new Error('expected notes "Talk about three." in popup after deck next(), got: ' + notesHtml2);

console.log('  PASS — deck next() broadcasts slidechange → popup notes update');

console.log('Test: slide without notes falls back to summary (lead + bullets, NOT full body)');
D.goTo(3);
await new Promise((r) => setTimeout(r, 100));

const state3 = D.getState();
if (state3.index !== 3) throw new Error('expected deck index=3, got ' + state3.index);

const notesHtml3 = popup.window.document.getElementById('pp-notes').innerHTML;
// Lead: first 2 sentences of first <p>
if (!/First sentence about four\. Second sentence with detail\./.test(notesHtml3)) {
  throw new Error('expected lead (2 sentences) in summary, got: ' + notesHtml3);
}
if (/Third sentence that should be cut off/.test(notesHtml3)) {
  throw new Error('summary should NOT include 3rd+ sentences, got: ' + notesHtml3);
}
// Bullets
if (!/<li>Bullet one<\/li>/.test(notesHtml3)) {
  throw new Error('expected bullets in summary, got: ' + notesHtml3);
}
if (!/<li>Bullet two<\/li>/.test(notesHtml3)) {
  throw new Error('expected bullet two in summary, got: ' + notesHtml3);
}
// No raw notes-aside
if (/<aside class="notes">/.test(notesHtml3)) {
  throw new Error('expected fallback to summary, not raw notes');
}

console.log('  PASS — popup shows lead + bullets summary (not full body)');

console.log('Test: deck-side jump via goTo() syncs popup counter + notes');
D.goTo(0);
await new Promise((r) => setTimeout(r, 100));

const state4 = D.getState();
if (state4.index !== 0) throw new Error('expected deck index=0, got ' + state4.index);

const counter4 = popup.window.document.getElementById('pp-counter').textContent;
if (!/1\s*\/\s*4/.test(counter4)) throw new Error('expected popup counter "1 / 4" after deck goTo(0), got ' + counter4);

const notesHtml4 = popup.window.document.getElementById('pp-notes').innerHTML;
if (!/Talk about one/.test(notesHtml4)) {
  throw new Error('expected notes "Talk about one." in popup after deck goTo(0), got: ' + notesHtml4);
}

console.log('  PASS — deck goTo() syncs popup counter + notes');

process.exit(0);
