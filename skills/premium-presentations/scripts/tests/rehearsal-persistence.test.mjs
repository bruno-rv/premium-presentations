// v1.3 R1 — rehearsal persistence: localStorage read/write/cap, median
// budgets, and the slideCount-mismatch filter (DESIGN_V1_3_PRESENTER_MOAT.md
// ADR-2/ADR-3). AT1 and AT3 (per DESIGN §5, AT3 may live here or in
// teleprompter.test.mjs — kept here for persistence topical cohesion).

import assert from 'node:assert/strict';
import test from 'node:test';

import { FakeBC, installGlobalFakeBC, loadScript, makeWindow as makeBaseWindow } from './_helpers.mjs';

installGlobalFakeBC();

const FOUR_SLIDES = `
      <section class="slide" id="slide-1"><h1 class="slide__display">Opening</h1><aside class="notes">One.</aside></section>
      <section class="slide" id="slide-2"><h1 class="slide__display">Problem framing</h1><aside class="notes">Two.</aside></section>
      <section class="slide" id="slide-3"><h1 class="slide__display">Approach</h1><aside class="notes">Three.</aside></section>
      <section class="slide" id="slide-4"><h1 class="slide__display">Retrieval benchmark</h1><aside class="notes">Four.</aside></section>
`;

function makeWindow(options) {
  return makeBaseWindow({ slides: FOUR_SLIDES, bc: FakeBC, ...options });
}

function tick(ms = 20) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Fixture from DEFINE_V1_3_PRESENTER_MOAT.md AT1 (medians corrected per
// DESIGN §0: slide 3 sorted [62000,65000,70000] -> 65000, not 62000).
const AT1_FIXTURE = {
  version: 1,
  slideCount: 4,
  runs: [
    { ts: 1, totalMs: 240000, slideMs: [50000, 70000, 55000, 65000] },
    { ts: 2, totalMs: 240000, slideMs: [52000, 68000, 60000, 62000] },
    { ts: 3, totalMs: 240000, slideMs: [48000, 72000, 50000, 70000] },
  ],
};
const AT1_EXPECTED_MEDIANS = [50000, 70000, 55000, 65000];
const AT1_EXPECTED_TS3_DELTAS = [-12000, 12000, -10000, 10000];
const REHEARSAL_KEY = 'premium-rehearsal:/deck.html';

async function setupPresenterPair({ now = 1_700_000_000_000, seedRehearsal } = {}) {
  FakeBC.channels = new Map();

  const deck = makeWindow({ url: 'http://localhost/deck.html', focused: true });
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
    withSlides: false,
  });
  popup.window.Date.now = () => now;

  // Seed the localStorage fixture BEFORE premium-presenter.js loads in the
  // popup, so the very first renderTimeline() (triggered by the deck's
  // snapshot reply) already reads it — this is the read path under test
  // (ADR-2), not a synthetic call into a private function.
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

test('AT1 — injected 3-run fixture renders expected medians + ts3 deltas', async (t) => {
  const { deck, popup, deckControls } = await setupPresenterPair({ seedRehearsal: AT1_FIXTURE });
  t.after(() => { deck.window.close(); popup.window.close(); });

  // Pin the timer total to 240000ms over 4 slides -> getPlannedSlideMs() = 60000.
  deck.window.PremiumTimer.setMinutes(4);
  await tick(100);

  assert.equal(deckControls.getState().total, 4, 'stubbed 4-slide context');

  // Spread: getSuggestedBudgets()/getLastRunDeltas() return arrays created in
  // the popup window's own realm; assert.deepEqual (strict) treats
  // same-content cross-realm arrays as non-reference-equal, so normalize into
  // this module's realm first.
  const budgets = [...popup.window.PremiumPresenterView.getSuggestedBudgets()];
  assert.deepEqual(budgets, AT1_EXPECTED_MEDIANS,
    'per-slide median must be [50000,70000,55000,65000] (slide 3 corrected from ' +
    'DEFINE line 121\'s mis-copied 62000 — DESIGN §0)');

  const deltas = [...popup.window.PremiumPresenterView.getLastRunDeltas()];
  assert.deepEqual(deltas, AT1_EXPECTED_TS3_DELTAS,
    'delta vs uniform average for the most-recent run (ts=3) must be ' +
    '[-12000,+12000,-10000,+10000]');

  // Light DOM checks: budget block renders a non-empty markdown table, and
  // deltas surface only inside #pp-timeline <li> nodes.
  const budgetPre = popup.window.document.querySelector('#pp-budget-block pre');
  assert.ok(budgetPre && budgetPre.textContent.includes('50000'), 'budget block renders the median markdown table');
  assert.ok(budgetPre.textContent.includes('Budget (ms)'), 'budget table carries the Tier-2 Budget (ms) column');

  const deltaSpans = [...popup.window.document.querySelectorAll('#pp-timeline .pp-timeline__delta')];
  assert.equal(deltaSpans.length, 4, 'one delta span per timeline slide');
  assert.match(deltaSpans[0].textContent, /-12:00|-0:12|vs avg/, 'delta span renders signed vs-average text');

  // ADR-6 invariant: the timer pace pill is never touched by R1 code.
  const pacePill = popup.window.document.getElementById('pp-timer-pace');
  assert.ok(pacePill, 'pace pill exists');
  assert.doesNotMatch(pacePill.textContent, /vs avg|median/, 'pace pill must never render coach/delta text');
});

