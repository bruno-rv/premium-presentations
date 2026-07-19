// PLAN.md Workstream B (v2.1.0) — timed teleprompter scroll. Covers the
// engage rule (step 7), the epoch-based progress model incl. mid-slide
// multiplier rebase continuity and slide-change re-epoching (step 8/9),
// pause->resume position continuity (step 9), speed-key clamp bounds (step
// 10), and the localStorage v2 schema + legacy-string migration (step 11).
// Manual-mode (budgetless deck) coverage lives in teleprompter.test.mjs —
// this file only adds/changes behavior for budgeted decks, per the engage
// rule ("otherwise today's manual constant px/s, untouched").

import assert from 'node:assert/strict';
import test from 'node:test';

import { FakeBC, installGlobalFakeBC, loadScript, makeWindow as makeBaseWindow } from './_helpers.mjs';

installGlobalFakeBC();

const BUDGETED_SLIDES = `
      <section class="slide" id="slide-1" data-budget="2000"><h1 class="slide__display">One</h1><aside class="notes">One.</aside></section>
      <section class="slide" id="slide-2" data-budget="4000"><h1 class="slide__display">Two</h1><aside class="notes">Two.</aside></section>
`;

const INVALID_PARTIAL_SLIDES = `
      <section class="slide" id="slide-1" data-budget="2000"><h1 class="slide__display">One</h1><aside class="notes">One.</aside></section>
      <section class="slide" id="slide-2"><h1 class="slide__display">Two</h1><aside class="notes">Two.</aside></section>
`;

const DECK_SLIDES = `
      <section class="slide" id="slide-1"><h1 class="slide__display">One</h1><aside class="notes">One.</aside></section>
      <section class="slide" id="slide-2"><h1 class="slide__display">Two</h1><aside class="notes">Two.</aside></section>
`;

function makeWindow(options) {
  return makeBaseWindow({ bc: FakeBC, ...options });
}

function tick(ms = 20) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function pressKey(win, key, code) {
  const ev = new win.KeyboardEvent('keydown', { key, code: code || key, bubbles: true, cancelable: true });
  win.document.dispatchEvent(ev);
}

async function setupPresenterPair({ popupSlides = DECK_SLIDES, seedTeleprompter } = {}) {
  FakeBC.channels = new Map();

  const deck = makeWindow({ url: 'http://localhost/deck.html', slides: DECK_SLIDES, focused: true });
  loadScript(deck, 'premium-controller.js');
  await tick(0);
  loadScript(deck, 'slide-engine.js');
  deck.window.eval('new SlideEngine();');
  const deckControls = deck.window.PremiumDeckControls;
  loadScript(deck, 'premium-timer.js');
  loadScript(deck, 'premium-presenter.js');
  const deckSession = deck.window.document.documentElement.dataset.session;

  const popup = makeWindow({
    url: 'http://localhost/deck.html?presenter=1&session=' + deckSession,
    focused: true,
    withSlides: true,
    slides: popupSlides,
  });

  if (seedTeleprompter !== undefined) {
    popup.window.localStorage.setItem('premium-teleprompter', seedTeleprompter);
  }

  // Deterministic clock: real setInterval/TP_TICK_MS still drives repaint
  // (per contract, "interval/rAF may drive repaint, but position derives
  // from performance.now()"), but every read of performance.now() inside
  // the popup returns this stubbed value until setNow() changes it.
  let nowMs = 0;
  popup.window.performance.now = () => nowMs;

  loadScript(popup, 'premium-controller.js');
  await tick(0);
  loadScript(popup, 'premium-presenter.js');
  await tick(100);

  const notes = popup.window.document.getElementById('pp-notes');

  return {
    deck,
    popup,
    deckControls,
    notes,
    setNow(ms) { nowMs = ms; },
    setNotesLayout(scrollHeight, clientHeight) {
      Object.defineProperty(notes, 'scrollHeight', { value: scrollHeight, configurable: true });
      Object.defineProperty(notes, 'clientHeight', { value: clientHeight, configurable: true });
    },
  };
}

test('engage rule — a complete valid budget vector engages timed scroll', async (t) => {
  const { deck, popup } = await setupPresenterPair({ popupSlides: BUDGETED_SLIDES });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(1);
  await tick(50);

  assert.equal(popup.window.PremiumPresenterView.getTeleprompterState().timedEngaged, true);
});

test('engage-rule fallback — an incomplete/invalid vector keeps manual constant px/s untouched', async (t) => {
  const { deck, popup, setNow, setNotesLayout, notes } = await setupPresenterPair({ popupSlides: INVALID_PARTIAL_SLIDES });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(1);
  await tick(50);

  assert.equal(popup.window.PremiumPresenterView.getTeleprompterState().timedEngaged, false,
    'atomic fallback: partial vector must not engage timed scroll');

  setNotesLayout(1000, 200);
  setNow(0);
  pressKey(popup.window, 'p');
  await tick(120);
  // Manual mode: scrollTop grows by rate*(tick/1000) every real tick, wholly
  // independent of performance.now() — assert only that it moved forward
  // (unaffected by the stubbed clock, proving the manual path is untouched).
  assert.ok(notes.scrollTop > 0, 'manual scroll still advances via wall-clock ticks, not performance.now()');
});

