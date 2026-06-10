// 3D mode engine tests (premium-controls.js): cycle order via e.code,
// scoped persistence, legacy policy, author defaults, invalid modes, compat
// wrappers, reduced-motion no-bind, .slide-3d-frame injection, and CSS
// contract assertions (depth section placement, print flatten).

import { JSDOM } from 'jsdom';
import { readFileSync } from 'fs';
import { join } from 'path';
import { SHARED, ROOT } from './_helpers.mjs';

let failures = 0;
function assert(cond, label) {
  if (cond) { console.log('  ok  ' + label); }
  else { failures += 1; console.log('  FAIL ' + label); }
}

const CONTROLS_SRC = readFileSync(join(SHARED, 'premium-controls.js'), 'utf8');

const SLIDES = `
  <section class="slide slide--title" id="slide-1">
    <figure class="theme-visual"><img></figure>
    <div class="slide__glow"></div>
    <p class="slide__subtitle reveal">Sub</p>
    <h1 class="slide__display reveal">One</h1>
    <aside class="notes">notes here</aside>
  </section>
  <section class="slide" id="slide-2">
    <div class="slide__number">02</div>
    <h2 class="slide__heading reveal">Two</h2>
    <p class="slide__body reveal">Body</p>
  </section>
`;

// makeWindow in _helpers uses id="deck" without class; build our own fixture
// with class="deck" + chrome-rich slides and controllable matchMedia.
async function makeDeck({ htmlAttrs = '', stored = {}, reduce = false, fine = true, url = 'http://localhost/deck.html' } = {}) {
  const html = `<!doctype html><html ${htmlAttrs}><head></head><body>
    <div class="deck" id="deck">${SLIDES}</div></body></html>`;
  const dom = new JSDOM(html, { url, runScripts: 'outside-only', pretendToBeVisual: true });
  const w = dom.window;
  for (const [k, v] of Object.entries(stored)) {
    w.localStorage.setItem(k, v);
  }
  w.matchMedia = (q) => ({
    matches: /prefers-reduced-motion/.test(q) ? reduce : (/any-hover/.test(q) ? fine : false),
    addEventListener: () => {},
    removeEventListener: () => {},
  });
  w.requestAnimationFrame = (cb) => setTimeout(cb, 0);
  w.cancelAnimationFrame = (id) => clearTimeout(id);
  w.eval(CONTROLS_SRC);
  // JSDOM stays in readyState 'loading' until the next tick — init() runs on
  // DOMContentLoaded, so give it a beat.
  await new Promise((r) => setTimeout(r, 0));
  return dom;
}

function mode(dom) { return dom.window.document.documentElement.getAttribute('data-3d'); }
function pressDigit3(dom, shift = false) {
  const w = dom.window;
  const e = new w.KeyboardEvent('keydown', { code: 'Digit3', key: shift ? '#' : '3', shiftKey: shift, bubbles: true, cancelable: true });
  w.document.body.dispatchEvent(e);
}
const SCOPED_KEY = 'premium-3d:/deck.html';

console.log('Test: resolution order + defaults');
{
  let d = await makeDeck();
  assert(mode(d) === 'off', 'no stored/attr -> off');
  assert(d.window.document.documentElement.dataset.parallax === 'off', 'data-parallax mirrored off');

  d = await makeDeck({ htmlAttrs: 'data-3d="tilt"' });
  assert(mode(d) === 'tilt', 'author data-3d="tilt" respected');
  assert(d.window.localStorage.getItem(SCOPED_KEY) === null, 'author default not persisted as user pref');

  d = await makeDeck({ htmlAttrs: 'data-3d="banana"' });
  assert(mode(d) === 'off', 'invalid author mode -> off');

  d = await makeDeck({ htmlAttrs: 'data-parallax="on"' });
  assert(mode(d) === 'ambient', 'legacy attr data-parallax="on" -> ambient');

  d = await makeDeck({ htmlAttrs: 'data-3d="depth"', stored: { [SCOPED_KEY]: 'tilt' } });
  assert(mode(d) === 'tilt', 'stored scoped pref beats author attr');

  d = await makeDeck({ stored: { [SCOPED_KEY]: 'banana' } });
  assert(mode(d) === 'off', 'invalid stored mode -> off');

  d = await makeDeck({ stored: { 'premium-parallax': 'on' } });
  assert(mode(d) === 'off', 'legacy UNSCOPED stored key is ignored (no migration)');

  d = await makeDeck({ htmlAttrs: 'data-3d="ambient"', stored: { 'premium-parallax': 'off' } });
  assert(mode(d) === 'ambient', 'legacy stored value never overrides author default');
}

