// premium-glossary.js — Shared glossary/term-popup module.
// Parses a <script type="application/json" id="glossary"> dictionary from the
// page, injects a #term-popup modal, wires click/Esc/focus handlers, and
// exposes a public API on window.PremiumGlossary.
//
// Usage: include conditionally when the deck contains .term-link[data-term]
// elements or a <script id="glossary"> data block. The bundler (bundle_deck.py)
// handles inclusion via wants_premium_glossary().
//
// API:
//   window.PremiumGlossary.open(term)            — open popup for a key
//   window.PremiumGlossary.close()               — close popup
//   window.PremiumGlossary.getTerms()            — { key: {title, body}, … }
//   window.PremiumGlossary.getTermsForSlide(el)  — [{key,title,body}] for el

(function () {
  'use strict';

  // ── Parse dictionary ────────────────────────────────────────────────────────
  // Parsing happens before the presenter guard so the read-only API
  // (getTerms / getTermsForSlide) works in the presenter popup window.

  var dict = {};
  try {
    var scriptEl = document.getElementById('glossary');
    if (scriptEl && scriptEl.type === 'application/json') {
      var parsed = JSON.parse(scriptEl.textContent);
      if (parsed && typeof parsed === 'object') {
        dict = parsed;
      }
    }
  } catch (_) {}

  // Guard: inside the presenter popup window install a read-only API —
  // no modal, no click/Esc handlers (open/close are no-ops).
  // getTerms() and getTermsForSlide() are fully functional so the
  // presenter renderNotes() can populate .pp-notes-terms.
  if (window.location.search.indexOf('presenter=1') !== -1) {
    window.PremiumGlossary = {
      open: function () {},
      close: function () {},
      getTerms: function () {
        var copy = {};
        var keys = Object.keys(dict);
        for (var i = 0; i < keys.length; i++) {
          copy[keys[i]] = dict[keys[i]];
        }
        return copy;
      },
      getTermsForSlide: function (slideEl) {
        if (!slideEl) return [];
        var links = slideEl.querySelectorAll('.term-link[data-term]');
        var seen = {};
        var result = [];
        for (var i = 0; i < links.length; i++) {
          var key = links[i].dataset.term;
          if (key && !seen[key] && dict[key]) {
            seen[key] = true;
            result.push({ key: key, title: dict[key].title || key, body: dict[key].body || '' });
          }
        }
        return result;
      },
    };
    return;
  }

  // ── Inject modal DOM ────────────────────────────────────────────────────────

  var popup = null;
  var titleEl = null;
  var bodyEl = null;
  var closeBtn = null;

  function ensurePopup() {
    if (popup) return;
    if (document.getElementById('term-popup')) {
      popup = document.getElementById('term-popup');
      titleEl = document.getElementById('term-popup-title');
      bodyEl = popup.querySelector('.term-popup__body');
      closeBtn = popup.querySelector('.term-popup__close');
      return;
    }

    var wrapper = document.createElement('div');
    wrapper.innerHTML =
      '<div class="term-popup" id="term-popup" aria-hidden="true">' +
        '<button type="button" class="term-popup__backdrop" data-term-close aria-label="Close definition"></button>' +
        '<div class="term-popup__card" role="dialog" aria-modal="true" aria-labelledby="term-popup-title">' +
          '<button type="button" class="term-popup__close" data-term-close aria-label="Close">×</button>' +
          '<h3 id="term-popup-title" class="term-popup__title"></h3>' +
          '<p class="term-popup__body"></p>' +
          '<p class="term-popup__hint">Esc or click outside to close</p>' +
        '</div>' +
      '</div>';
    document.body.appendChild(wrapper.firstChild);
    popup = document.getElementById('term-popup');
    titleEl = document.getElementById('term-popup-title');
    bodyEl = popup.querySelector('.term-popup__body');
    closeBtn = popup.querySelector('.term-popup__close');
  }

  // ── Open / close ────────────────────────────────────────────────────────────

  var lastFocus = null;

  function openTerm(key) {
    var entry = dict[key];
    if (!entry) return;
    ensurePopup();
    if (!popup) return;
    lastFocus = document.activeElement;
    if (titleEl) titleEl.textContent = entry.title || key;
    if (bodyEl) bodyEl.textContent = entry.body || '';
    popup.classList.add('is-open');
    popup.setAttribute('aria-hidden', 'false');
    if (closeBtn) closeBtn.focus();
  }

  function closeTerm() {
    if (!popup) return;
    popup.classList.remove('is-open');
    popup.setAttribute('aria-hidden', 'true');
    if (lastFocus && typeof lastFocus.focus === 'function') {
      try { lastFocus.focus(); } catch (_) {}
    }
    lastFocus = null;
  }

  // ── Event wiring ────────────────────────────────────────────────────────────

  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('.term-link[data-term]');
    if (btn) {
      e.preventDefault();
      e.stopPropagation();
      openTerm(btn.dataset.term);
      return;
    }
    if (e.target.closest && e.target.closest('[data-term-close]')) {
      closeTerm();
    }
  });

  // Capture-phase keyboard guard: active only while the popup is open.
  // (a) Traps Tab within the dialog (close button is the only focusable element).
  // (b) Consumes deck-navigation keys so they don't reach the slide engine.
  // (c) Escape closes the popup — only stops propagation while open so the
  //     deck's other Esc behaviors are not affected when the popup is closed.
  var DECK_NAV_KEYS = {
    ArrowLeft: 1, ArrowRight: 1, ArrowUp: 1, ArrowDown: 1,
    ' ': 1, PageUp: 1, PageDown: 1, Home: 1, End: 1,
  };

  document.addEventListener('keydown', function (e) {
    var isOpen = popup && popup.classList.contains('is-open');
    if (!isOpen) return;

    if (e.key === 'Escape') {
      e.stopPropagation();
      closeTerm();
      return;
    }

    if (e.key === 'Tab') {
      // Only focusable element inside the dialog is closeBtn — wrap focus.
      e.preventDefault();
      e.stopImmediatePropagation();
      ensurePopup();
      if (closeBtn) closeBtn.focus();
      return;
    }

    if (DECK_NAV_KEYS[e.key]) {
      e.preventDefault();
      e.stopImmediatePropagation();
    }
  }, true); // capture phase

  // ── Public API ──────────────────────────────────────────────────────────────

  window.PremiumGlossary = {
    open: openTerm,
    close: closeTerm,
    getTerms: function () {
      var copy = {};
      var keys = Object.keys(dict);
      for (var i = 0; i < keys.length; i++) {
        copy[keys[i]] = dict[keys[i]];
      }
      return copy;
    },
    getTermsForSlide: function (slideEl) {
      if (!slideEl) return [];
      var links = slideEl.querySelectorAll('.term-link[data-term]');
      var seen = {};
      var result = [];
      for (var i = 0; i < links.length; i++) {
        var key = links[i].dataset.term;
        if (key && !seen[key] && dict[key]) {
          seen[key] = true;
          result.push({ key: key, title: dict[key].title || key, body: dict[key].body || '' });
        }
      }
      return result;
    },
  };
})();