test('cap-10 eviction — the 11th persisted run evicts the oldest', async (t) => {
  const { deck, popup, deckControls, advance } = await setupPresenterPair({ now: 1_700_000_000_000 });
  t.after(() => { deck.window.close(); popup.window.close(); });

  deck.window.PremiumTimer.setMinutes(4);
  await tick(50);

  const toggle = popup.window.document.getElementById('pp-rehearsal-toggle');
  const reset = popup.window.document.getElementById('pp-rehearsal-reset');

  for (let i = 0; i < 11; i++) {
    toggle.click();               // start
    deckControls.goTo(0);
    advance(5_000);                // simulate elapsed rehearsal time (pollution guard needs >0ms)
    toggle.click();               // pause -> persistRun()
    reset.click();                // clears in-memory + rehearsalRunTs, opens next run
    await tick(5);
  }

  const store = popup.window.PremiumPresenterView.getRehearsalStore();
  assert.equal(store.runs.length, 10, 'runs[] never exceeds the 10-run cap');
});

test('slideCount-mismatch filter — mismatched runs are kept but excluded from medians', async (t) => {
  const mixed = {
    version: 1,
    slideCount: 4,
    runs: [
      { ts: 1, totalMs: 240000, slideMs: [50000, 70000, 55000, 65000] },
      { ts: 2, totalMs: 240000, slideMs: [52000, 68000, 60000, 62000] },
      { ts: 3, totalMs: 180000, slideMs: [60000, 60000, 60000] }, // 3-slide deck, mismatched
    ],
  };
  const { deck, popup } = await setupPresenterPair({ seedRehearsal: mixed });
  t.after(() => { deck.window.close(); popup.window.close(); });

  deck.window.PremiumTimer.setMinutes(4);
  await tick(100);

  const budgets = [...popup.window.PremiumPresenterView.getSuggestedBudgets()];
  // Only the two 4-slide runs are eligible; median of 2 values is the
  // Math.round((lo+hi)/2) even-count rule (ADR-3).
  assert.deepEqual(budgets, [51000, 69000, 57500, 63500]);

  const store = popup.window.PremiumPresenterView.getRehearsalStore();
  assert.equal(store.runs.length, 3, 'mismatched run stays in runs[] (never discarded)');
});