console.log('Test: cycle order via e.code Digit3 + persistence');
{
  const d = await makeDeck();
  const seen = [mode(d)];
  for (let i = 0; i < 4; i++) { pressDigit3(d); seen.push(mode(d)); }
  assert(seen.join('>') === 'off>ambient>tilt>depth>off', 'forward cycle off>ambient>tilt>depth>off');
  pressDigit3(d, true);
  assert(mode(d) === 'depth', 'Shift+3 cycles backward (off -> depth)');
  assert(d.window.localStorage.getItem(SCOPED_KEY) === 'depth', 'cycle persists to scoped key');
  assert(d.window.localStorage.getItem('premium-parallax') === null, 'legacy unscoped key never written');
  const toast = d.window.document.getElementById('premium-3d-toast');
  assert(!!toast && toast.textContent === '3D: DEPTH', 'toast shows current mode via textContent');
  const sel = d.window.document.getElementById('premium-3d');
  assert(!!sel && sel.value === 'depth', '#premium-3d select synced');
}

console.log('Test: compat wrappers + API surface');
{
  const d = await makeDeck();
  const api = d.window.PremiumPresentations;
  assert(typeof api.set3dMode === 'function' && typeof api.cycle3d === 'function' && typeof api.get3dMode === 'function', 'new API exposed');
  api.setParallax(true);
  assert(mode(d) === 'ambient', 'setParallax(true) -> ambient');
  api.setParallax(false);
  assert(mode(d) === 'off', 'setParallax(false) -> off');
  api.toggleParallax();
  assert(mode(d) === 'ambient', 'toggleParallax off -> ambient');
  api.set3dMode('depth');
  api.toggleParallax();
  assert(mode(d) === 'off', 'toggleParallax from depth -> off');
  api.set3dMode('nope');
  assert(mode(d) === 'off', 'set3dMode invalid -> off');
  assert(d.window.document.documentElement.dataset.parallax === 'off', 'mirror follows API calls');
}

console.log('Test: .slide-3d-frame injection');
{
  const d = await makeDeck();
  const doc = d.window.document;
  const s1 = doc.getElementById('slide-1');
  const frame = s1.querySelector(':scope > .slide-3d-frame');
  assert(!!frame, 'frame injected as direct child');
  assert(!!s1.querySelector(':scope > .theme-visual'), 'theme-visual stays outside frame');
  assert(!!s1.querySelector(':scope > .slide__glow'), 'slide__glow stays outside frame');
  assert(!!s1.querySelector(':scope > .notes'), 'notes stay outside frame');
  assert(!!doc.querySelector('#slide-2 > .slide__number'), 'slide__number stays outside frame (corner rule intact)');
  assert(!!frame.querySelector('.slide__display'), 'content moved inside frame');
  s1.classList.add('visible');
  assert(!!doc.querySelector('.slide.visible .reveal:nth-child(1)'), 'reveal stagger nth-child still matches inside frame');
  // Idempotent re-init
  d.window.eval(CONTROLS_SRC);
  assert(s1.querySelectorAll('.slide-3d-frame').length === 1, 're-init does not double-wrap');
}

