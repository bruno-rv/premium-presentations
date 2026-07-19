// Slide Budget grammar/serializer — the single JS counterpart to
// slide_spec.py's Python serializer. Both consume the same shared vectors in
// budget-vectors.json (PLAN.md Workstream A canonical rules) and must agree
// on every one.

import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { loadScript, makeWindow } from './_helpers.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const VECTORS = JSON.parse(readFileSync(join(HERE, 'budget-vectors.json'), 'utf8'));

function loadPresenter() {
  // Session-less window: init() no-ops (no sessionId) but
  // window.PremiumPresenterView is still assigned unconditionally.
  const dom = makeWindow({ url: 'http://localhost/deck.html', withSlides: false });
  loadScript(dom, 'premium-presenter.js');
  return dom.window.PremiumPresenterView;
}

test('validateBudgetMs accepts every msValid vector', () => {
  const view = loadPresenter();
  for (const { value, ms } of VECTORS.msValid) {
    assert.equal(view.validateBudgetMs(value), ms, `value=${value}`);
  }
});

test('validateBudgetMs rejects every msInvalid vector', () => {
  const view = loadPresenter();
  for (const { value, reason } of VECTORS.msInvalid) {
    assert.throws(() => view.validateBudgetMs(value), new RegExp('invalid_budget_ms'), `value=${JSON.stringify(value)} reason=${reason}`);
  }
});

test('formatBudgetMmss matches every mmssFromMs vector', () => {
  const view = loadPresenter();
  for (const { ms, mmss } of VECTORS.mmssFromMs) {
    assert.equal(view.formatBudgetMmss(ms), mmss, `ms=${ms}`);
  }
});

test('validateBudgetMmss accepts every mmssValid vector', () => {
  const view = loadPresenter();
  for (const { mmss, ms } of VECTORS.mmssValid) {
    assert.doesNotThrow(() => view.validateBudgetMmss(mmss, ms), `mmss=${mmss}`);
  }
});

test('validateBudgetMmss rejects every mmssInvalid vector', () => {
  const view = loadPresenter();
  for (const { mmss, reason } of VECTORS.mmssInvalid) {
    assert.throws(() => view.validateBudgetMmss(mmss, 50000), new RegExp('invalid_budget_mmss'), `mmss=${JSON.stringify(mmss)} reason=${reason}`);
  }
});

test('validateBudgetMmss rejects every mmssMsMismatch vector', () => {
  const view = loadPresenter();
  for (const { mmss, ms } of VECTORS.mmssMsMismatch) {
    assert.throws(() => view.validateBudgetMmss(mmss, ms), new RegExp('budget_mismatch'), `mmss=${mmss} ms=${ms}`);
  }
});
