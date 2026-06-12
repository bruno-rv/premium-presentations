// Runtime jsdom test for theme visual data-URI resolution end-to-end.
//
// Proves that in a bundled deck context — where window.PremiumThemeVisuals
// carries embedded data: URIs — every .theme-visual__image src resolves to
// a data: URI after setTheme() for every manifest theme. Also regression-tests
// the themeVisualSrc() passthrough regex: a data: URI must never get a
// base-path prefix prepended to it.
//
// Does NOT depend on a pre-built bundle file. Builds a synthetic in-memory
// deck using makeWindow() (matching the harness idiom of the other suites),
// evals the embed block manually before loading premium-controls.js, then
// fires DOMContentLoaded so init() runs (JSDOM readyState is 'loading').

import { readFileSync } from 'fs';
import { join } from 'path';
import { ROOT, SHARED, makeWindow } from './_helpers.mjs';

// ── Read manifest dynamically so the test tracks manifest additions ──────────

const MANIFEST_PATH = join(ROOT, 'assets', 'shared', 'assets', 'theme-visuals', 'manifest.json');
const manifest = JSON.parse(readFileSync(MANIFEST_PATH, 'utf8'));
const THEMES = Object.keys(manifest); // ['editorial', 'warm', 'red', 'cupertino']

// Build roles map: theme → [role, ...] from manifest assets array
const THEME_ROLES = {};
for (const [theme, entry] of Object.entries(manifest)) {
  THEME_ROLES[theme] = (entry.assets || []).map((a) => a.role);
}

// ── Synthetic PremiumThemeVisuals payload (simulates bundler embed) ──────────

// For each theme + role, use a deterministic test data URI. The exact bytes
// don't matter — what matters is that they carry the data: scheme so we can
// verify no base-path corruption occurred.
function makeTestDataUri(theme, role) {
  return `data:image/webp;base64,TEST${theme.toUpperCase()}${role.toUpperCase()}`;
}

const PREMIUM_THEME_VISUALS = {};
for (const theme of THEMES) {
  PREMIUM_THEME_VISUALS[theme] = {};
  for (const role of THEME_ROLES[theme]) {
    PREMIUM_THEME_VISUALS[theme][role] = makeTestDataUri(theme, role);
  }
}

// ── Shared assertion helpers ──────────────────────────────────────────────────

let passed = 0;
let failed = 0;

function assert(label, condition, detail) {
  if (condition) {
    console.log('  PASS — ' + label);
    passed++;
  } else {
    console.error('  FAIL — ' + label + (detail ? ': ' + detail : ''));
    failed++;
  }
}

// ── Build JSDOM window from makeWindow() ─────────────────────────────────────
//
// makeWindow() uses runScripts: 'outside-only' (no auto-executed inline
// scripts) and produces a standard stubs environment (matchMedia, IO, rAF,
// crypto). JSDOM readyState is 'loading' at eval time — premium-controls.js
// defers init() to DOMContentLoaded in that case — so we fire it manually
// after loading the script, matching the pattern in presenter-smoke.mjs.

const SLIDES_MARKUP = `
  <section class="slide slide--title" id="slide-1">
    <h1 class="slide__display">Title Slide</h1>
  </section>
  <section class="slide slide--divider" id="slide-2">
    <h2 class="slide__heading">Divider Slide</h2>
  </section>
`;

const dom = makeWindow({
  url: 'http://localhost/bundle/deck.html',
  slides: SLIDES_MARKUP,
  withSlides: true,
});

const win = dom.window;
const doc = win.document;

// Set data-theme + data-themes on <html> so discoverThemes() returns all 4
// themes without needing CSS stylesheets.
doc.documentElement.dataset.theme = 'editorial';
doc.documentElement.dataset.themes = THEMES.join(',');

// Eval the embed block — simulates the bundler-injected PremiumThemeVisuals
// script block that bundle_deck.py will produce.
const embedScript = `window.PremiumThemeVisuals = Object.assign(
  ${JSON.stringify(PREMIUM_THEME_VISUALS, null, 2)},
  window.PremiumThemeVisuals || {}
);`;
win.eval(embedScript);

// Load premium-controls.js — readyState is 'loading', so init() will register
// a DOMContentLoaded listener and wait.
win.eval(readFileSync(join(SHARED, 'premium-controls.js'), 'utf8'));

// Fire DOMContentLoaded to trigger init() (mirrors fireReadyStateLoaded in
// presenter-smoke.mjs).
const dclEvent = new win.Event('DOMContentLoaded');
doc.dispatchEvent(dclEvent);

// Allow micro-tasks to flush.
await new Promise((r) => setTimeout(r, 20));

// ── TEST SUITE ────────────────────────────────────────────────────────────────

console.log('\nTest suite: theme-visuals runtime data-URI resolution');
console.log('Manifest themes:', THEMES.join(', '));

// ── Test 1: manifest theme count sanity check ────────────────────────────────
// Explicit count guard so a manifest change is a conscious test update, not a
// silent pass.

console.log('\nTest: manifest theme count');
assert(
  'manifest has exactly 4 themes',
  THEMES.length === 4,
  'got: ' + THEMES.length + ' (' + THEMES.join(', ') + ')'
);

// ── Test 2: .theme-visual__image elements injected after init ────────────────

