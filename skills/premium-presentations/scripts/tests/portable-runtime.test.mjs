import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');

function read(path) {
  return readFileSync(resolve(root, path), 'utf8');
}

function listRuntimeSources() {
  const sources = [];
  for (const dir of ['assets/shared', 'assets/templates', 'assets/studio']) {
    for (const entry of readdirSync(resolve(root, dir), { withFileTypes: true })) {
      if (!entry.isFile()) continue;
      if (!/\.(css|html|js|svg)$/.test(entry.name)) continue;
      sources.push(`${dir}/${entry.name}`);
    }
  }
  return sources;
}

const portableSources = listRuntimeSources();
const externalUrl = /https?:\/\/(?!www\.w3\.org\/(?:1999\/xhtml|2000\/svg)\b)/i;

test('runtime assets and templates do not require network URLs', () => {
  for (const source of portableSources) {
    assert.doesNotMatch(
      read(source),
      externalUrl,
      `${source} should not require external network dependencies`,
    );
  }
});

test('red chrome inlines its mark instead of referencing a repo file', () => {
  const redChrome = read('assets/shared/premium-red-chrome.js');
  assert.doesNotMatch(redChrome, /red-mark\.svg/i);
  assert.doesNotMatch(redChrome, /src=["'][^"']*shared\/assets/i);
  assert.match(redChrome, /RED_MARK_SVG/);
});

test('deck templates do not point at a missing default cover image', () => {
  for (const source of portableSources.filter((name) => name.startsWith('assets/templates/'))) {
    assert.doesNotMatch(
      read(source),
      /og-cover\.png/i,
      `${source} should not reference og-cover.png unless the scaffold creates it`,
    );
  }
});

test('PremiumSearch builds and queries a local index without MiniSearch', async () => {
  const searchScript = read('assets/shared/premium-search.js');
  const dom = new JSDOM(
    `<!doctype html><html><body>
      <main id="deck">
        <section class="slide" id="s1">
          <h2 class="slide__heading">RAG retrieves evidence</h2>
          <p>Vector databases ground model answers.</p>
        </section>
        <section class="slide" id="s2">
          <h2 class="slide__heading">Fine tuning changes weights</h2>
          <p>Training changes model parameters.</p>
        </section>
      </main>
      <script>${searchScript}</script>
    </body></html>`,
    { url: 'http://localhost/deck.html', runScripts: 'dangerously', pretendToBeVisual: true },
  );

  await dom.window.PremiumSearch.rebuild();

  const results = dom.window.PremiumSearch.query('vector evidence');
  assert.equal(results[0].slideId, 's1');
  assert.equal(results[0].num, 1);
});

test('PremiumSearch escapes slide text before rendering result HTML', async () => {
  const searchScript = read('assets/shared/premium-search.js');
  const dom = new JSDOM(
    `<!doctype html><html><body>
      <main id="deck">
        <section class="slide" id="s1">
          <h2 class="slide__heading">Vector safety</h2>
          <p>&lt;img src=x onerror="window.__hit=1"&gt; vector payload</p>
        </section>
      </main>
      <script>${searchScript}</script>
    </body></html>`,
    { url: 'http://localhost/deck.html', runScripts: 'dangerously', pretendToBeVisual: true },
  );

  dom.window.PremiumSearch.open();
  const input = dom.window.document.querySelector('.premium-search-input');
  input.value = 'vector';
  input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));

  const result = dom.window.document.querySelector('.premium-search-result__body');
  assert.ok(result);
  assert.equal(result.querySelector('img'), null);
  assert.match(result.innerHTML, /&lt;img/);
});

test('PremiumSearch Enter on empty results does not jump to slide 1', async () => {
  const searchScript = read('assets/shared/premium-search.js');
  const dom = new JSDOM(
    `<!doctype html><html><body>
      <main id="deck">
        <section class="slide" id="s1"><h2 class="slide__heading">Only slide</h2></section>
      </main>
      <script>${searchScript}</script>
    </body></html>`,
    { url: 'http://localhost/deck.html', runScripts: 'dangerously', pretendToBeVisual: true },
  );

  let scrolled = false;
  dom.window.HTMLElement.prototype.scrollIntoView = () => { scrolled = true; };
  dom.window.PremiumSearch.open();
  const input = dom.window.document.querySelector('.premium-search-input');
  input.value = 'notfound';
  input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  input.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));

  assert.equal(scrolled, false);
});

test('PremiumExport rejects failed PNG export and keeps XML-safe serialization path', async () => {
  const exportScript = read('assets/shared/premium-og-cover.js');
  const dom = new JSDOM(
    `<!doctype html><html><body>
      <div class="premium-controls"></div>
      <main id="deck">
        <section class="slide visible" id="s1"><h2>Title<br>Break</h2></section>
      </main>
      <script>${exportScript}</script>
    </body></html>`,
    {
      url: 'http://localhost/deck.html',
      runScripts: 'dangerously',
      pretendToBeVisual: true,
      beforeParse(window) {
        window.console.error = () => {};
        class FailingImage {
          set src(_value) {
            setTimeout(() => this.onerror?.(new Error('decode failed')), 0);
          }
        }
        window.Image = FailingImage;
      },
    },
  );

  assert.match(exportScript, /XMLSerializer/);
  await assert.rejects(
    dom.window.PremiumExport.exportSlidePng(dom.window.document.getElementById('s1')),
    /image decode failed/i,
  );
});
