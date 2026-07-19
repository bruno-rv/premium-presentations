// Slide Budget runtime — readSlideBudgets() acceptance/atomic-fallback, the
// centralized planned-time/comparison-label helper ("vs plan"/"vs average"),
// and the suggested-budget export (ID-keyed, sample-eligibility refusal,
// legacy ordinal+title fallback). PLAN.md Workstream A steps 4/5.

import assert from 'node:assert/strict';
import test from 'node:test';

import { FakeBC, installGlobalFakeBC, loadScript, makeWindow as makeBaseWindow } from './_helpers.mjs';

installGlobalFakeBC();

const BUDGETED_SLIDES = `
      <section class="slide" id="slide-1" data-budget="50000"><h1 class="slide__display">Opening</h1><aside class="notes">One.</aside></section>
      <section class="slide" id="slide-2" data-budget="70000"><h1 class="slide__display">Problem framing</h1><aside class="notes">Two.</aside></section>
`;

const INVALID_PARTIAL_SLIDES = `
      <section class="slide" id="slide-1" data-budget="50000"><h1 class="slide__display">Opening</h1><aside class="notes">One.</aside></section>
      <section class="slide" id="slide-2"><h1 class="slide__display">Problem framing</h1><aside class="notes">Two.</aside></section>
`;

const LEGACY_SLIDES = `
      <section class="slide"><h1 class="slide__display">Opening</h1><aside class="notes">One.</aside></section>
      <section class="slide"><h1 class="slide__display">Problem framing</h1><aside class="notes">Two.</aside></section>
`;

const DECK_SLIDES = `
      <section class="slide" id="slide-1"><h1 class="slide__display">Opening</h1><aside class="notes">One.</aside></section>
      <section class="slide" id="slide-2"><h1 class="slide__display">Problem framing</h1><aside class="notes">Two.</aside></section>
`;

const REHEARSAL_KEY = 'premium-rehearsal:/deck.html';

function makeWindow(options) {
  return makeBaseWindow({ bc: FakeBC, ...options });
}

function tick(ms = 20) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function setupPresenterPair({ popupSlides = DECK_SLIDES, seedRehearsal, now = 1_700_000_000_000 } = {}) {
  FakeBC.channels = new Map();

  const deck = makeWindow({ url: 'http://localhost/deck.html', slides: DECK_SLIDES, focused: true });
  loadScript(deck, 'premium-controller.js');
  await tick(0);
  loadScript(deck, 'slide-engine.js');
  deck.window.eval('new SlideEngine();');
  const deckControls = deck.window.PremiumDeckControls;
  assert.ok(deckControls, 'deck controls should be available');

  loadScript(deck, 'premium-timer.js');
  loadScript(deck, 'premium-presenter.js');
  const deckSession = deck.window.document.documentElement.dataset.session;

  const popup = makeWindow({
    url: 'http://localhost/deck.html?presenter=1&session=' + deckSession,
    focused: true,
    withSlides: true,
    slides: popupSlides,
  });
  popup.window.Date.now = () => now;

  if (seedRehearsal) {
    popup.window.localStorage.setItem(REHEARSAL_KEY, JSON.stringify(seedRehearsal));
  }

  loadScript(popup, 'premium-controller.js');
  await tick(0);
  loadScript(popup, 'premium-presenter.js');
  await tick(100);

  return {
    deck,
    popup,
    deckControls,
    advance(ms) {
      now += ms;
      popup.window.Date.now = () => now;
    },
  };
}

test('readSlideBudgets() accepts a complete valid vector and labels "vs plan"', async (t) => {
  const { deck, popup } = await setupPresenterPair({ popupSlides: BUDGETED_SLIDES });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(2);
  await tick(50);

  const result = popup.window.PremiumPresenterView.readSlideBudgets();
  assert.deepEqual([...result.vector], [50000, 70000]);
  assert.deepEqual([...result.ids], ['slide-1', 'slide-2']);
  assert.equal(popup.window.PremiumPresenterView.getComparisonLabel(), 'vs plan');
  assert.equal(popup.window.PremiumPresenterView.getPlannedTimeFor(0), 50000);
  assert.equal(popup.window.PremiumPresenterView.getPlannedTimeFor(1), 70000);
});

test('readSlideBudgets() atomically falls back to vs-average on an incomplete vector, with exactly one diagnostic', async (t) => {
  // Patch console.warn BEFORE setup: the very first renderTimeline() (fired
  // by the popup's initial snapshot reply) is what memoizes budgetPlan() and
  // fires the one diagnostic — later render ticks must not re-warn.
  const warnings = [];
  const originalWarn = console.warn;
  console.warn = (...args) => warnings.push(args.join(' '));
  let deck, popup, deckControls;
  try {
    ({ deck, popup, deckControls } = await setupPresenterPair({ popupSlides: INVALID_PARTIAL_SLIDES }));
    deck.window.PremiumTimer.setMinutes(2);
    await tick(50);
    deckControls.goTo(1);        // multiple renderTimeline ticks — should still warn only once
    await tick(50);
    deckControls.goTo(0);
    await tick(50);
  } finally {
    console.warn = originalWarn;
  }
  t.after(() => { deck.window.close(); popup.window.close(); });

  const diagnostics = warnings.filter((w) => w.includes('readSlideBudgets'));
  assert.equal(diagnostics.length, 1, 'exactly one console diagnostic despite multiple render ticks');
  assert.equal(popup.window.PremiumPresenterView.getComparisonLabel(), 'vs average');
});

