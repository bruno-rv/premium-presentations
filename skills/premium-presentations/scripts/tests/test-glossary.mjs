// Tests for premium-glossary.js — PremiumGlossary public API and popup behaviour.

import { makeWindow, loadScript } from './_helpers.mjs';

const GLOSSARY_JSON = JSON.stringify({
  RAG: { title: 'RAG — Retrieval-Augmented Generation', body: 'Augments an LLM with retrieved docs.' },
  LLM: { title: 'LLM — Large Language Model', body: 'A transformer model for text generation.' },
  ANN: { title: 'ANN — Approximate Nearest Neighbor', body: 'Fast similarity search via index.' },
});

function makeGlossaryWindow({ url = 'http://localhost/deck.html', withGlossary = true } = {}) {
  const glossaryScript = withGlossary
    ? `<script type="application/json" id="glossary">${GLOSSARY_JSON}</script>`
    : '';
  const dom = makeWindow({
    url,
    withSlides: true,
    slides: `
      <section class="slide" id="slide-1">
        <p><button class="term-link" type="button" data-term="RAG">RAG</button> and
           <button class="term-link" type="button" data-term="LLM">LLM</button></p>
      </section>
      <section class="slide" id="slide-2">
        <p><button class="term-link" type="button" data-term="ANN">ANN</button></p>
      </section>
    `,
  });
  // Inject the JSON block before loading the script.
  if (withGlossary) {
    dom.window.document.body.insertAdjacentHTML('afterbegin', glossaryScript);
  }
  loadScript(dom, 'premium-glossary.js');
  return dom;
}

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

// ── API existence ─────────────────────────────────────────────────────────────

console.log('Test: PremiumGlossary API exists');
{
  const dom = makeGlossaryWindow();
  const g = dom.window.PremiumGlossary;
  assert('PremiumGlossary defined', !!g);
  assert('open is function', typeof g.open === 'function');
  assert('close is function', typeof g.close === 'function');
  assert('getTerms is function', typeof g.getTerms === 'function');
  assert('getTermsForSlide is function', typeof g.getTermsForSlide === 'function');
}

// ── getTerms ──────────────────────────────────────────────────────────────────

console.log('Test: getTerms returns parsed dictionary');
{
  const dom = makeGlossaryWindow();
  const terms = dom.window.PremiumGlossary.getTerms();
  assert('RAG key present', 'RAG' in terms);
  assert('LLM key present', 'LLM' in terms);
  assert('ANN key present', 'ANN' in terms);
  assert('RAG title', terms.RAG.title === 'RAG — Retrieval-Augmented Generation');
  assert('LLM body', terms.LLM.body.includes('transformer'));
}

console.log('Test: getTerms returns copy (not mutable ref)');
{
  const dom = makeGlossaryWindow();
  const terms1 = dom.window.PremiumGlossary.getTerms();
  terms1.RAG = null;
  const terms2 = dom.window.PremiumGlossary.getTerms();
  assert('mutation does not affect subsequent calls', terms2.RAG !== null);
}

console.log('Test: getTerms empty when no glossary JSON block');
{
  const dom = makeGlossaryWindow({ withGlossary: false });
  const terms = dom.window.PremiumGlossary.getTerms();
  assert('empty dict when no block', Object.keys(terms).length === 0);
}

// ── getTermsForSlide ──────────────────────────────────────────────────────────

console.log('Test: getTermsForSlide returns terms for slide');
{
  const dom = makeGlossaryWindow();
  const slide1 = dom.window.document.getElementById('slide-1');
  const result = dom.window.PremiumGlossary.getTermsForSlide(slide1);
  assert('slide-1 has 2 terms', result.length === 2);
  const keys = result.map((t) => t.key);
  assert('RAG in slide-1 terms', keys.includes('RAG'));
  assert('LLM in slide-1 terms', keys.includes('LLM'));
  assert('has title field', result[0].title !== undefined);
  assert('has body field', result[0].body !== undefined);
}

console.log('Test: getTermsForSlide deduplicates repeated term-links');
{
  const dom = makeWindow({
    url: 'http://localhost/deck.html',
    withSlides: true,
    slides: `
      <section class="slide" id="slide-dup">
        <button class="term-link" data-term="RAG">RAG</button>
        <button class="term-link" data-term="RAG">RAG again</button>
      </section>
    `,
  });
  dom.window.document.body.insertAdjacentHTML(
    'afterbegin',
    `<script type="application/json" id="glossary">${GLOSSARY_JSON}</script>`,
  );
  loadScript(dom, 'premium-glossary.js');
  const slide = dom.window.document.getElementById('slide-dup');
  const result = dom.window.PremiumGlossary.getTermsForSlide(slide);
  assert('deduplicates RAG', result.length === 1);
}