test('AT3 — rehearsal persists across popup close/reopen', async (t) => {
  const { deck, popup, deckControls, advance } = await setupPresenterPair({ now: 1_700_000_000_000 });
  t.after(() => { deck.window.close(); popup.window.close(); });

  deck.window.PremiumTimer.setMinutes(4);
  await tick(50);

  const toggle = popup.window.document.getElementById('pp-rehearsal-toggle');
  toggle.click();                 // start
  advance(45_000);
  deckControls.goTo(1);
  await tick(50);
  advance(20_000);
  toggle.click();                 // pause -> persistRun() commits the run

  const persisted = popup.window.localStorage.getItem(REHEARSAL_KEY);
  assert.ok(persisted, 'run committed to localStorage on pause');
  const parsed = JSON.parse(persisted);   // plain JSON.parse in this module's own realm
  assert.equal(parsed.runs.length, 1);
  assert.deepEqual(parsed.runs[0].slideMs.slice(0, 2), [45000, 20000]);

  // Simulate popup close/reopen: new JSDOM window, same pathname, carrying
  // the same localStorage payload forward (a fresh JSDOM instance does not
  // share storage with the closed one — this models the same-origin
  // localStorage a real browser keeps across window close/reopen).
  const deckSession = deck.window.document.documentElement.dataset.session;
  const popup2 = makeWindow({
    url: 'http://localhost/deck.html?presenter=1&session=' + deckSession,
    focused: true,
    withSlides: false,
  });
  popup2.window.localStorage.setItem(REHEARSAL_KEY, persisted);
  loadScript(popup2, 'premium-controller.js');
  await tick(0);
  loadScript(popup2, 'premium-presenter.js');
  await tick(100);

  const reopenedStore = popup2.window.PremiumPresenterView.getRehearsalStore();
  assert.equal(reopenedStore.runs.length, parsed.runs.length, 'runs.length unchanged after reopen');
  assert.deepEqual([...reopenedStore.runs[0].slideMs], parsed.runs[0].slideMs, 'slideMs[] intact after reopen');

  const firstItem = popup2.window.document.querySelector('#pp-timeline li[data-index="0"]');
  assert.match(firstItem.textContent, /actual 0:45/, 'restored run renders in the reopened timeline');

  popup2.window.close();
});

test('same-ms collision — a stubbed clock reused across runs must not collapse them', async (t) => {
  const { deck, popup, deckControls, advance } = await setupPresenterPair({ now: 1_700_000_000_000 });
  t.after(() => { deck.window.close(); popup.window.close(); });

  deck.window.PremiumTimer.setMinutes(4);
  await tick(50);

  const toggle = popup.window.document.getElementById('pp-rehearsal-toggle');
  const reset = popup.window.document.getElementById('pp-rehearsal-reset');

  // Run 1: start -> 5s elapsed -> pause. persistRun assigns rehearsalRunTs
  // lazily, so ts1 is Date.now() AT PAUSE, not at start.
  toggle.click();
  advance(5_000);
  toggle.click();
  await tick(5);

  let store = popup.window.PremiumPresenterView.getRehearsalStore();
  assert.equal(store.runs.length, 1, 'run 1 persisted');
  const ts1 = store.runs[0].ts;

  reset.click();

  // Rewind the stubbed clock to the exact instants run 1 used (fake clocks
  // in tests/fast automation don't carry state across runs) so run 2's
  // pause-time Date.now() collides with ts1.
  advance(-5_000);
  toggle.click();               // start run 2 at the same instant run 1 started
  advance(5_000);
  toggle.click();               // pause -> candidate ts === ts1 without the guard
  await tick(5);

  store = popup.window.PremiumPresenterView.getRehearsalStore();
  assert.equal(store.runs.length, 2, 'run 2 must append, not replace run 1, despite the ts collision');
  const ts2 = store.runs[1].ts;
  assert.notEqual(ts2, ts1, 'colliding candidate ts is bumped to stay unique across different runs');

  // Idempotency still holds: resuming and re-pausing the SAME run (no reset
  // in between) upserts in place rather than duplicating (ADR-2).
  toggle.click();                // resume run 2 (rehearsalRunTs unchanged)
  advance(1_000);
  toggle.click();                // pause -> persistRun upserts run 2 again
  await tick(5);

  store = popup.window.PremiumPresenterView.getRehearsalStore();
  assert.equal(store.runs.length, 2, 'resume->pause on the same run upserts, not duplicates');
  assert.equal(store.runs[1].ts, ts2, 'upsert keeps matching the current run id');
});

