import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';
import { JSDOM } from 'jsdom';
import { SHARED } from './_helpers.mjs';

function loadDesignPower(dom) {
  dom.window.eval(readFileSync(join(SHARED, 'premium-design-power.js'), 'utf8'));
  return dom.window.PremiumDesignPower;
}

function makeDom(body = '', htmlAttrs = '') {
  return new JSDOM(
    `<!doctype html><html ${htmlAttrs}><head></head><body>${body}</body></html>`,
    { url: 'http://localhost/deck.html', runScripts: 'outside-only', pretendToBeVisual: true },
  );
}

test('theme composer sanitizes theme ids and applies portable theme tokens', () => {
  const dom = makeDom();
  const api = loadDesignPower(dom);

  const css = api.themeComposer.buildThemeCss({
    id: 'Focus Lab!',
    label: 'Focus Lab',
    bg: '#101820',
    text: '#f7fafc',
    accent: '#4a9eff',
    surface: '#182838',
    fontDisplay: 'system-ui',
    fontBody: 'Arial',
  });

  assert.match(css, /html\[data-theme="focus-lab"\]/);
  assert.match(css, /--bg:\s*#101820/);
  assert.doesNotMatch(css, /Focus Lab!/);

  api.themeComposer.applyTheme({
    id: 'Focus Lab!',
    bg: '#101820',
    text: '#f7fafc',
    accent: '#4a9eff',
    surface: '#182838',
  }, dom.window.document);

  assert.equal(dom.window.document.documentElement.dataset.theme, 'focus-lab');
  assert.ok(dom.window.document.getElementById('premium-theme-composer-focus-lab'));
});

test('motion profiles apply deck-level motion tokens and default 3D modes', () => {
  const dom = makeDom('', 'data-3d="off"');
  const api = loadDesignPower(dom);

  api.motionProfiles.apply('cinematic', dom.window.document);

  const root = dom.window.document.documentElement;
  assert.equal(root.dataset.motionProfile, 'cinematic');
  assert.equal(root.dataset['3d'], 'depth');
  assert.equal(root.style.getPropertyValue('--motion-reveal-ms'), '760ms');
  assert.equal(root.style.getPropertyValue('--motion-depth'), '1.35');
});

test('visual density checker reports crowded slides with actionable warnings', () => {
  const dom = makeDom(`
    <section class="slide">
      <h2>Too much at once</h2>
      <p>${'word '.repeat(145)}</p>
      ${Array.from({ length: 8 }, (_, i) => `<p class="reveal">Point ${i + 1}</p>`).join('')}
      <div class="stats-row">
        ${Array.from({ length: 7 }, (_, i) => `<div class="stat-card">Metric ${i + 1}</div>`).join('')}
      </div>
    </section>
  `);
  const api = loadDesignPower(dom);

  const report = api.density.analyzeSlide(dom.window.document.querySelector('.slide'));

  assert.equal(report.level, 'high');
  assert.ok(report.metrics.words > 140);
  assert.ok(report.warnings.some((w) => /shorten text/i.test(w.message)));
  assert.ok(report.warnings.some((w) => /reveals/i.test(w.message)));
  assert.ok(report.warnings.some((w) => /cards/i.test(w.message)));
});

test('layout variants and component playground render reusable slide blocks', () => {
  const dom = makeDom();
  const api = loadDesignPower(dom);

  const layout = api.layouts.render('decision-matrix', {
    title: 'Choose a path',
    columns: ['Impact', 'Risk', 'Effort'],
    rows: [
      ['Studio', 'High', 'Low', 'Medium'],
      ['Presenter', 'Medium', 'Low', 'Low'],
    ],
  });
  const component = api.components.render('checklist', {
    title: 'Design gate',
    items: ['Theme tokens', 'Motion profile', 'Density pass'],
  });

  assert.match(layout, /class="dp-layout dp-layout--decision-matrix"/);
  assert.match(layout, /Choose a path/);
  assert.match(component, /class="dp-component dp-component--checklist"/);
  assert.match(component, /Density pass/);
});

test('data visualization renderer supports trend, funnel, heatmap, and sankey blocks', () => {
  const dom = makeDom();
  const api = loadDesignPower(dom);

  const trend = api.dataViz.render('line', { title: 'Adoption', values: [2, 4, 7, 11] });
  const funnel = api.dataViz.render('funnel', { title: 'Pipeline', values: [100, 64, 33] });
  const heatmap = api.dataViz.render('heatmap', { title: 'Fit', rows: [['A', 1, 3], ['B', 2, 4]] });
  const sankey = api.dataViz.render('sankey', { title: 'Flow', links: [['Idea', 'Deck', 4], ['Deck', 'Talk', 3]] });

  assert.match(trend, /class="dp-viz dp-viz--line"/);
  assert.match(trend, /<svg/);
  assert.match(funnel, /class="dp-viz dp-viz--funnel"/);
  assert.match(heatmap, /class="dp-viz dp-viz--heatmap"/);
  assert.match(sankey, /class="dp-viz dp-viz--sankey"/);
});

test('visual asset system inventories assets and flags non-portable references', () => {
  const dom = makeDom(`
    <section class="slide" data-visual-asset="hero" data-asset-src="data:image/webp;base64,abc"></section>
    <img src="https://example.com/remote.png" alt="remote">
    <img src="./sidecar.png" alt="relative">
  `);
  const api = loadDesignPower(dom);

  const report = api.assets.audit(dom.window.document);

  assert.equal(report.assets.length, 3);
  assert.ok(report.warnings.some((w) => /remote/i.test(w.message)));
  assert.ok(report.warnings.some((w) => /relative/i.test(w.message)));
});

test('design-power CSS prevents timeline text from collapsing into the number column', () => {
  const css = readFileSync(join(SHARED, 'premium-design-power.css'), 'utf8');

  assert.match(css, /\.dp-component--timeline li p\s*\{[^}]*grid-column:\s*2\b/s);
  assert.match(css, /\.dp-component--timeline li span\s*\{[^}]*grid-row:\s*1\s*\/\s*3/s);
});

test('deck CSS gives bare .split a stable two-panel layout', () => {
  const css = readFileSync(join(SHARED, 'premium-deck.css'), 'utf8');

  assert.match(css, /\.slide-3d-frame\s*>\s*\.split,\s*\.slide\s*>\s*\.split\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(0,\s*1fr\)/s);
  assert.match(css, /@media \(max-width:\s*900px\)[\s\S]*\.slide-3d-frame\s*>\s*\.split,\s*\.slide\s*>\s*\.split\s*\{[^}]*grid-template-columns:\s*1fr/s);
});
