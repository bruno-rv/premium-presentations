/**
 * Premium Presentations — LAN follow-along (conditional runtime module).
 *
 * Gated by `data-follow` on <html> at bundle time (see bundle_deck.py
 * wants_follow / validate_runtime_contract.py needs_follow_runtime) — mirrors
 * the existing data-theme="red" attribute-trigger pattern.
 *
 * Portability (AT5, load-bearing): with neither `?present=1` nor `?follow=1`
 * in the URL (file:// open, plain HTTP open, or any other param), this
 * module returns immediately — no fetch, no setInterval, no listener bound.
 * Dead code on every deck that isn't actively presenting/following.
 *
 * ?present=1  — POST {id} to /slide on every premium:slidechange.
 * ?follow=1   — single-flight recursive poll of GET /slide, ~1500ms between
 *               polls; navigate via document.getElementById(id).scrollIntoView(),
 *               exactly what PremiumDeckControls.goTo() does. slide-engine.js
 *               binds popstate only (not hashchange), so a programmatic
 *               location.hash assignment would NOT navigate — scrollIntoView
 *               is the only correct nav mechanism here. The scroll-snap
 *               IntersectionObserver then updates current/chrome/hash/broadcast.
 *
 *               Single-flight: the next poll cycle is scheduled exactly
 *               once per cycle — either when the fetch settles on its own,
 *               or (if it hangs) when a 1400ms timeout (under the 1500ms
 *               cadence) fires abort() and advances anyway, so a stalled
 *               LAN can never pile up unresolved polls. abort() is
 *               best-effort: per the fetch spec, a request already past
 *               the point of completion can still resolve normally even
 *               after abort() is called. So that stale fetch may still
 *               resolve later, in the background, after later polls have
 *               already run — every resolution is stamped with the
 *               monotonic sequence number of the poll that issued it and
 *               checked against the latest sequence immediately before
 *               navigating, so a late, superseded response is dropped
 *               instead of scrolling the audience back to a stale slide.
 */
(function () {
  var q = new URLSearchParams(location.search);
  var present = q.get('present') === '1';
  var follow = q.get('follow') === '1';
  if (!present && !follow) return;

  if (present) {
    window.addEventListener('premium:slidechange', function (e) {
      try {
        fetch('/slide', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: e.detail && e.detail.id }),
        });
      } catch (_) {}
    });
  }

  if (follow) {
    var pollSeq = 0;
    var pollDelayMs = 1500;
    var pollTimeoutMs = 1400;

    function poll() {
      pollSeq += 1;
      var mySeq = pollSeq;
      var controller = new AbortController();
      var advanced = false;

      // Advance exactly once per cycle, whichever fires first: the
      // fetch settling on its own, or the abort-timeout below. This is
      // what makes the loop single-flight without ever wedging open.
      function advance() {
        if (advanced) return;
        advanced = true;
        setTimeout(poll, pollDelayMs);
      }

      var timedOut = setTimeout(function () {
        controller.abort();
        advance();
      }, pollTimeoutMs);

      fetch('/slide', { signal: controller.signal })
        .then(function (r) { return r.json(); })
        .then(function (s) {
          if (mySeq !== pollSeq) return; // superseded by a later poll — ignore
          if (!s || !s.id) return;
          var cur = document.querySelector('.slide.visible');
          if (cur && cur.id === s.id) return;
          var el = document.getElementById(s.id);
          if (el && el.classList.contains('slide')) {
            el.scrollIntoView({ behavior: 'smooth' });
          }
        })
        .catch(function () {})
        .then(function () {
          clearTimeout(timedOut);
          advance();
        });
    }

    poll();
  }
})();