test('Codex round-3 — unload commits the in-flight segment, no pause/slide-change needed', async (t) => {
  // Regression for the HIGH finding: onPopupUnload used to gate persistRun()
  // behind hasRehearsalData(), but elapsed time on the CURRENT slide only
  // lands in elapsedMs/slideMs via commitCurrentRehearsalSegment(), which
  // runs on pause or slide change — NOT on the 1s render-only interval. A
  // rehearsal that stayed on slide 1 the whole time looked "empty" at the
  // precheck and was silently dropped on popup close.
  const { deck, popup, advance } = await setupPresenterPair({ now: 1_700_000_000_000 });
  t.after(() => { deck.window.close(); popup.window.close(); });

  deck.window.PremiumTimer.setMinutes(4);
  await tick(50);

  const toggle = popup.window.document.getElementById('pp-rehearsal-toggle');
  toggle.click();               // start rehearsal on slide 1
  advance(37_000);              // dwell on slide 1 — no pause, no slide change
  await tick(5);

  popup.window.dispatchEvent(new popup.window.Event('beforeunload'));
  popup.window.dispatchEvent(new popup.window.Event('unload'));       // double-fire, per real browsers

  const persisted = popup.window.localStorage.getItem(REHEARSAL_KEY);
  assert.ok(persisted, 'unload with uncommitted dwell time still persists a run');
  const parsed = JSON.parse(persisted);
  assert.equal(parsed.runs.length, 1, 'beforeunload+unload double-fire upserts one run, not two');
  assert.ok(Math.abs(parsed.runs[0].slideMs[0] - 37_000) < 1000,
    'slide-1 dwell reflects the advanced clock even though nothing committed it before unload');
});

test('popup closed before rehearsal ever started — nothing persisted', async (t) => {
  const { deck, popup } = await setupPresenterPair({ now: 1_700_000_000_000 });
  t.after(() => { deck.window.close(); popup.window.close(); });

  deck.window.PremiumTimer.setMinutes(4);
  await tick(50);

  popup.window.dispatchEvent(new popup.window.Event('beforeunload'));
  popup.window.dispatchEvent(new popup.window.Event('unload'));

  assert.equal(popup.window.localStorage.getItem(REHEARSAL_KEY), null,
    'rehearsal never started (never active) — unload must not write anything');
});

test('corrupt payload sanitization — malformed runs are dropped on read, valid run survives', async (t) => {
  // Codex round-2: a hand-edited or corrupted localStorage payload must
  // degrade cleanly, not crash the popup. Mix of shapes readRehearsalStore()
  // must reject: null, a bare number, an object missing slideMs/totalMs, and
  // an object whose slideMs contains a non-numeric entry. VALID_RUN is the
  // only structurally sound entry ({ts, totalMs, slideMs[]} per schema).
  const VALID_RUN = { ts: 42, totalMs: 240000, slideMs: [50000, 70000, 55000, 65000] };
  const CORRUPT_FIXTURE = {
    version: 1,
    slideCount: 4,
    runs: [null, 5, { ts: 'x' }, { ts: 1, slideMs: [1, 'a'] }, VALID_RUN],
  };

  const { deck, popup, advance } = await setupPresenterPair({ seedRehearsal: CORRUPT_FIXTURE });
  t.after(() => { deck.window.close(); popup.window.close(); });

  const errors = [];
  popup.window.addEventListener('error', (e) => errors.push(e.error || e.message));

  deck.window.PremiumTimer.setMinutes(4);
  await tick(100);

  assert.deepEqual(errors, [], 'malformed runs must not throw during initial timeline + budget render');

  const store = popup.window.PremiumPresenterView.getRehearsalStore();
  assert.equal(store.runs.length, 1, 'malformed entries are dropped on read; only VALID_RUN survives');
  assert.deepEqual([...store.runs[0].slideMs], VALID_RUN.slideMs);

  // Median math must use only the sanitized run — a solo run's "median" is
  // itself.
  const budgets = [...popup.window.PremiumPresenterView.getSuggestedBudgets()];
  assert.deepEqual(budgets, VALID_RUN.slideMs, 'medians are computed only from the sanitized valid run');

  // A subsequent pause-persist must succeed and re-write a sanitized store —
  // the malformed entries are never resurrected by the upsert path.
  const toggle = popup.window.document.getElementById('pp-rehearsal-toggle');
  toggle.click();                 // start
  advance(5_000);
  toggle.click();                 // pause -> persistRun() commits the new run
  await tick(20);

  assert.deepEqual(errors, [], 'pause-persist on a sanitized store must not throw');
  const persisted = JSON.parse(popup.window.localStorage.getItem(REHEARSAL_KEY));
  assert.equal(persisted.runs.length, 2, 'persisted store holds the sanitized VALID_RUN plus the new run');
  assert.ok(
    persisted.runs.every((r) => r && Number.isFinite(r.ts) && Number.isFinite(r.totalMs) && Array.isArray(r.slideMs)),
    'every run written back is structurally sound; no malformed entry resurrected',
  );
});
