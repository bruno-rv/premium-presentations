// AT5 — premium-follow.js must be inert with no ?present/?follow param: no
// fetch, no setTimeout, no listener bound, no throw. Mirrors
// portable-runtime.test.mjs conventions.
//
// Codex round-3 finding: the ?follow=1 poller used a bare setInterval with
// no in-flight guard, timeout, or ordering check — a stalled LAN could pile
// up unresolved polls, and an out-of-order late response could scrollIntoView
// AFTER a newer one, jumping the audience back to a stale slide. The fix is
// a single-flight recursive poll (setTimeout, not setInterval) + an
// AbortController timeout that advances the cycle even if the fetch hangs +
// a monotonic sequence number checked immediately before navigating, so a
// stale response (one that slips past its own abort, per the fetch spec —
// "a request already complete when abort() is called can still resolve")
// is dropped instead of navigating. See premium-follow.js for the full
// design note.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const source = readFileSync(resolve(root, 'assets/shared/premium-follow.js'), 'utf8');

function makeDom(url) {
  return new JSDOM(
    `<!doctype html><html><body>
      <main id="deck">
        <section class="slide visible" id="slide-1"></section>
        <section class="slide" id="slide-2"></section>
        <section class="slide" id="slide-3"></section>
      </main>
    </body></html>`,
    { url, runScripts: 'dangerously', pretendToBeVisual: true },
  );
}

// Flush a handful of microtask turns — enough for a couple of chained
// `.then()`s to settle without waiting on a real timer.
async function flush(times = 4) {
  for (let i = 0; i < times; i += 1) {
    await new Promise((r) => setImmediate(r));
  }
}

test('no param (file:// / plain open): 0 fetch, 0 setTimeout, 0 listeners, no throw', () => {
  const dom = makeDom('http://localhost/deck.html');
  const { window } = dom;

  let fetchCalls = 0;
  window.fetch = () => { fetchCalls += 1; throw new Error('fetch must not be called'); };
  let timeoutCalls = 0;
  const realSetTimeout = window.setTimeout.bind(window);
  window.setTimeout = (...args) => { timeoutCalls += 1; return realSetTimeout(...args); };
  let slidechangeListeners = 0;
  const realAddEventListener = window.addEventListener.bind(window);
  window.addEventListener = (type, ...rest) => {
    if (type === 'premium:slidechange') slidechangeListeners += 1;
    return realAddEventListener(type, ...rest);
  };

  assert.doesNotThrow(() => window.eval(source));

  assert.equal(fetchCalls, 0);
  assert.equal(timeoutCalls, 0);
  assert.equal(slidechangeListeners, 0);
});

test('?present=1 binds a premium:slidechange listener that POSTs the slide id', async () => {
  const dom = makeDom('http://localhost/deck.html?present=1');
  const { window } = dom;

  const posted = [];
  window.fetch = (url, opts) => {
    posted.push({ url, opts });
    return Promise.resolve({ json: () => Promise.resolve({}) });
  };

  window.eval(source);
  window.dispatchEvent(new window.CustomEvent('premium:slidechange', { detail: { id: 'slide-2' } }));
  await Promise.resolve();

  assert.equal(posted.length, 1);
  assert.equal(posted[0].url, '/slide');
  assert.equal(posted[0].opts.method, 'POST');
  assert.deepEqual(JSON.parse(posted[0].opts.body), { id: 'slide-2' });
});

test('?present=1 swallows fetch errors instead of throwing', () => {
  const dom = makeDom('http://localhost/deck.html?present=1');
  const { window } = dom;
  window.fetch = () => { throw new Error('network down'); };

  window.eval(source);
  assert.doesNotThrow(() => {
    window.dispatchEvent(new window.CustomEvent('premium:slidechange', { detail: { id: 'slide-2' } }));
  });
});

// Capture every setTimeout call (both the abort-timeout and the
// next-poll-delay use setTimeout now that the poller is a recursive
// single-flight loop, not setInterval). A leaked real timer keeps the node
// process alive forever under `node --test`, so nothing here ever falls
// through to a real timer — every callback is driven by hand.
function stubSetTimeoutCapture(window) {
  const calls = [];
  window.setTimeout = (cb, ms) => { calls.push({ cb, ms }); return calls.length; };
  window.clearTimeout = () => {};
  return calls;
}

test('?follow=1 polls GET /slide and navigates via scrollIntoView by id', async () => {
  const dom = makeDom('http://localhost/deck.html?follow=1');
  const { window } = dom;

  let scrolledId = null;
  window.HTMLElement.prototype.scrollIntoView = function () { scrolledId = this.id; };
  const calls = stubSetTimeoutCapture(window);
  window.fetch = () => Promise.resolve({ json: () => Promise.resolve({ id: 'slide-2' }) });

  window.eval(source);
  // poll() runs synchronously at eval time and schedules its abort-timeout.
  assert.equal(calls.length, 1);
  assert.equal(calls[0].ms, 1400);

  await flush();

  assert.equal(scrolledId, 'slide-2');
  // The fetch resolved well under the abort deadline, so the cycle advanced
  // by scheduling exactly one next-poll timer at the 1500ms cadence.
  assert.equal(calls.length, 2);
  assert.equal(calls[1].ms, 1500);
});