test('budgetless deck (no data-budget anywhere) falls back silently — no diagnostic', async (t) => {
  const { deck, popup, deckControls } = await setupPresenterPair({ popupSlides: DECK_SLIDES });
  t.after(() => { deck.window.close(); popup.window.close(); });

  const warnings = [];
  const originalWarn = console.warn;
  console.warn = (...args) => warnings.push(args.join(' '));
  try {
    deck.window.PremiumTimer.setMinutes(2);
    await tick(50);
    deckControls.goTo(1);
    await tick(50);
  } finally {
    console.warn = originalWarn;
  }

  assert.equal(warnings.filter((w) => w.includes('readSlideBudgets')).length, 0, 'budgetless is expected, not an error');
  assert.equal(popup.window.PremiumPresenterView.getComparisonLabel(), 'vs average');
});

test('timeline deltas render "vs plan" for a budgeted deck', async (t) => {
  const { deck, popup, deckControls, advance } = await setupPresenterPair({ popupSlides: BUDGETED_SLIDES });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(2);
  await tick(50);

  const toggle = popup.window.document.getElementById('pp-rehearsal-toggle');
  toggle.click();                 // start on slide-1 (planned 50000ms)
  advance(60_000);                // 60s actual vs 50s planned -> +10s delta
  deckControls.goTo(1);
  await tick(50);
  toggle.click();                 // pause

  const deltaSpans = [...popup.window.document.querySelectorAll('#pp-timeline .pp-timeline__delta')];
  assert.match(deltaSpans[0].textContent, /vs plan/);
  assert.doesNotMatch(deltaSpans[0].textContent, /vs average/);
});

test('suggested-budget export refuses when a slide lacks an in-range observation, naming it by ID', async (t) => {
  const fixture = {
    version: 1,
    slideCount: 2,
    runs: [
      { ts: 1, totalMs: 60000, slideMs: [50000, 0] },     // slide-2 never visited (0ms)
      { ts: 2, totalMs: 60000, slideMs: [52000, 500] },   // slide-2 sub-second, still out of range
    ],
  };
  const { deck, popup } = await setupPresenterPair({ popupSlides: BUDGETED_SLIDES, seedRehearsal: fixture });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(2);
  await tick(100);

  const result = popup.window.PremiumPresenterView.getSuggestedBudgetExport();
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'insufficient_samples');
  assert.match(result.message, /slide-2/);
  assert.equal(popup.window.document.getElementById('pp-budget-block').dataset.empty, 'true');
});

test('suggested-budget export succeeds ID-keyed when every slide has an eligible observation', async (t) => {
  const fixture = {
    version: 1,
    slideCount: 2,
    runs: [{ ts: 1, totalMs: 120000, slideMs: [50000, 70000] }],
  };
  const { deck, popup } = await setupPresenterPair({ popupSlides: BUDGETED_SLIDES, seedRehearsal: fixture });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(2);
  await tick(100);

  const result = popup.window.PremiumPresenterView.getSuggestedBudgetExport();
  assert.equal(result.ok, true);
  assert.equal(result.identityMode, 'id');
  // Cross-realm arrays: normalize into this module's realm via spread before
  // assert.deepEqual (strict) — see AT1 comment in rehearsal-persistence.test.mjs.
  assert.deepEqual([...result.rows.map((r) => r.id)], ['slide-1', 'slide-2']);

  const md = popup.window.document.querySelector('#pp-budget-block pre').textContent;
  assert.match(md, /\| ID \| Budget \(mm:ss\) \| Budget \(ms\) \|/);
  assert.match(md, /\| slide-1 \| 00:50 \| 50000 \|/);

  const payload = JSON.parse(popup.window.PremiumPresenterView.exportRehearsalJson());
  assert.equal(payload.v, 2);
  assert.equal(payload.identity, 'id');
  assert.deepEqual(payload.rows[0], { id: 'slide-1', mmss: '00:50', ms: 50000 });
});

test('suggested-budget export falls back to ordinal+title with a stable-ID notice on legacy decks', async (t) => {
  const fixture = {
    version: 1,
    slideCount: 2,
    runs: [{ ts: 1, totalMs: 120000, slideMs: [50000, 70000] }],
  };
  const { deck, popup } = await setupPresenterPair({ popupSlides: LEGACY_SLIDES, seedRehearsal: fixture });
  t.after(() => { deck.window.close(); popup.window.close(); });
  deck.window.PremiumTimer.setMinutes(2);
  await tick(100);

  const result = popup.window.PremiumPresenterView.getSuggestedBudgetExport();
  assert.equal(result.ok, true);
  assert.equal(result.identityMode, 'ordinal');
  assert.equal(result.rows[0].id, null);

  const md = popup.window.document.querySelector('#pp-budget-block pre').textContent;
  assert.match(md, /\| # \| Title \| Budget \(mm:ss\) \| Budget \(ms\) \|/);
  assert.match(md, /initialize stable IDs before merging/);

  const payload = JSON.parse(popup.window.PremiumPresenterView.exportRehearsalJson());
  assert.equal(payload.identity, 'ordinal');
  assert.deepEqual(payload.rows[0], { ordinal: 1, title: 'Opening', mmss: '00:50', ms: 50000 });
});
