// Quick verification: does the controller actually run when the bundle loads?
import { JSDOM } from 'jsdom';
import { readFileSync } from 'fs';

const bundle = process.argv[2] || 'assets/decks/vector-databases/vector-databases-slides.linked.html';
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
});

setTimeout(() => {
  const has = typeof dom.window.PremiumController;
  const state = has === 'object' ? dom.window.PremiumController.getState() : null;
  console.log('bundle:', bundle);
  console.log('typeof window.PremiumController:', has);
  console.log('state:', state);
  console.log('has isLocalOwner:', has === 'object' && typeof dom.window.PremiumController.isLocalOwner);
  process.exit(0);
}, 500);