test('budgetless deck — no data-budget anywhere keeps manual scroll (engage rule negative case)', async (t) => {
  const { deck, popup } = await setupPresenterPair({ popupSlides: DECK_SLIDES });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(1);
  await tick(50);

  assert.equal(popup.window.PremiumPresenterView.getTeleprompterState().timedEngaged, false);
});

test('progress model — scrollTop = progress * (scrollHeight - clientHeight) at multiplier x1.0', async (t) => {
  const { deck, popup, setNow, setNotesLayout, notes } = await setupPresenterPair({ popupSlides: BUDGETED_SLIDES });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(1);
  await tick(50);

  setNotesLayout(1000, 200); // distance = 800
  setNow(0);
  pressKey(popup.window, 'p');
  setNow(1000); // slide-1 budget = 2000ms -> progress = 1000/2000 = 0.5
  await tick(120);

  assert.equal(notes.scrollTop, 400, 'progress 0.5 * distance 800 = 400');
});

test('mid-slide multiplier rebase — no jump at the moment of change, new rate applies going forward', async (t) => {
  const { deck, popup, setNow, setNotesLayout, notes } = await setupPresenterPair({ popupSlides: BUDGETED_SLIDES });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(1);
  await tick(50);

  setNotesLayout(1000, 200); // distance = 800
  setNow(0);
  pressKey(popup.window, 'p');
  setNow(1000); // progress = 1000/2000 = 0.5
  await tick(120);
  assert.equal(notes.scrollTop, 400);

  // Multiplier nudge at the SAME instant (clock unchanged): commit progress
  // under the OLD multiplier (0.5, exact), rebase epoch to now. No new
  // elapsed time has passed yet, so the very next tick must reproduce the
  // identical position — this is the "no jump" contract.
  pressKey(popup.window, ']', 'BracketRight'); // multiplierTenths 10 -> 11 (x1.1)
  await tick(120);
  assert.equal(notes.scrollTop, 400, 'position is continuous across a multiplier change (no jump)');

  const state = popup.window.PremiumPresenterView.getTeleprompterState();
  assert.equal(state.multiplierTenths, 11);

  // Advance 400ms post-rebase at the NEW x1.1 multiplier:
  // progress = 0.5 + 400*1.1/2000 = 0.72 -> scrollTop = 576 (not 560, which
  // is what the OLD x1.0 multiplier would have produced).
  setNow(1400);
  await tick(120);
  assert.equal(notes.scrollTop, 576, 'the new multiplier applies only to time elapsed after the rebase');
});

test('pause -> resume — position continuity: no restart, no backward jump', async (t) => {
  const { deck, popup, setNow, setNotesLayout, notes } = await setupPresenterPair({ popupSlides: BUDGETED_SLIDES });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(1);
  await tick(50);

  setNotesLayout(1000, 200); // distance = 800
  setNow(0);
  pressKey(popup.window, 'p');
  setNow(600); // progress = 600/2000 = 0.3
  await tick(120);
  assert.equal(notes.scrollTop, 240);

  pressKey(popup.window, 'p'); // pause — commits accumulatedProgress=0.3, clears epoch
  let state = popup.window.PremiumPresenterView.getTeleprompterState();
  assert.equal(state.scrolling, false);
  assert.equal(state.accumulatedProgress, 0.3);

  // Time moving on while paused must not move the position (no timer is
  // running — clearInterval on pause — so no tick can fire regardless of
  // the clock).
  setNow(5000);
  await tick(120);
  assert.equal(notes.scrollTop, 240, 'position holds while paused, even as the clock advances');

  pressKey(popup.window, 'p'); // resume — keeps accumulatedProgress, fresh epoch at now=5000
  state = popup.window.PremiumPresenterView.getTeleprompterState();
  assert.equal(state.scrolling, true);
  assert.equal(state.accumulatedProgress, 0.3, 'resume keeps accumulatedProgress — no restart to 0');

  setNow(5400); // 400ms after resume -> progress = 0.3 + 400/2000 = 0.5
  await tick(120);
  assert.equal(notes.scrollTop, 400, 'resume continues forward from the paused position, no backward jump');
});

