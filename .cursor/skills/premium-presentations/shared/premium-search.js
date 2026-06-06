/**
 * Premium Presentations — fuzzy search palette (Cmd/Ctrl+K).
 * Lazy-loads MiniSearch from CDN.
 */
(function () {
  const MS_URL = 'https://cdn.jsdelivr.net/npm/minisearch@7/+esm';
  let msLib = null;
  let index = null;
  let docs = [];
  let active = false;
  let overlay = null;
  let input = null;
  let resultsEl = null;
  let currentFocus = 0;
  let currentResults = [];

  async function loadMiniSearch() {
    if (msLib) return msLib;
    msLib = await import(MS_URL);
    return msLib;
  }

  function buildDocs() {
    const slides = [...document.querySelectorAll('#deck .slide')];
    return slides.map((s, i) => {
      const heading = s.querySelector('[data-nav-title], .slide__heading, .slide__display, .slide__label')?.textContent?.trim() || '';
      const body = s.innerText.replace(/\s+/g, ' ').trim().slice(0, 200);
      return { id: i, slideId: s.id, num: i + 1, heading, body };
    });
  }

  async function rebuild() {
    docs = buildDocs();
    const ms = await loadMiniSearch();
    index = new ms.default({
      fields: ['heading', 'body'],
      store: ['num', 'heading', 'body', 'slideId'],
      searchOptions: { boost: { heading: 2 }, prefix: true, fuzzy: 0.2 },
    });
    index.addAll(docs);
  }

  function highlight(text, query) {
    if (!query) return text;
    const re = new RegExp('(' + query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
    return text.replace(re, '<mark>$1</mark>');
  }

  function renderResults(items, query) {
    currentResults = items;
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
    currentFocus = 0;
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
    const items = index.search(q);
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
    if (e.key === 'Enter') { e.preventDefault(); jump(currentResults[currentFocus]?.id ?? 0); return; }
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

  window.PremiumSearch = { open, close, rebuild };
})();
