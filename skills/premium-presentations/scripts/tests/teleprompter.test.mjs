// v1.3 R2 — teleprompter mode: distance-reading toggle (`m`), explicit
// start/pause scroll (`p`), speed keys (`[`/`]`), reduced-motion safety
// (DESIGN_V1_3_PRESENTER_MOAT.md ADR-1). AT2 (DEFINE_V1_3_PRESENTER_MOAT.md).

import assert from 'node:assert/strict';
import test from 'node:test';
import { execFileSync } from 'node:child_process';

import { FakeBC, installGlobalFakeBC, loadScript, makeWindow as makeBaseWindow, ROOT } from './_helpers.mjs';

installGlobalFakeBC();

const TWO_SLIDES = `
      <section class="slide" id="slide-1"><h1 class="slide__display">One</h1><aside class="notes">Notes for slide one, long enough to scroll in a teleprompter pane.</aside></section>
      <section class="slide" id="slide-2"><h1 class="slide__display">Two</h1><aside class="notes">Notes for slide two.</aside></section>
`;

function makeWindow(options) {
  return makeBaseWindow({ slides: TWO_SLIDES, bc: FakeBC, ...options });
}

function tick(ms = 20) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function setupPresenterPair({ reducedMotion = false } = {}) {
  FakeBC.channels = new Map();

  const deck = makeWindow({ url: 'http://localhost/deck.html', focused: true });
  loadScript(deck, 'premium-controller.js');
  await tick(0);
  loadScript(deck, 'slide-engine.js');
  deck.window.eval('new SlideEngine();');
  loadScript(deck, 'premium-timer.js');
  loadScript(deck, 'premium-presenter.js');
  const deckSession = deck.window.document.documentElement.dataset.session;

  const popup = makeWindow({
    url: 'http://localhost/deck.html?presenter=1&session=' + deckSession,
    focused: true,
    withSlides: false,
  });
  // AT2: install matchMedia BEFORE premium-presenter.js loads so
  // prefersReducedMotion() reads the reduced-motion preference from the
  // first render onward, exactly as a real browser would report it.
  popup.window.matchMedia = (query) => ({
    media: query,
    matches: reducedMotion && /prefers-reduced-motion/.test(query),
    addEventListener: () => {},
    removeEventListener: () => {},
  });

  loadScript(popup, 'premium-controller.js');
  await tick(0);
  loadScript(popup, 'premium-presenter.js');
  await tick(100);

  return { deck, popup };
}

function pressKey(win, key, code) {
  const ev = new win.KeyboardEvent('keydown', { key, code: code || key, bubbles: true, cancelable: true });
  win.document.dispatchEvent(ev);
}

test('AT2 — reduced motion: mode toggle applies the CSS class with no motion; only `p` starts scroll', async (t) => {
  const { deck, popup } = await setupPresenterPair({ reducedMotion: true });
  t.after(() => { deck.window.close(); popup.window.close(); });

  const notes = popup.window.document.getElementById('pp-notes');
  assert.ok(notes, 'notes pane mounted');

  // Initial state: always paused, matching the accessibility invariant
  // regardless of the reduced-motion preference (R2.5).
  let state = popup.window.PremiumPresenterView.getTeleprompterState();
  assert.equal(state.scrolling, false, 'teleprompter never auto-starts');
  assert.equal(state.reducedMotion, true, 'prefersReducedMotion() reflects the stubbed matchMedia');

  // `m` toggles distance-reading mode ON — CSS class only, no motion.
  pressKey(popup.window, 'm');
  assert.ok(notes.classList.contains('pp-notes--teleprompter'), 'mode-on applies the distance-reading class');
  state = popup.window.PremiumPresenterView.getTeleprompterState();
  assert.equal(state.mode, true);
  assert.equal(state.scrolling, false, 'mode toggle alone must not start motion (AT2)');

  const scrollBefore = notes.scrollTop;
  await tick(120); // long enough for a would-be scroll tick (50ms) to have fired if buggy
  assert.equal(notes.scrollTop, scrollBefore, 'no scroll motion occurs from mode toggle under reduced motion');

  // `p` is the explicit start — allowed even under reduced motion (never AUTO).
  pressKey(popup.window, 'p');
  state = popup.window.PremiumPresenterView.getTeleprompterState();
  assert.equal(state.scrolling, true, 'p is the explicit start gesture');
  await tick(120);
  assert.ok(notes.scrollTop > scrollBefore, 'scrollTop advances only after the explicit p start');

  // `p` again pauses.
  pressKey(popup.window, 'p');
  state = popup.window.PremiumPresenterView.getTeleprompterState();
  assert.equal(state.scrolling, false, 'second p press pauses');
  const scrollAfterPause = notes.scrollTop;
  await tick(120);
  assert.equal(notes.scrollTop, scrollAfterPause, 'no further motion once paused');
});

