import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');

function read(path) {
  return readFileSync(resolve(root, path), 'utf8');
}

function localHtmlLinks(htmlPath) {
  const html = read(htmlPath);
  const base = dirname(resolve(root, htmlPath));
  return [...html.matchAll(/<a\b[^>]*\bhref=["']([^"']+\.html)["'][^>]*>/gi)]
    .map((match) => match[1])
    .filter((href) => !/^(https?:)?\/\//i.test(href))
    .map((href) => resolve(base, href));
}

test('studio gallery links only to preview-safe HTML', () => {
  const linkedHtmlFiles = localHtmlLinks('assets/studio/index.html');
  assert.ok(linkedHtmlFiles.length > 0, 'expected assets/studio/index.html to link to local HTML');

  for (const absPath of linkedHtmlFiles) {
    const body = readFileSync(absPath, 'utf8');
    assert.doesNotMatch(
      body,
      /\{\{(?:THEME|TITLE|SHARED|BAR_RIGHT)\}\}/,
      `${absPath} should not expose raw scaffold placeholders from the studio gallery`,
    );
  }
});

test('theme visuals use the generic asset path', () => {
  const controlsScript = read('assets/shared/premium-controls.js');
  const manifest = JSON.parse(read('assets/shared/assets/theme-visuals/manifest.json'));
  const deprecatedPath = ['chatgpt', 'theme-visuals'].join('-');

  assert.match(controlsScript, /assets\/theme-visuals\//);
  assert.doesNotMatch(controlsScript, new RegExp(deprecatedPath));
  assert.ok(manifest.editorial.assets.some((asset) => asset.src === 'editorial-hero.webp'));
});

test('theme preference is scoped by deck path, not restored globally', async () => {
  const controlsScript = read('assets/shared/premium-controls.js');
  const dom = new JSDOM(
    `<!doctype html><html data-theme="warm" data-parallax="off"><head></head><body><section class="slide slide--title"></section><script>${controlsScript}</script></body></html>`,
    {
      url: 'http://localhost/assets/decks/generated/generated-slides.html',
      runScripts: 'dangerously',
      pretendToBeVisual: true,
      beforeParse(window) {
        window.localStorage.setItem('premium-theme', 'red');
      },
    },
  );

  await new Promise((resolveReady) => {
    dom.window.addEventListener('load', resolveReady, { once: true });
  });

  assert.equal(dom.window.document.documentElement.dataset.theme, 'warm');

  dom.window.PremiumPresentations.setTheme('editorial');

  assert.equal(
    dom.window.localStorage.getItem('premium-theme:/assets/decks/generated/generated-slides.html'),
    'editorial',
  );
  assert.equal(dom.window.localStorage.getItem('premium-theme'), 'red');
});

test('shared theme source avoids reported Impeccable anti-pattern motifs', () => {
  const css = read('assets/shared/premium-themes.css');

  assert.doesNotMatch(css, /background-clip:\s*text/i, 'gradient text should not be in source themes');
  assert.doesNotMatch(css, /-webkit-background-clip:\s*text/i, 'gradient text should not be in source themes');
  assert.doesNotMatch(css, /border-left:\s*[2-9]px/i, 'side-tab borders should not be in source themes');
});

test('motion avoids layout-property transitions in deck chrome', () => {
  const css = read('assets/shared/premium-deck.css');

  assert.doesNotMatch(css, /transition:[^;]*\bwidth\b/i, 'progress should avoid width transitions');
  assert.doesNotMatch(css, /transition:[^;]*\bmax-width\b/i, 'dot labels should avoid max-width transitions');
});

test('display typography has clipping guardrails', () => {
  const css = read('assets/shared/premium-deck.css');
  const displayBlock = css.match(/\.slide__display\s*\{[^}]+\}/)?.[0] ?? '';

  assert.match(displayBlock, /font-size:\s*clamp\(38px,\s*7\.5vw,\s*80px\)/);
  assert.match(displayBlock, /line-height:\s*1\.05/);
});

test('mobile controls meet touch target minimums', () => {
  const css = read('assets/shared/premium-deck.css');
  const mobileBlock = css.match(/@media \(max-width:\s*640px\)\s*\{[\s\S]+?\n\}/)?.[0] ?? '';

  assert.match(mobileBlock, /\.premium-controls-tab[\s\S]+min-height:\s*44px/);
  assert.match(mobileBlock, /\.premium-controls select,\s*\.premium-controls button[\s\S]+min-height:\s*44px/);
  assert.match(mobileBlock, /\.premium-controls__group[\s\S]+gap:\s*8px/);
});

test('theme font stacks avoid reported overused families and keep warm hierarchy split', () => {
  const files = [
    'assets/studio/index.html',
    'assets/templates/premium-base.html',
    'assets/templates/red-base.html',
    'assets/templates/warm-base.html',
    'assets/templates/editorial-base.html',
    'assets/templates/cupertino-base.html',
    'assets/templates/preview-editorial.html',
    'assets/templates/preview-warm.html',
    'assets/templates/preview-red.html',
    'assets/templates/preview-cupertino.html',
    'assets/templates/clawd-base.html',
    'assets/templates/preview-clawd.html',
    'assets/shared/premium-themes.css',
    'assets/shared/premium-controls.js',
    'assets/shared/premium-components.css',
  ];
  const overusedFonts = /Instrument(?:\+| )Serif|Fraunces|Montserrat|DM(?:\+| )Sans|Newsreader|font-family:\s*['"]Inter['"]/i;

  for (const file of files) {
    assert.doesNotMatch(read(file), overusedFonts, `${file} should avoid the reported overused theme fonts`);
  }

  const themes = read('assets/shared/premium-themes.css');
  const warmBlock = themes.match(/html\[data-theme="warm"\]\s*\{[^}]+\}/)?.[0] ?? '';
  const display = warmBlock.match(/--font-display:\s*([^;]+);/)?.[1]?.trim();
  const body = warmBlock.match(/--font-body:\s*([^;]+);/)?.[1]?.trim();

  assert.ok(display && body, 'warm theme should define display and body font stacks');
  assert.notEqual(display, body, 'warm theme display and body stacks should not be identical');
});

test('Clawd preview resolves six action assets with accessible metadata', () => {
  const previewPath = 'assets/templates/preview-clawd.html';
  const previewHtml = read(previewPath);
  const dom = new JSDOM(previewHtml);
  const cutouts = [...dom.window.document.querySelectorAll('.clawd-cutout')];
  const expectedActions = ['build', 'inspect', 'present', 'plan', 'test', 'handoff'];
  const assetRoot = resolve(root, 'assets/shared/assets/clawd');

  assert.equal(cutouts.length, expectedActions.length, 'Clawd preview should show six action cards');

  const actions = cutouts.map((cutout) => {
    const image = cutout.querySelector('img');
    const caption = cutout.querySelector('figcaption');

    assert.ok(image, 'each Clawd action card should include an image');
    assert.ok(image.alt.trim(), 'each Clawd action image should have non-empty alt text');
    assert.ok(caption?.textContent.trim(), 'each Clawd action image should have a non-empty caption');

    const imagePath = resolve(dirname(resolve(root, previewPath)), image.getAttribute('src'));
    assert.ok(imagePath.startsWith(`${assetRoot}/`), 'Clawd action images should stay in the Clawd asset directory');
    assert.ok(existsSync(imagePath), `Clawd action image should resolve: ${imagePath}`);

    return imagePath.slice(assetRoot.length + 1).replace(/^clawd-/, '').replace(/\.webp$/, '');
  });

  assert.deepEqual(actions, expectedActions);
});

test('Clawd preview keeps two action columns on compact screens', () => {
  const previewHtml = read('assets/templates/preview-clawd.html');
  const mobileBlock = previewHtml.match(/@media \(max-width:\s*700px\)\s*\{([\s\S]*?)\n\s*\}/)?.[1] ?? '';

  assert.match(
    mobileBlock,
    /\.clawd-cutouts\s*\{\s*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);\s*\}/,
    'compact Clawd previews should keep two columns to avoid mobile slide overflow',
  );
});