console.log('Test: motion gating (reduced motion / pointer writes)');
{
  // Fine pointer, motion allowed: tilt writes vars on the active frame.
  const d = await makeDeck();
  d.window.PremiumPresentations.set3dMode('tilt');
  const doc = d.window.document;
  doc.getElementById('slide-1').classList.add('visible');
  doc.dispatchEvent(new d.window.Event('pointermove'));
  const move = new d.window.Event('pointermove');
  move.clientX = 100; move.clientY = 100;
  doc.dispatchEvent(move);
  await new Promise((r) => setTimeout(r, 50));
  const frame = doc.querySelector('.slide.visible .slide-3d-frame');
  assert(frame && frame.style.getPropertyValue('--tilt-x') !== '', 'tilt writes --tilt-x on active frame');

  d.window.PremiumPresentations.set3dMode('off');
  await new Promise((r) => setTimeout(r, 30));
  assert(frame.style.getPropertyValue('--tilt-x') === '', 'mode off clears frame vars');

  // Reduced motion: no var writes even in tilt.
  const dr = await makeDeck({ reduce: true });
  dr.window.PremiumPresentations.set3dMode('tilt');
  const docr = dr.window.document;
  docr.getElementById('slide-1').classList.add('visible');
  const mv = new dr.window.Event('pointermove');
  mv.clientX = 200; mv.clientY = 200;
  docr.dispatchEvent(mv);
  await new Promise((r) => setTimeout(r, 50));
  const framer = docr.querySelector('.slide.visible .slide-3d-frame');
  assert(framer && framer.style.getPropertyValue('--tilt-x') === '', 'reduced motion: no tilt var writes');
}

console.log('Test: CSS contract');
{
  const components = readFileSync(join(SHARED, 'premium-components.css'), 'utf8');
  const deck = readFileSync(join(SHARED, 'premium-deck.css'), 'utf8');
  const extras = readFileSync(join(SHARED, 'premium-extras.css'), 'utf8');

  const depthIdx = components.indexOf('html[data-3d="depth"]');
  assert(depthIdx !== -1, 'depth rules exist in premium-components.css');
  // Anchor on selectors that never appear inside the 3D section (the section
  // itself references bare component classes like .live-flow__row).
  const lastComponentIdx = Math.max(components.lastIndexOf('.live-flow__row--stack'), components.lastIndexOf('.terminal-window__body'));
  assert(depthIdx > lastComponentIdx, 'depth section placed after component rules');
  assert(/html\[data-3d="depth"\] \.live-flow__row\s*\{[^}]*preserve-3d/.test(components.slice(depthIdx)), 'intermediate containers preserve 3D so nested tiers render');
  assert(/html\[data-3d="tilt"\] \.slide\.visible \.slide-3d-frame/.test(components), 'tilt targets the frame, not .slide');
  assert(!/html\[data-3d="tilt"\] \.slide\.visible\s*\{[^}]*transform:/.test(components), 'tilt never transforms .slide itself');
  assert(/\[data-flat\]/.test(components), 'data-flat opt-out present');

  const frameBlock = deck.match(/\.slide-3d-frame\s*\{[^}]*\}/);
  assert(!!frameBlock && /display:\s*flex/.test(frameBlock[0]) && !/display:\s*contents/.test(frameBlock[0]), 'frame is a real flex box in all modes (no display: contents)');

  assert(/body\.print-pdf \.slide-3d-frame/.test(extras), 'print-pdf flatten present');
  const mediaPrint = extras.slice(extras.indexOf('@media print'));
  assert(/html\[data-3d\] \.slide-3d-frame/.test(mediaPrint), 'raw @media print flatten present');

  const presenter = readFileSync(join(SHARED, 'premium-presenter.js'), 'utf8');
  assert(/parallax\.toggle.*toggleParallax/.test(presenter), 'presenter parallax.toggle routes to compat wrapper');
  assert(/mode3d\.cycle/.test(presenter) && /Digit3/.test(presenter), 'presenter popup uses Digit3 + mode3d.cycle');
}

console.log(failures === 0 ? '\nAll 3D mode tests passed' : `\n${failures} test(s) FAILED`);
process.exit(failures === 0 ? 0 : 1);
