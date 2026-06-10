// Quick verification: does the controller actually run when the bundle loads?
import { JSDOM } from 'jsdom';
import { readFileSync } from 'fs';

const bundle = process.argv[2];
if (!bundle) {
  console.error('Usage: node scripts/tests/verify_bundle.mjs assets/decks/<slug>/<slug>-slides.html');
  process.exit(2);
}
const html = readFileSync(bundle, 'utf8');
const mermaidRuntimeCount = (html.match(/\/\*\s*---\s*premium-mermaid\s+\(inlined\)\s*---\s*\*\//g) || []).length;

if (mermaidRuntimeCount > 1) {
  console.error(`bundle: ${bundle}`);
  console.error(`duplicate premium-mermaid runtime blocks: ${mermaidRuntimeCount}`);
  process.exit(1);
}

const dom = new JSDOM(html, {
  url: 'http://localhost/deck.html',
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  beforeParse(window) {
    window.__bundleErrors = [];
    window.addEventListener('error', (event) => {
      window.__bundleErrors.push(event.error?.stack || event.error?.message || event.message);
    });
    window.addEventListener('unhandledrejection', (event) => {
      window.__bundleErrors.push(event.reason?.stack || event.reason?.message || String(event.reason));
    });
    window.IntersectionObserver = class {
      constructor() {}
      observe() {}
      unobserve() {}
      disconnect() {}
    };
    window.matchMedia = () => ({
      matches: false,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
    });
    window.requestAnimationFrame = (cb) => setTimeout(cb, 16);
    window.cancelAnimationFrame = (id) => clearTimeout(id);
    window.HTMLElement.prototype.scrollIntoView = function () {};
    if (window.SVGElement) {
      window.SVGElement.prototype.getBBox = function () {
        return { x: 0, y: 0, width: 1280, height: 720 };
      };
    }
  },
});

setTimeout(() => {
  const has = typeof dom.window.PremiumController;
  const state = has === 'object' ? dom.window.PremiumController.getState() : null;
  const runtimeErrors = dom.window.__bundleErrors || [];
  console.log('bundle:', bundle);
  console.log('typeof window.PremiumController:', has);
  console.log('state:', state);
  console.log('has isLocalOwner:', has === 'object' && typeof dom.window.PremiumController.isLocalOwner);
  if (runtimeErrors.length > 0) {
    console.error('runtime errors:', runtimeErrors.slice(0, 3));
    process.exit(1);
  }
  if (has !== 'object') {
    process.exit(1);
  }
  process.exit(0);
}, 500);