console.log('\nTest: .theme-visual__image elements injected on title and divider slides');
{
  const imgs = doc.querySelectorAll('.theme-visual__image');
  assert(
    '.theme-visual__image elements exist after init',
    imgs.length >= 2,
    'found: ' + imgs.length
  );

  const titleSlide = doc.querySelector('.slide--title');
  const dividerSlide = doc.querySelector('.slide--divider');

  assert(
    'title slide has a .theme-visual__image',
    titleSlide !== null && titleSlide.querySelector('.theme-visual__image') !== null
  );
  assert(
    'divider slide has a .theme-visual__image',
    dividerSlide !== null && dividerSlide.querySelector('.theme-visual__image') !== null
  );
}

// ── Test 3: PremiumPresentations.setTheme is exposed ────────────────────────

console.log('\nTest: window.PremiumPresentations API exposed');
{
  assert(
    'window.PremiumPresentations exists',
    typeof win.PremiumPresentations === 'object' && win.PremiumPresentations !== null
  );
  assert(
    'setTheme is a function',
    typeof win.PremiumPresentations.setTheme === 'function'
  );
}

// ── Test 4: every theme → every .theme-visual__image src is a data: URI ─────
//
// Primary assertion. For each manifest theme, call setTheme() and verify that
// every .theme-visual__image src starts with 'data:image/webp;base64,' — never
// a relative path like 'shared/assets/...' or '../../shared/...'.
//
// NOTE: this test WILL FAIL if the regex passthrough fix at premium-controls.js
// ~line 327 has not yet landed (data: absent from the passthrough pattern).
// That is expected-red until Approach item 1 is applied. Do NOT weaken this
// assertion.

console.log('\nTest: setTheme() → all .theme-visual__image srcs are data: URIs');
for (const theme of THEMES) {
  win.PremiumPresentations.setTheme(theme);

  const imgs = doc.querySelectorAll('.theme-visual__image');
  assert(
    `theme "${theme}": .theme-visual__image elements present`,
    imgs.length >= 2,
    'found: ' + imgs.length
  );

  for (const img of imgs) {
    const src = img.getAttribute('src') || '';
    assert(
      `theme "${theme}": img src is data:image/webp;base64, (not a relative path)`,
      src.startsWith('data:image/webp;base64,'),
      'got src: ' + (src.length > 80 ? src.slice(0, 80) + '...' : src)
    );
    assert(
      `theme "${theme}": img src does not start with shared/`,
      !src.startsWith('shared/'),
      'got src: ' + src.slice(0, 60)
    );
    assert(
      `theme "${theme}": img src does not start with ../../`,
      !src.startsWith('../../'),
      'got src: ' + src.slice(0, 60)
    );
  }
}

// ── Test 5: regression — data: URI passes through unmangled ─────────────────
//
// Directly verify that the exact data URI value set in PremiumThemeVisuals
// arrives on the img element without any base-path prefix prepended. This
// catches the original bug: themeVisualSrc() prepended themeVisualBase() to a
// data: string because data: was absent from the passthrough regex at ~line 327.
//
// We check editorial/hero as the representative case.

console.log('\nTest: regression — data: URI value passes through unmangled');
{
  win.PremiumPresentations.setTheme('editorial');

  const titleSlide = doc.querySelector('.slide--title');
  const img = titleSlide && titleSlide.querySelector('.theme-visual__image');
  const src = img ? (img.getAttribute('src') || '') : '';
  const expected = makeTestDataUri('editorial', 'hero');

  assert(
    'editorial/hero img src equals exact data URI (no base-path corruption)',
    src === expected,
    '\n         expected: ' + expected +
    '\n              got: ' + src
  );
}

// ── Test 6: setTheme cycles back to initial theme cleanly ────────────────────

console.log('\nTest: setTheme cycles back to editorial after full cycle');
{
  // Cycle through all themes then back to editorial
  for (const theme of THEMES) {
    win.PremiumPresentations.setTheme(theme);
  }
  win.PremiumPresentations.setTheme('editorial');

  const imgs = doc.querySelectorAll('.theme-visual__image');
  let allDataUri = true;
  for (const img of imgs) {
    const src = img.getAttribute('src') || '';
    if (!src.startsWith('data:image/webp;base64,')) { allDataUri = false; }
  }
  assert(
    'after full cycle + back to editorial, all srcs are data: URIs',
    allDataUri
  );
}

// ── Summary ──────────────────────────────────────────────────────────────────

console.log('\nResults: ' + passed + ' passed, ' + failed + ' failed');

if (failed > 0) {
  // Check whether the failure is likely the expected pre-fix red by inspecting
  // the source for the data: passthrough in themeVisualSrc.
  const regexFixed = (() => {
    const controlsSrc = readFileSync(join(SHARED, 'premium-controls.js'), 'utf8');
    const fnIdx = controlsSrc.indexOf('function themeVisualSrc');
    const fnSnippet = fnIdx >= 0 ? controlsSrc.slice(fnIdx, fnIdx + 600) : '';
    return fnSnippet.includes('data:');
  })();
  if (!regexFixed) {
    console.error(
      '\nNOTE: The data: passthrough regex fix has NOT landed in premium-controls.js yet.'
    );
    console.error(
      '      data: URI assertions are expected-red until Approach item 1 is applied.'
    );
  }
  process.exit(1);
}
process.exit(0);
