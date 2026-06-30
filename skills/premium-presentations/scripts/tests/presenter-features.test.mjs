import assert from 'node:assert/strict';
import test from 'node:test';

import { FakeBC, installGlobalFakeBC, loadScript, makeWindow as makeBaseWindow } from './_helpers.mjs';

installGlobalFakeBC();

const FOUR_SLIDES = `
      <section class="slide" id="slide-1"><h1 class="slide__display">One</h1><aside class="notes">Talk about one.</aside></section>
      <section class="slide" id="slide-2"><h1 class="slide__display">Two</h1><aside class="notes">Talk about two.</aside></section>
      <section class="slide" id="slide-3"><h1 class="slide__display">Three</h1><aside class="notes">Talk about three.</aside></section>
      <section class="slide" id="slide-4"><h1 class="slide__display">Four</h1><aside class="notes">Talk about four.</aside></section>
`;

function makeWindow(options) {
  return makeBaseWindow({ slides: FOUR_SLIDES, bc: FakeBC, ...options });
}

function tick(ms = 20) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function setupPresenterPair({ now = 1_700_000_000_000 } = {}) {
  FakeBC.channels = new Map();

  const deck = makeWindow({ url: 'http://localhost/deck.html', focused: true });
  loadScript(deck, 'premium-controller.js');
  await tick(0);
  loadScript(deck, 'slide-engine.js');
  deck.window.eval('new SlideEngine();');
  const deckControls = deck.window.PremiumDeckControls;
  assert.ok(deckControls, 'deck controls should be available');

  loadScript(deck, 'premium-timer.js');
  loadScript(deck, 'premium-presenter.js');
  const deckSession = deck.window.document.documentElement.dataset.session;

  const popup = makeWindow({
    url: 'http://localhost/deck.html?presenter=1&session=' + deckSession,
    focused: true,
    withSlides: false,
  });
  popup.window.Date.now = () => now;
  loadScript(popup, 'premium-controller.js');
  await tick(0);
  loadScript(popup, 'premium-presenter.js');
  await tick(100);

  return {
    deck,
    popup,
    deckControls,
    setNow(value) {
      now = value;
      popup.window.Date.now = () => now;
    },
    advance(ms) {
      now += ms;
      popup.window.Date.now = () => now;
    },
  };
}

test('presenter popup renders a clickable slide timeline', async (t) => {
  const { deck, deckControls, popup } = await setupPresenterPair();
  t.after(() => {
    deck.window.close();
    popup.window.close();
  });

  const timeline = popup.window.document.getElementById('pp-timeline');
  assert.ok(timeline, 'presenter timeline should be mounted');

  const items = [...timeline.querySelectorAll('li[data-index]')];
  assert.equal(items.length, 4);
  assert.equal(items[0].dataset.state, 'current');
  assert.match(items[0].textContent, /One/);
  assert.match(items[1].textContent, /Two/);

  items[2].querySelector('button').click();
  await tick(100);

  assert.equal(deckControls.getState().index, 2);
  const updatedItems = [...timeline.querySelectorAll('li[data-index]')];
  assert.equal(updatedItems[2].dataset.state, 'current');
  assert.equal(updatedItems[0].dataset.state, 'past');
});

test('rehearsal mode tracks elapsed time per slide in the presenter timeline', async (t) => {
  const base = 1_700_000_000_000;
  const { deck, deckControls, popup, advance } = await setupPresenterPair({ now: base });
  t.after(() => {
    deck.window.close();
    popup.window.close();
  });

  const toggle = popup.window.document.getElementById('pp-rehearsal-toggle');
  const reset = popup.window.document.getElementById('pp-rehearsal-reset');
  const status = popup.window.document.getElementById('pp-rehearsal-status');
  assert.ok(toggle, 'rehearsal toggle should be mounted');
  assert.ok(reset, 'rehearsal reset should be mounted');
  assert.ok(status, 'rehearsal status should be mounted');

  toggle.click();
  assert.equal(toggle.textContent, 'Pause rehearsal');
  assert.match(status.textContent, /Rehearsing/);

  advance(61_000);
  deckControls.goTo(1);
  await tick(100);

  let firstItem = popup.window.document.querySelector('#pp-timeline li[data-index="0"]');
  let secondItem = popup.window.document.querySelector('#pp-timeline li[data-index="1"]');
  assert.match(firstItem.textContent, /actual 1:01/);
  assert.equal(firstItem.dataset.rehearsal, 'visited');
  assert.equal(secondItem.dataset.rehearsal, 'active');

  advance(30_000);
  toggle.click();
  assert.equal(toggle.textContent, 'Resume rehearsal');
  assert.match(status.textContent, /Paused/);
  secondItem = popup.window.document.querySelector('#pp-timeline li[data-index="1"]');
  assert.match(secondItem.textContent, /actual 0:30/);

  reset.click();
  assert.equal(toggle.textContent, 'Start rehearsal');
  assert.match(status.textContent, /Rehearsal off/);
  firstItem = popup.window.document.querySelector('#pp-timeline li[data-index="0"]');
  assert.doesNotMatch(firstItem.textContent, /actual/);
});