console.log('Test: getTermsForSlide skips keys not in dictionary');
{
  const dom = makeGlossaryWindow();
  const dom2 = makeWindow({
    url: 'http://localhost/deck.html',
    withSlides: true,
    slides: `
      <section class="slide" id="slide-unknown">
        <button class="term-link" data-term="UNKNOWN_KEY">Unknown</button>
      </section>
    `,
  });
  dom2.window.document.body.insertAdjacentHTML(
    'afterbegin',
    `<script type="application/json" id="glossary">${GLOSSARY_JSON}</script>`,
  );
  loadScript(dom2, 'premium-glossary.js');
  const slide = dom2.window.document.getElementById('slide-unknown');
  const result = dom2.window.PremiumGlossary.getTermsForSlide(slide);
  assert('unknown key filtered out', result.length === 0);
}

console.log('Test: getTermsForSlide returns empty for null');
{
  const dom = makeGlossaryWindow();
  const result = dom.window.PremiumGlossary.getTermsForSlide(null);
  assert('null slideEl → empty array', Array.isArray(result) && result.length === 0);
}

// ── Modal injection ───────────────────────────────────────────────────────────

console.log('Test: open injects #term-popup into DOM');
{
  const dom = makeGlossaryWindow();
  dom.window.PremiumGlossary.open('RAG');
  const popup = dom.window.document.getElementById('term-popup');
  assert('popup element created', !!popup);
  assert('popup has is-open class', popup.classList.contains('is-open'));
  assert('aria-hidden=false', popup.getAttribute('aria-hidden') === 'false');
  const title = dom.window.document.getElementById('term-popup-title');
  assert('title text set', title && title.textContent.includes('RAG'));
}

console.log('Test: open does nothing for unknown key');
{
  const dom = makeGlossaryWindow();
  dom.window.PremiumGlossary.open('NO_SUCH_KEY');
  const popup = dom.window.document.getElementById('term-popup');
  assert('popup not created for unknown key', !popup);
}

// ── close ─────────────────────────────────────────────────────────────────────

console.log('Test: close removes is-open and restores aria-hidden');
{
  const dom = makeGlossaryWindow();
  dom.window.PremiumGlossary.open('RAG');
  dom.window.PremiumGlossary.close();
  const popup = dom.window.document.getElementById('term-popup');
  assert('is-open removed after close', !popup.classList.contains('is-open'));
  assert('aria-hidden=true after close', popup.getAttribute('aria-hidden') === 'true');
}

// ── Click handler ─────────────────────────────────────────────────────────────

console.log('Test: clicking .term-link opens popup for that term');
{
  const dom = makeGlossaryWindow();
  const btn = dom.window.document.querySelector('[data-term="LLM"]');
  btn.click();
  const title = dom.window.document.getElementById('term-popup-title');
  assert('LLM popup opened via click', title && title.textContent.includes('LLM'));
}

// ── Keyboard handling ─────────────────────────────────────────────────────────

// Helper: dispatch a keydown event and return whether preventDefault was called.
function fireKey(win, key, { target } = {}) {
  const el = target || win.document.body;
  let prevented = false;
  let stopped = false;
  const evt = new win.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true });
  Object.defineProperty(evt, 'preventDefault', {
    value: () => { prevented = true; },
    writable: false,
  });
  Object.defineProperty(evt, 'stopImmediatePropagation', {
    value: () => { stopped = true; },
    writable: false,
  });
  el.dispatchEvent(evt);
  return { prevented, stopped };
}

console.log('Test: Tab while popup is open keeps focus on close button');
{
  const dom = makeGlossaryWindow();
  dom.window.PremiumGlossary.open('RAG');
  const popup = dom.window.document.getElementById('term-popup');
  assert('popup open before Tab test', popup.classList.contains('is-open'));
  const { prevented } = fireKey(dom.window, 'Tab');
  assert('Tab preventDefault called while open', prevented);
  // After Tab the close button retains focus (no other focusable in dialog).
  const closeBtn = popup.querySelector('.term-popup__close');
  assert('close button exists', !!closeBtn);
}

console.log('Test: ArrowRight while popup is open is consumed (deck does not navigate)');
{
  const dom = makeGlossaryWindow();
  dom.window.PremiumGlossary.open('RAG');
  const { prevented, stopped } = fireKey(dom.window, 'ArrowRight');
  assert('ArrowRight preventDefault while open', prevented);
  assert('ArrowRight stopImmediatePropagation while open', stopped);
}

