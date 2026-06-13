/**
 * Premium Presentations — portable slide search palette (Cmd/Ctrl+K).
 */
(function () {
  let index = null;
  let docs = [];
  let active = false;
  let overlay = null;
  let input = null;
  let resultsEl = null;
  let currentFocus = 0;
  let currentResults = [];

  function textOf(el) {
    return (el?.innerText || el?.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function tokenize(text) {
    return text
      .toLowerCase()
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .split(/[^a-z0-9]+/)
      .filter(Boolean);
  }

  function editDistance(a, b, limit = 2) {
    if (a === b) return 0;
    if (Math.abs(a.length - b.length) > limit) return limit + 1;
    const prev = Array.from({ length: b.length + 1 }, (_, i) => i);
    const curr = new Array(b.length + 1);
    for (let i = 1; i <= a.length; i++) {
      curr[0] = i;
      let rowMin = curr[0];
      for (let j = 1; j <= b.length; j++) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        curr[j] = Math.min(
          curr[j - 1] + 1,
          prev[j] + 1,
          prev[j - 1] + cost
        );
        rowMin = Math.min(rowMin, curr[j]);
      }
      if (rowMin > limit) return limit + 1;
      for (let j = 0; j <= b.length; j++) prev[j] = curr[j];
    }
    return prev[b.length];
  }

  function tokenScore(queryToken, docToken) {
    if (!queryToken || !docToken) return 0;
    if (docToken === queryToken) return 8;
    if (docToken.startsWith(queryToken)) return 5;
    if (docToken.includes(queryToken)) return 3;
    if (queryToken.length >= 4 && editDistance(queryToken, docToken) <= 1) return 1.5;
    return 0;
  }

  function scoreDoc(doc, queryTokens) {
    if (!queryTokens.length) return 1;
    let total = 0;
    for (const q of queryTokens) {
      let best = 0;
      for (const t of doc.headingTokens) best = Math.max(best, tokenScore(q, t) * 2);
      for (const t of doc.bodyTokens) best = Math.max(best, tokenScore(q, t));
      if (!best) return 0;
      total += best;
    }
    return total;
  }

  function escapeHtml(text) {
    return String(text || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function buildDocs() {
    const slides = [...document.querySelectorAll('#deck .slide')];
    return slides.map((s, i) => {
      const heading =
        s.getAttribute('data-nav-title') ||
        textOf(s.querySelector('.slide__heading, .slide__display, .slide__label'));
      const body = textOf(s).slice(0, 400);
      return {
        id: i,
        slideId: s.id,
        num: i + 1,
        heading,
        body,
        headingTokens: tokenize(heading),
        bodyTokens: tokenize(body),
      };
    });
  }

  async function rebuild() {
    docs = buildDocs();
    index = docs;
    return index;
  }

  function query(q) {
    const qTokens = tokenize(q || '');
    if (!index) {
      docs = buildDocs();
      index = docs;
    }
    if (!qTokens.length) return [...docs];
    return [...index]
      .map((doc) => ({ ...doc, score: scoreDoc(doc, qTokens) }))
      .filter((doc) => doc.score > 0)
      .sort((a, b) => b.score - a.score || a.num - b.num);
  }

  function highlight(text, query) {
    text = String(text || '');
    if (!query) return escapeHtml(text);
    const re = new RegExp('(' + query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
    let out = '';
    let last = 0;
    let match;
    while ((match = re.exec(text))) {
      out += escapeHtml(text.slice(last, match.index));
      out += '<mark>' + escapeHtml(match[0]) + '</mark>';
      last = match.index + match[0].length;
    }
    return out + escapeHtml(text.slice(last));
  }

  function renderResults(items, query) {
    currentResults = items;
    currentFocus = 0;
    if (!items.length) {
      resultsEl.innerHTML = '<li class="premium-search-result" style="opacity:0.5">No matches</li>';
      return;
    }
    resultsEl.innerHTML = items.slice(0, 10).map((it, i) => {
      const title = highlight(it.heading || '(untitled)', query);
      const body = highlight((it.body || '').slice(0, 80), query);
      return '<li class="premium-search-result' + (i === 0 ? ' is-active' : '') + '" data-i="' + it.id + '">' +
        '<span class="premium-search-result__num">' + it.num + '</span>' +
        '<div style="flex:1"><div class="premium-search-result__title">' + title + '</div>' +
        '<div class="premium-search-result__body">' + body + '</div></div></li>';
    }).join('');
  }

  function open() {
    if (active) return;
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'premium-search-overlay';
      overlay.innerHTML =
        '<div class="premium-search-palette">' +
        '<input class="premium-search-input" type="search" placeholder="Search slides…" aria-label="Search slides">' +
        '<ul class="premium-search-results"></ul>' +
        '<div class="premium-search-hint">↑↓ navigate · ↵ jump · esc close</div>' +
        '</div>';
      document.body.appendChild(overlay);
      input = overlay.querySelector('.premium-search-input');
      resultsEl = overlay.querySelector('.premium-search-results');
      input.addEventListener('input', () => update(input.value));
      input.addEventListener('keydown', onKey);
      resultsEl.addEventListener('click', (e) => {
        const li = e.target.closest('.premium-search-result');
        if (li) jump(parseInt(li.dataset.i, 10));
      });
      overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    }
    overlay.style.display = 'flex';
    active = true;
    setTimeout(() => input.focus(), 30);
    rebuild();
  }

  function close() {
    if (!active) return;
    overlay.style.display = 'none';
    active = false;
    input.value = '';
  }

  function update(q) {
    if (!index) return;
    if (!q) { renderResults(docs, ''); return; }
    const items = query(q);
    renderResults(items, q);
  }

  function jump(id) {
    const deck = document.getElementById('deck');
    const slide = document.querySelectorAll('#deck .slide')[id];
    if (slide) slide.scrollIntoView({ behavior: 'smooth' });
    close();
  }

  function onKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key === 'Enter') {
      e.preventDefault();
      const item = currentResults[currentFocus];
      if (item) jump(item.id);
      return;
    }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const dir = e.key === 'ArrowDown' ? 1 : -1;
      const items = [...resultsEl.querySelectorAll('.premium-search-result')];
      if (!items.length) return;
      currentFocus = (currentFocus + dir + items.length) % items.length;
      items.forEach((el, i) => el.classList.toggle('is-active', i === currentFocus));
      items[currentFocus].scrollIntoView({ block: 'nearest' });
    }
  }

  function init() {
    document.addEventListener('keydown', (e) => {
      if (e.repeat) return;
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      if (new URLSearchParams(location.search).get('presenter') === '1') return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        active ? close() : open();
      } else if (!e.metaKey && !e.ctrlKey && e.key === '/' && !active) {
        e.preventDefault();
        open();
      }
    });
    document.addEventListener('premium-theme-change', () => { rebuild(); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumSearch = { open, close, rebuild, query };
})();