test('slide change — zeroes accumulatedProgress and re-epochs while playing, no new keypress needed', async (t) => {
  const { deck, popup, deckControls, setNow, setNotesLayout, notes } = await setupPresenterPair({ popupSlides: BUDGETED_SLIDES });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(1);
  await tick(50);

  setNotesLayout(1000, 200); // distance = 800
  setNow(0);
  pressKey(popup.window, 'p');
  setNow(1000); // slide-1 (budget 2000ms): progress = 0.5
  await tick(120);
  assert.equal(notes.scrollTop, 400);

  deckControls.goTo(1); // slide-2, budget 4000ms
  await tick(80);
  assert.equal(notes.scrollTop, 0, 'slide change zeroes accumulatedProgress with no elapsed time yet');

  const state = popup.window.PremiumPresenterView.getTeleprompterState();
  assert.equal(state.scrolling, true, 'motion continues without a new p keypress');

  setNow(1800); // 800ms after the slide change, at slide-2's 4000ms budget -> progress = 0.2
  await tick(120);
  assert.equal(notes.scrollTop, 160, 'the NEW slide budget (4000ms) governs post-change progress');
});

test('no-overflow guard — notes that do not overflow never move, but play intent stays on', async (t) => {
  const { deck, popup, setNow, setNotesLayout, notes } = await setupPresenterPair({ popupSlides: BUDGETED_SLIDES });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(1);
  await tick(50);

  setNotesLayout(200, 200); // distance = 0 — no overflow
  setNow(0);
  pressKey(popup.window, 'p');
  setNow(5000);
  await tick(120);

  assert.equal(notes.scrollTop, 0, 'no overflow -> no motion, no division');
  assert.equal(popup.window.PremiumPresenterView.getTeleprompterState().scrolling, true,
    'play intent stays on even though there is nothing to scroll');
});

test('clamp bounds — multiplierTenths clamps to [5,20]; manual rate clamps to [10,240]', async (t) => {
  const budgeted = await setupPresenterPair({ popupSlides: BUDGETED_SLIDES });
  budgeted.deck.window.PremiumTimer.setMinutes(1);
  await tick(50);
  for (let i = 0; i < 20; i++) pressKey(budgeted.popup.window, ']', 'BracketRight');
  assert.equal(budgeted.popup.window.PremiumPresenterView.getTeleprompterState().multiplierTenths, 20);
  for (let i = 0; i < 30; i++) pressKey(budgeted.popup.window, '[', 'BracketLeft');
  assert.equal(budgeted.popup.window.PremiumPresenterView.getTeleprompterState().multiplierTenths, 5);
  budgeted.deck.window.close(); budgeted.popup.window.close();

  const manual = await setupPresenterPair({ popupSlides: DECK_SLIDES });
  manual.deck.window.PremiumTimer.setMinutes(1);
  await tick(50);
  for (let i = 0; i < 40; i++) pressKey(manual.popup.window, ']', 'BracketRight');
  assert.equal(manual.popup.window.PremiumPresenterView.getTeleprompterState().rate, 240);
  for (let i = 0; i < 40; i++) pressKey(manual.popup.window, '[', 'BracketLeft');
  assert.equal(manual.popup.window.PremiumPresenterView.getTeleprompterState().rate, 10);
  manual.deck.window.close(); manual.popup.window.close();
});

test('storage migration — legacy plain-numeric string is read as manualRate and migrated to v2 on first write', async (t) => {
  const { deck, popup } = await setupPresenterPair({ popupSlides: DECK_SLIDES, seedTeleprompter: '75' });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(1);
  await tick(50);

  let state = popup.window.PremiumPresenterView.getTeleprompterState();
  assert.equal(state.rate, 75, 'legacy numeric string is read as the manual rate');
  assert.equal(popup.window.localStorage.getItem('premium-teleprompter'), '75',
    'reading alone must not rewrite storage — migration happens on first write');

  pressKey(popup.window, ']', 'BracketRight'); // first write -> migrates to v2
  const persisted = JSON.parse(popup.window.localStorage.getItem('premium-teleprompter'));
  assert.deepEqual(persisted, { v: 2, manualRate: 85, multiplierTenths: 10 },
    'saved rate survives the migration (75 + RATE_STEP 10 = 85)');
});

test('storage v2 round-trip — manualRate and multiplierTenths both survive a reload', async (t) => {
  const seeded = JSON.stringify({ v: 2, manualRate: 120, multiplierTenths: 15 });
  const { deck, popup } = await setupPresenterPair({ popupSlides: DECK_SLIDES, seedTeleprompter: seeded });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(1);
  await tick(50);

  const state = popup.window.PremiumPresenterView.getTeleprompterState();
  assert.equal(state.rate, 120);
  assert.equal(state.multiplierTenths, 15);
});

test('corrupt storage payload — malformed JSON degrades to defaults without throwing', async (t) => {
  const { deck, popup } = await setupPresenterPair({ popupSlides: DECK_SLIDES, seedTeleprompter: '{not json' });
  t.after(() => { deck.window.close(); popup.window.close(); });

  const errors = [];
  popup.window.addEventListener('error', (e) => errors.push(e.error || e.message));
  deck.window.PremiumTimer.setMinutes(1);
  await tick(50);

  assert.deepEqual(errors, []);
  const state = popup.window.PremiumPresenterView.getTeleprompterState();
  assert.equal(state.rate, 40, 'falls back to the default manual rate');
  assert.equal(state.multiplierTenths, 10, 'falls back to the default multiplier');
});