test('teleprompter mode toggle never starts motion when reduced motion is NOT set', async (t) => {
  const { deck, popup } = await setupPresenterPair({ reducedMotion: false });
  t.after(() => { deck.window.close(); popup.window.close(); });

  const notes = popup.window.document.getElementById('pp-notes');
  const state0 = popup.window.PremiumPresenterView.getTeleprompterState();
  assert.equal(state0.scrolling, false, 'initial load is always paused, reduced-motion or not');

  pressKey(popup.window, 'm');
  const scrollBefore = notes.scrollTop;
  await tick(120);
  assert.equal(notes.scrollTop, scrollBefore, 'mode toggle alone never starts motion, regardless of the motion preference');
});

test('speed keys ([ / ]) adjust and persist the scroll rate via e.code', async (t) => {
  const { deck, popup } = await setupPresenterPair({ reducedMotion: false });
  t.after(() => { deck.window.close(); popup.window.close(); });

  const initialRate = popup.window.PremiumPresenterView.getTeleprompterState().rate;
  pressKey(popup.window, ']', 'BracketRight');
  let rate = popup.window.PremiumPresenterView.getTeleprompterState().rate;
  assert.ok(rate > initialRate, 'BracketRight speeds up');

  pressKey(popup.window, '[', 'BracketLeft');
  pressKey(popup.window, '[', 'BracketLeft');
  rate = popup.window.PremiumPresenterView.getTeleprompterState().rate;
  assert.ok(rate < initialRate, 'BracketLeft slows down below the initial rate');

  const persisted = popup.window.localStorage.getItem('premium-teleprompter');
  assert.equal(Number(persisted), rate, 'rate is persisted to localStorage on every nudge');
});

test('keymap-collision — m / p / [ / ] are new bindings, absent from the pre-v1.3 handler', (t) => {
  const relPath = 'skills/premium-presentations/assets/shared/premium-presenter.js';
  // Pinned to the commit immediately BEFORE af5a8e9 (v1.3 presenter moat),
  // not HEAD — HEAD moves and eventually becomes the feature commit itself,
  // which would diff the file against itself and always pass trivially.
  const baselineCommit = '5263929';
  let baseline;
  try {
    baseline = execFileSync('git', ['show', baselineCommit + ':' + relPath], { cwd: ROOT, encoding: 'utf8' });
  } catch (err) {
    t.skip('pinned baseline commit ' + baselineCommit + ' is unavailable (shallow clone?): ' + err.message);
    return;
  }
  assert.doesNotMatch(baseline, /key === 'm'/, 'pre-v1.3 handler must not already bind m');
  assert.doesNotMatch(baseline, /key === 'p'/, 'pre-v1.3 handler must not already bind p');
  assert.doesNotMatch(baseline, /BracketRight/, 'pre-v1.3 handler must not already bind ]');
  assert.doesNotMatch(baseline, /BracketLeft/, 'pre-v1.3 handler must not already bind [');

  const current = execFileSync('git', ['show', 'HEAD:' + relPath], { cwd: ROOT, encoding: 'utf8' });
  assert.match(current, /key === 'm'/, 'current handler must bind m');
  assert.match(current, /key === 'p'/, 'current handler must bind p');
  assert.match(current, /BracketRight/, 'current handler must bind ]');
  assert.match(current, /BracketLeft/, 'current handler must bind [');
});
