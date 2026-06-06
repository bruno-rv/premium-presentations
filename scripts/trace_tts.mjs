// Trace TTS follow with all the right stubs.
import { JSDOM } from 'jsdom';
import { readFileSync } from 'fs';

const bundle = 'decks/vector-databases/vector-databases-slides.linked.html';

const dom = new JSDOM(readFileSync(bundle, 'utf8'), {
  url: 'http://localhost/deck.html',
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  beforeParse(window) {
    const fakeRect = { x: 0, y: 0, width: 1280, height: 720 };
    window.SVGElement.prototype.getBBox = function () {
      return fakeRect;
    };
    if (window.SVGPathElement && window.SVGPathElement.prototype) {
      window.SVGPathElement.prototype.getTotalLength = function () { return 1000; };
      window.SVGPathElement.prototype.getPointAtLength = function () { return { x: 0, y: 0 }; };
    }
    // SVGSVGElement.viewBox.baseVal (used by premium-journey.js buildWaypoints)
    Object.defineProperty(window.SVGSVGElement.prototype, 'viewBox', {
      configurable: true,
      get() { return { baseVal: fakeRect, animVal: fakeRect }; },
    });
    window.IntersectionObserver = class { constructor() {} observe() {} unobserve() {} disconnect() {} };
    window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} });
    window.requestAnimationFrame = (cb) => setTimeout(cb, 16);
    window.cancelAnimationFrame = (id) => clearTimeout(id);
    window.HTMLElement.prototype.scrollIntoView = function () {};
    // Fake speechSynthesis
    window.speechSynthesis = {
      speak() { window.__events.push('speak'); },
      cancel() { window.__events.push('cancel'); },
      getVoices() { return []; },
    };
    window.__events = [];
  },
});

// Wait for scripts to execute
await new Promise((r) => setTimeout(r, 500));

// Force-instrument: wrap new SlideEngine
const origLog = console.log;
console.log('--- before any patches ---');
console.log('document.readyState:', dom.window.document.readyState);
console.log('typeof SlideEngine:', typeof dom.window.SlideEngine);
console.log('typeof PremiumTts:', typeof dom.window.PremiumTts);
console.log('typeof PremiumDeckControls:', typeof dom.window.PremiumDeckControls);

// Listen for errors
const errors = [];
dom.window.addEventListener('error', (e) => errors.push(e.error?.message || e.message));

console.log('typeof PremiumTts:', typeof dom.window.PremiumTts);
console.log('typeof PremiumController:', typeof dom.window.PremiumController);
console.log('typeof PremiumDeckControls:', typeof dom.window.PremiumDeckControls);
console.log('typeof window.initPremiumJourney:', typeof dom.window.initPremiumJourney);
console.log('typeof window.SlideEngine:', typeof dom.window.SlideEngine);

const slides = dom.window.document.querySelectorAll('#deck .slide');
console.log('slide count:', slides.length);
console.log('errors during init:', errors.slice(0, 5));

if (typeof dom.window.PremiumDeckControls === 'undefined') {
  console.log('\n!! SlideEngine never initialized. Forcing it now...');
  // slide-engine.js code is in the bundle; load it manually
  const slideEngineJs = readFileSync('shared/slide-engine.js', 'utf8');
  dom.window.eval(slideEngineJs);
  // And init controller
  const controllerJs = readFileSync('shared/premium-controller.js', 'utf8');
  dom.window.eval(controllerJs);
  dom.window.eval('new SlideEngine()');
  await new Promise((r) => setTimeout(r, 200));
  console.log('typeof PremiumDeckControls after manual init:', typeof dom.window.PremiumDeckControls);
}

console.log('\n--- Test 1: Mark slide 0 visible + Listen ---');
slides[0].classList.add('visible');
dom.window.__events.length = 0;
dom.window.PremiumTts.play();
await new Promise((r) => setTimeout(r, 50));
console.log('events:', dom.window.__events);
console.log('isOn:', dom.window.PremiumTts.isOn());

console.log('\n--- Test 2: Navigate to slide 1 ---');
dom.window.__events.length = 0;
slides[0].classList.remove('visible');
slides[1].classList.add('visible');
dom.window.dispatchEvent(new dom.window.CustomEvent('premium:slidechange', { detail: { index: 1 } }));
await new Promise((r) => setTimeout(r, 100));
console.log('events:', dom.window.__events);

console.log('\n--- Test 3: Navigate to slide 2 ---');
dom.window.__events.length = 0;
slides[1].classList.remove('visible');
slides[2].classList.add('visible');
dom.window.dispatchEvent(new dom.window.CustomEvent('premium:slidechange', { detail: { index: 2 } }));
await new Promise((r) => setTimeout(r, 100));
console.log('events:', dom.window.__events);

console.log('\n--- Test 4: Stop ---');
dom.window.__events.length = 0;
dom.window.PremiumTts.stop();
console.log('events:', dom.window.__events);
console.log('isOn after stop:', dom.window.PremiumTts.isOn());

process.exit(0);