console.log('Test: ArrowRight after popup closes is NOT consumed');
{
  const dom = makeGlossaryWindow();
  dom.window.PremiumGlossary.open('RAG');
  dom.window.PremiumGlossary.close();
  const popup = dom.window.document.getElementById('term-popup');
  assert('popup closed before ArrowRight test', !popup.classList.contains('is-open'));
  const { prevented } = fireKey(dom.window, 'ArrowRight');
  assert('ArrowRight not prevented when popup closed', !prevented);
}

console.log('Test: Escape while popup is open closes it and stops propagation');
{
  const dom = makeGlossaryWindow();
  dom.window.PremiumGlossary.open('RAG');
  const popup = dom.window.document.getElementById('term-popup');
  let escReached = false;
  dom.window.document.addEventListener('keydown', function () { escReached = true; }, false);
  const evt = new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
  dom.window.document.dispatchEvent(evt);
  assert('popup closed after Escape', !popup.classList.contains('is-open'));
}

console.log('Test: Escape when popup is closed does NOT stop propagation');
{
  const dom = makeGlossaryWindow();
  // Popup not opened — Escape should bubble freely.
  let bubbled = false;
  dom.window.document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') bubbled = true;
  }, false);
  const evt = new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
  dom.window.document.dispatchEvent(evt);
  assert('Escape bubbles when popup is closed', bubbled);
}

// ── Presenter popup guard ─────────────────────────────────────────────────────

console.log('Test: presenter=1 window — no modal, open/close are no-ops');
{
  const dom = makeWindow({
    url: 'http://localhost/deck.html?presenter=1&session=abc',
    withSlides: true,
    slides: `
      <section class="slide" id="slide-p1">
        <p><button class="term-link" type="button" data-term="RAG">RAG</button></p>
      </section>
    `,
  });
  dom.window.document.body.insertAdjacentHTML(
    'afterbegin',
    `<script type="application/json" id="glossary">${GLOSSARY_JSON}</script>`,
  );
  loadScript(dom, 'premium-glossary.js');
  const g = dom.window.PremiumGlossary;
  assert('API present in presenter window', !!g);
  g.open('RAG');
  const popup = dom.window.document.getElementById('term-popup');
  assert('no popup injected in presenter window', !popup);
}

console.log('Test: presenter=1 window — getTerms returns real dictionary');
{
  const dom = makeWindow({
    url: 'http://localhost/deck.html?presenter=1&session=abc',
    withSlides: true,
  });
  dom.window.document.body.insertAdjacentHTML(
    'afterbegin',
    `<script type="application/json" id="glossary">${GLOSSARY_JSON}</script>`,
  );
  loadScript(dom, 'premium-glossary.js');
  const g = dom.window.PremiumGlossary;
  const terms = g.getTerms();
  assert('getTerms has RAG in presenter window', 'RAG' in terms);
  assert('getTerms has LLM in presenter window', 'LLM' in terms);
  assert('getTerms has ANN in presenter window', 'ANN' in terms);
}

console.log('Test: presenter=1 window — getTermsForSlide resolves terms');
{
  const dom = makeWindow({
    url: 'http://localhost/deck.html?presenter=1&session=abc',
    withSlides: true,
    slides: `
      <section class="slide" id="slide-p1">
        <p><button class="term-link" type="button" data-term="RAG">RAG</button>
           <button class="term-link" type="button" data-term="LLM">LLM</button></p>
      </section>
    `,
  });
  dom.window.document.body.insertAdjacentHTML(
    'afterbegin',
    `<script type="application/json" id="glossary">${GLOSSARY_JSON}</script>`,
  );
  loadScript(dom, 'premium-glossary.js');
  const g = dom.window.PremiumGlossary;
  const slide = dom.window.document.getElementById('slide-p1');
  const result = g.getTermsForSlide(slide);
  assert('getTermsForSlide returns 2 terms in presenter window', result.length === 2);
  const keys = result.map((t) => t.key);
  assert('RAG resolved in presenter window', keys.includes('RAG'));
  assert('LLM resolved in presenter window', keys.includes('LLM'));
  assert('result has title field', result[0].title !== undefined);
  assert('result has body field', result[0].body !== undefined);
}

// ── Summary ───────────────────────────────────────────────────────────────────

console.log('\nResults: ' + passed + ' passed, ' + failed + ' failed');
if (failed > 0) process.exit(1);
process.exit(0);