test('?follow=1 does not re-navigate when the polled id matches the current visible slide', async () => {
  const dom = makeDom('http://localhost/deck.html?follow=1');
  const { window } = dom;

  let scrollCount = 0;
  window.HTMLElement.prototype.scrollIntoView = function () { scrollCount += 1; };
  stubSetTimeoutCapture(window);
  window.fetch = () => Promise.resolve({ json: () => Promise.resolve({ id: 'slide-1' }) });

  window.eval(source);
  await flush();

  assert.equal(scrollCount, 0);
});

test('?follow=1 swallows fetch rejection and keeps polling', async () => {
  const dom = makeDom('http://localhost/deck.html?follow=1');
  const { window } = dom;
  const calls = stubSetTimeoutCapture(window);
  window.fetch = () => Promise.reject(new Error('offline'));

  assert.doesNotThrow(() => window.eval(source));
  await flush();

  assert.equal(calls.length, 2); // abort-timeout (unused) + next-poll timer
  assert.equal(calls[1].ms, 1500);
});

test('?follow=1 is single-flight: no second fetch while the first is still pending', async () => {
  const dom = makeDom('http://localhost/deck.html?follow=1');
  const { window } = dom;

  let fetchCalls = 0;
  window.fetch = () => { fetchCalls += 1; return new Promise(() => {}); }; // never settles
  const calls = stubSetTimeoutCapture(window);

  window.eval(source);
  await flush();

  assert.equal(fetchCalls, 1);
  // Only the abort-timeout for the still-pending first poll is scheduled —
  // the next-poll timer must not exist yet, because the cycle hasn't
  // advanced (nothing has settled or timed out).
  assert.equal(calls.length, 1);
  assert.equal(calls[0].ms, 1400);
});

test('?follow=1 advances to the next poll when the abort-timeout fires on a hung fetch', async () => {
  const dom = makeDom('http://localhost/deck.html?follow=1');
  const { window } = dom;

  let fetchCalls = 0;
  const controllers = [];
  window.fetch = (url, opts) => {
    fetchCalls += 1;
    controllers.push(opts.signal);
    return new Promise(() => {}); // hangs forever (stalled LAN)
  };
  const calls = stubSetTimeoutCapture(window);

  window.eval(source);
  assert.equal(fetchCalls, 1);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].ms, 1400);

  // Fire the abort-timeout for poll #1.
  calls[0].cb();
  assert.equal(controllers[0].aborted, true);
  // advance() schedules the next-poll timer synchronously — no need to
  // wait on the (never-settling) fetch promise.
  assert.equal(calls.length, 2);
  assert.equal(calls[1].ms, 1500);

  // Fire the next-poll timer: poll #2 starts, proving single-flight
  // recursion proceeds past a stalled request instead of piling up.
  calls[1].cb();
  assert.equal(fetchCalls, 2);
  assert.equal(calls.length, 3);
  assert.equal(calls[2].ms, 1400);
});

test('?follow=1 drops a stale response that resolves late and out of order (no navigate)', async () => {
  const dom = makeDom('http://localhost/deck.html?follow=1');
  const { window } = dom;

  let scrolledId = null;
  window.HTMLElement.prototype.scrollIntoView = function () { scrolledId = this.id; };

  // Each fetch call is manually resolved by the test — this models a
  // request whose abort() has no effect because the response was already
  // complete (a real, spec-documented fetch/AbortController race).
  const resolvers = [];
  window.fetch = () => new Promise((resolve) => { resolvers.push(resolve); });
  const calls = stubSetTimeoutCapture(window);

  window.eval(source); // poll #1 (mySeq=1): fetch #1 pending
  assert.equal(calls.length, 1);

  calls[0].cb(); // abort-timeout fires for poll #1 — abort() is a no-op on our mock
  assert.equal(calls.length, 2);

  calls[1].cb(); // poll #2 starts (mySeq=2): fetch #2 pending
  assert.equal(resolvers.length, 2);
  assert.equal(calls.length, 3);

  // Newer response arrives first — navigates normally.
  resolvers[1]({ json: () => Promise.resolve({ id: 'slide-3' }) });
  await flush();
  assert.equal(scrolledId, 'slide-3');

  // Older (poll #1) response finally resolves late, after poll #2 already
  // navigated. It must be dropped, not applied on top.
  resolvers[0]({ json: () => Promise.resolve({ id: 'slide-2' }) });
  await flush();
  assert.equal(scrolledId, 'slide-3', 'stale out-of-order response must not navigate');
});
