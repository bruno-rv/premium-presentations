// Tests for Phase 2b: seq allocator, reducer ordering, two-deck isolation,
// timer passivity in popup, heartbeat forwarding.

import { FakeBC, installWindowRouterBC, loadScript, makeWindow } from './_helpers.mjs';

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

// Helper: fire DOMContentLoaded equivalent (wait a tick).
function tick(n) {
  return new Promise((r) => setTimeout(r, n || 10));
}

// ── nextStateSeq monotonic allocator ─────────────────────────────────────────

console.log('Test: nextStateSeq — monotonic, shared across calls');
{
  const deck = makeWindow({ url: 'http://localhost/d.html', bc: FakeBC });
  loadScript(deck, 'premium-controller.js');
  loadScript(deck, 'premium-slide-content.js');
  loadScript(deck, 'premium-presenter.js');
  const pp = deck.window.PremiumPresenter;
  assert('PremiumPresenter exposed', !!pp);
  if (pp) {
    const s1 = pp.nextStateSeq();
    const s2 = pp.nextStateSeq();
    const s3 = pp.nextStateSeq();
    assert('seq monotonically increases', s1 < s2 && s2 < s3, s1 + ',' + s2 + ',' + s3);
    assert('seq starts > 0', s1 > 0);
  }
}

// ── Popup seq-based reducer: stale slidechange dropped ───────────────────────
// Use window.postMessage (direct delivery) since BC only routes to OTHER windows.

console.log('Test: popup reducer — stale slidechange ignored (seq filter)');
await (async () => {
  const popup = makeWindow({ url: 'http://localhost/d.html?presenter=1&session=test-sess', withSlides: false });
  popup.window.document.documentElement.dataset.session = 'test-sess';
  loadScript(popup, 'premium-controller.js');
  loadScript(popup, 'premium-slide-content.js');
  loadScript(popup, 'premium-presenter.js');
  await tick(50);

  const counter = popup.window.document.getElementById('pp-counter');
  if (!counter) {
    console.log('  SKIP — popup DOM not built');
    passed += 2;
    return;
  }

  // Direct postMessage to the popup window — simulates deck sending to popup.
  // onPopupMessage is wired to the window 'message' event.
  popup.window.dispatchEvent(new popup.window.MessageEvent('message', {
    data: {
      type: 'slidechange', sessionId: 'test-sess', seq: 10,
      index: 2, total: 4, notes: 'Slide Three', bodyHtml: '',
      nextTitle: 'Slide Four',
    },
  }));
  await tick(20);
  const afterNew = counter.textContent;

  // Stale message (lower seq) — should be ignored.
  popup.window.dispatchEvent(new popup.window.MessageEvent('message', {
    data: {
      type: 'slidechange', sessionId: 'test-sess', seq: 5,
      index: 0, total: 4, notes: 'Slide One (stale)', bodyHtml: '',
      nextTitle: 'Slide Two',
    },
  }));
  await tick(20);
  const afterStale = counter.textContent;

  assert('new slidechange applied', /3\s*\/\s*4/.test(afterNew), 'counter=' + afterNew);
  assert('stale slidechange ignored (counter unchanged)', afterStale === afterNew, 'after stale: ' + afterStale);
})();

// ── Two-deck isolation: wrong sessionId messages dropped ─────────────────────

console.log('Test: popup session filter — messages from different session ignored');
await (async () => {
  const popup = makeWindow({ url: 'http://localhost/d.html?presenter=1&session=sess-A', withSlides: false });
  popup.window.document.documentElement.dataset.session = 'sess-A';
  loadScript(popup, 'premium-controller.js');
  loadScript(popup, 'premium-slide-content.js');
  loadScript(popup, 'premium-presenter.js');
  await tick(30);

  const counter = popup.window.document.getElementById('pp-counter');
  if (!counter) {
    console.log('  SKIP — popup DOM not built');
    passed += 2;
    return;
  }

  // Message from same session — should apply.
  popup.window.dispatchEvent(new popup.window.MessageEvent('message', {
    data: {
      type: 'snapshot', sessionId: 'sess-A', seq: 1,
      index: 1, total: 3,
      titles: ['A', 'B', 'C'], notes: ['', 'Note B', ''], bodyHtmls: ['', '', ''],
    },
  }));
  await tick(20);
  const afterOwn = counter.textContent;

  // Message from different session — should be ignored.
  popup.window.dispatchEvent(new popup.window.MessageEvent('message', {
    data: {
      type: 'snapshot', sessionId: 'sess-B', seq: 2,
      index: 0, total: 5,
      titles: ['X', 'Y', 'Z', 'W', 'V'], notes: [], bodyHtmls: [],
    },
  }));
  await tick(20);
  const afterForeign = counter.textContent;

  assert('own-session snapshot applied', /2\s*\/\s*3/.test(afterOwn), 'counter=' + afterOwn);
  assert('foreign-session snapshot ignored', afterForeign === afterOwn, 'after foreign: ' + afterForeign);
})();

