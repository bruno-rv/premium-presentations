/**
 * Premium Presentations — PremiumSlideContent
 *
 * Pure functions over slide DOM elements. Shared between SlideEngine (deck)
 * and the presenter popup. The popup calls these directly against its own
 * copy of the live slide DOM; the deck uses them when building wire payloads.
 *
 * All functions are side-effect free and return strings.
 */
(function () {
  function elementText(el) {
    if (!el) return '';
    const clone = el.cloneNode(true);
    clone.querySelectorAll('br').forEach((br) => br.replaceWith(' '));
    return clone.textContent.replace(/\s+/g, ' ').trim();
  }

  function truncateNavTitle(text) {
    text = (text || '').replace(/\s+/g, ' ').trim();
    if (!text) return '';
    const max = 52;
    if (text.length <= max) return text;
    return text.slice(0, max - 1).trim() + '…';
  }

  function firstPhrase(text) {
    text = (text || '').trim();
    if (!text) return '';
    const cut = text.match(/^[^.!?…]+[.!?…]?/);
    return (cut ? cut[0] : text).trim();
  }

  // Derive a display title for nav / presenter rail.
  function getTitle(slide, i) {
    if (!slide) return 'Part ' + ((i || 0) + 1);
    const custom = slide.dataset.navTitle || slide.dataset.title;
    if (custom) return truncateNavTitle(custom);

    const textFrom = (sel) => elementText(slide.querySelector(sel));

    const selectors = [
      '.slide__heading',
      '.slide__display',
      '.slide__label',
      'h2', 'h1',
      '.slide__subtitle',
      '.slide__table-title',
      'figcaption',
      'blockquote',
      'cite',
      '.slide__body p',
      '.reveal p',
      'th',
    ];

    for (let s = 0; s < selectors.length; s++) {
      const sel = selectors[s];
      const nodes = slide.querySelectorAll(sel);
      for (let n = 0; n < nodes.length; n++) {
        const el = nodes[n];
        if (sel === 'th') {
          const row = el.closest('tr');
          if (row && row.querySelector('th') !== el) continue;
        }
        if (sel === '.reveal p' && el.closest('blockquote')) continue;
        const t = elementText(el);
        if (t.length > 2) {
          const title = (sel === 'blockquote' || sel === '.reveal p') ? firstPhrase(t) : t;
          return truncateNavTitle(title);
        }
      }
    }

    const aria = slide.getAttribute('aria-label');
    if (aria) return truncateNavTitle(aria);

    const typeFallback = {
      'slide--title': 'Opening',
      'slide--quote': 'Quote',
      'slide--divider': 'Section',
      'slide--diagram': 'Diagram',
      'slide--dashboard': 'Dashboard',
      'slide--table': 'Table',
      'slide--split': 'Split',
      'slide--content': 'Content',
    };
    for (const cls in typeFallback) {
      if (slide.classList.contains(cls)) {
        const label = elementText(slide.querySelector('.slide__label'));
        if (label) return truncateNavTitle(label + ' — ' + typeFallback[cls]);
        return typeFallback[cls];
      }
    }

    return 'Part ' + ((i || 0) + 1);
  }

  // Speaker notes HTML from <aside class="notes"> or .slide__notes.
  // Returns '' when absent.
  function getNotesHtml(slide) {
    if (!slide) return '';
    const el = slide.querySelector('aside.notes, .slide__notes');
    return el ? el.innerHTML : '';
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // Condensed "talking points" view of a slide's body content.
  // Strategy: clone the WHOLE slide, strip structural chrome + notes,
  // NEVER remove .reveal (those are real content), then extract:
  //   - lead: first 2 sentences of first <p>
  //   - quote: first <blockquote>
  //   - bullets: up to 4 li from the first <ul> or <ol>
  //   - table: first <table> summary (column headers + first 2 rows)
  // Returns HTML string or '' if nothing useful found.
  function getSummaryHtml(slide) {
    if (!slide) return '';

    // Clone entire slide so we can mutate freely.
    const clone = slide.cloneNode(true);

    // Remove non-content elements: nav chrome, decorative overlays, notes.
    // DO NOT remove .reveal — it contains real body content.
    clone.querySelectorAll(
      'aside.notes, .slide__notes, ' +
      '.slide__label, .slide__number, .slide__chrome, .slide__nav, ' +
      '.slide__dot-strip, .slide__glow, .theme-visual, .geo-particle, ' +
      '.slide-3d-frame > .slide__number, ' +
      'script, style, svg, canvas, iframe, ' +
      '.premium-bg-3d, .deck-dots, .deck-progress, .deck-counter'
    ).forEach((n) => n.remove());

    // Remove headings (they're already shown in the rail title).
    clone.querySelectorAll('h1, h2, h3, h4').forEach((n) => n.remove());

    const parts = [];

    // Lead paragraph: first <p>, up to 2 sentences.
    const lead = clone.querySelector('p');
    if (lead) {
      const text = (lead.textContent || '').trim().replace(/\s+/g, ' ');
      const sentences = text.match(/[^.!?]+(?:[.!?]+|$)/g) || [text];
      const lead2 = sentences.slice(0, 2).join('').trim();
      if (lead2) parts.push('<p class="pp-summary__lead">' + escapeHtml(lead2) + '</p>');
      lead.remove();
    }

    // Blockquote callout.
    const quote = clone.querySelector('blockquote');
    if (quote) {
      const text = (quote.textContent || '').trim().replace(/\s+/g, ' ');
      if (text) parts.push('<blockquote class="pp-summary__quote">' + escapeHtml(text) + '</blockquote>');
      quote.remove();
    }

    // Bullets: first 4 items from any list.
    const list = clone.querySelector('ul, ol');
    if (list) {
      const items = [...list.querySelectorAll(':scope > li')].slice(0, 4).map((li) => {
        const t = (li.textContent || '').trim().replace(/\s+/g, ' ');
        const short = t.length > 140 ? t.slice(0, 137) + '…' : t;
        return '<li>' + escapeHtml(short) + '</li>';
      }).join('');
      if (items) parts.push('<ul class="pp-summary__bullets">' + items + '</ul>');
    }

    // Table summary: first table's column headers + up to 2 data rows.
    if (!parts.length) {
      const table = clone.querySelector('table');
      if (table) {
        const headers = [...table.querySelectorAll('th')].slice(0, 5).map((th) =>
          escapeHtml((th.textContent || '').trim())
        ).join(' | ');
        const rows = [...table.querySelectorAll('tbody tr')].slice(0, 2).map((tr) => {
          const cells = [...tr.querySelectorAll('td')].slice(0, 5).map((td) =>
            escapeHtml((td.textContent || '').trim())
          ).join(' | ');
          return '<li>' + cells + '</li>';
        }).join('');
        if (headers) parts.push('<p class="pp-summary__lead">' + headers + '</p>');
        if (rows) parts.push('<ul class="pp-summary__bullets">' + rows + '</ul>');
      }
    }

    if (parts.length > 0) return parts.join('');

    // Last-resort fallback per plan Phase 1.3: return the slide title as lead.
    const title = getTitle(slide);
    const trimmed = (title || '').trim();
    if (!trimmed) return '';
    return '<p class="pp-summary__lead">' + escapeHtml(trimmed) + '</p>';
  }

  window.PremiumSlideContent = {
    getTitle,
    getNotesHtml,
    getSummaryHtml,
  };
})();