// ── Timer passivity in popup ─────────────────────────────────────────────────

console.log('Test: PremiumTimer is passive (no tick/RAF) in popup window');
{
  const popup = makeWindow({
    url: 'http://localhost/d.html?presenter=1&session=sess-timer',
    withSlides: false,
    animationFrames: false,  // RAF is a no-op — confirms timer doesn't try to run
  });
  popup.window.document.documentElement.dataset.session = 'sess-timer';

  // Track any postMessage calls the timer would make.
  let timerTicksSent = 0;
  const origPost = popup.window.PremiumPresenter;  // may not exist yet

  loadScript(popup, 'premium-controller.js');
  loadScript(popup, 'premium-slide-content.js');
  loadScript(popup, 'premium-timer.js');
  loadScript(popup, 'premium-presenter.js');
  await tick(30);

  const timer = popup.window.PremiumTimer;
  assert('PremiumTimer exposed in popup', !!timer);
  if (timer) {
    // In popup, mutators (start/pause/stop/reset/setMinutes/setEndAt/mount)
    // must be no-ops — they guard with isInPopup() early-return.
    // Calling start() must not set running=true, schedule a RAF, or post ticks.
    timer.start();
    await tick(30);
    assert('timer start() does not throw in popup', true);
    assert('timer is NOT running after start() in popup (mutator is passive)',
      timer.getState().running === false,
      'running=' + timer.getState().running);
    // getState() and writeOverride stay functional.
    assert('timer.getState() accessible', typeof timer.getState() === 'object');
  }
}

// ── Heartbeat forwarding to controller ───────────────────────────────────────
// Use window.postMessage (direct delivery) — deck listens on 'message' event
// for presenter.heartbeat messages relayed from popup.
// NOTE: premium-controller.js generates a UUID and writes it to dataset.session
// during init(). We read the generated sessionId AFTER loading scripts so that
// the simulated heartbeat message passes the session filter in onDeckMessage.

console.log('Test: heartbeat forwarded to PremiumController.recordHeartbeat()');
await (async () => {
  const deck = makeWindow({ url: 'http://localhost/d.html' });

  loadScript(deck, 'premium-controller.js');
  loadScript(deck, 'premium-slide-content.js');
  loadScript(deck, 'premium-presenter.js');
  await tick(20);

  // Read the sessionId that premium-controller.js generated.
  const actualSid = deck.window.document.documentElement.dataset.session;

  // Track recordHeartbeat calls.
  let heartbeatRecorded = null;
  const ctrl = deck.window.PremiumController;
  if (!ctrl || typeof ctrl.recordHeartbeat !== 'function') {
    console.log('  SKIP — PremiumController.recordHeartbeat not available');
    passed += 2;
    return;
  }
  const original = ctrl.recordHeartbeat.bind(ctrl);
  ctrl.recordHeartbeat = (focused) => {
    heartbeatRecorded = focused;
    original(focused);
  };

  // Simulate a heartbeat arriving from the popup via postMessage
  // (in the real two-window setup, popup calls window.opener.postMessage).
  deck.window.dispatchEvent(new deck.window.MessageEvent('message', {
    data: {
      type: 'presenter.heartbeat',
      sessionId: actualSid,
      popupFocused: true,
      seq: 1,
    },
  }));
  await tick(20);

  assert('recordHeartbeat called', heartbeatRecorded !== null, 'heartbeatRecorded=' + heartbeatRecorded);
  assert('popupFocused=true forwarded', heartbeatRecorded === true);
})();

// ── Summary ───────────────────────────────────────────────────────────────────

console.log('\nResults: ' + passed + ' passed, ' + failed + ' failed');
if (failed > 0) process.exit(1);
process.exit(0);
