/**
 * Premium Presentations — SlideEngine (scroll-snap deck navigation).
 * Expects: #deck, sections.slide, chrome built dynamically or present.
 *
 * Exposes window.PremiumDeckControls for clicker, presenter popup (in-deck only),
 * and embed host to call next/prev/goTo and query titles/notes/state.
 */
function SlideEngine(options) {
  options = options || {};
  this.deck = document.getElementById('deck');
  if (!this.deck) throw new Error('SlideEngine: #deck not found');
  this.embedMode = new URLSearchParams(location.search).get('embedded') === '1' || window.self !== window.top;
  if (this.embedMode) {
    document.documentElement.dataset.embedded = 'true';
  }
  this.slides = [...this.deck.querySelectorAll('.slide')];
  this.ensureSlideIds();
  this.total = this.slides.length;
  this.current = 0;
  this.chromeStatic = options.chromeStatic === true;
  this.dotItems = [];
  if (this.chromeStatic) {
    this.progress = document.getElementById('progress');
    this.dots = document.getElementById('dots');
    this.counter = document.getElementById('counter');
    this.hints = document.getElementById('hints');
    this.slides.forEach((_, i) => {
      const item = this.createDotItem(i);
      this.dotItems.push(item);
      this.dots.appendChild(item);
    });
  } else {
    this.buildChrome();
  }
  this.bindEvents();
  this.bindEmbed();
  this.bindDotLabels();
  this.observe();
  this.slides[0]?.classList.add('visible');
  this.updateChrome();
  this.exposeApi();
  // Initial slide is index 0. After the popup sends presenter.ready,
  // premium-presenter.js reads the current index from the controller's
  // session channel, not from here. The popup will receive the first
  // slidechange or be answered by an explicit snapshot.
  this.broadcastSnapshotDebounced(50);
}

SlideEngine.LABEL_HIDE_MS = 5000;
SlideEngine.NAV_HIDE_MS = 4800;
SlideEngine.NAV_TITLE_MAX = 52;

SlideEngine.prototype.ensureSlideIds = function () {
  this.slides.forEach((slide, i) => {
    if (slide.id) return;
    slide.id = 'slide-' + (i + 1);
  });
};

SlideEngine.prototype.truncateNavTitle = function (text) {
  text = (text || '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  const max = SlideEngine.NAV_TITLE_MAX;
  if (text.length <= max) return text;
  return text.slice(0, max - 1).trim() + '…';
};

SlideEngine.prototype.elementText = function (el) {
  if (!el) return '';
  const clone = el.cloneNode(true);
  clone.querySelectorAll('br').forEach((br) => br.replaceWith(' '));
  return clone.textContent.replace(/\s+/g, ' ').trim();
};

SlideEngine.prototype.textFrom = function (slide, sel) {
  return this.elementText(slide.querySelector(sel));
};

SlideEngine.prototype.firstPhrase = function (text) {
  text = (text || '').trim();
  if (!text) return '';
  const cut = text.match(/^[^.!?…]+[.!?…]?/);
  return (cut ? cut[0] : text).trim();
};

SlideEngine.prototype.getSlideTitle = function (slide, i) {
  // Delegate to PremiumSlideContent when available.
  if (window.PremiumSlideContent && typeof window.PremiumSlideContent.getTitle === 'function') {
    return window.PremiumSlideContent.getTitle(slide, i);
  }
  // Inline fallback (same logic).
  const custom = slide.dataset.navTitle || slide.dataset.title;
  if (custom) return this.truncateNavTitle(custom);

  const pick = (sel) => this.textFrom(slide, sel);
  const fromSelectors = [
    '.slide__heading',
    '.slide__display',
    '.slide__label',
    'h2',
    'h1',
    '.slide__subtitle',
    '.slide__table-title',
    'figcaption',
    'blockquote',
    'cite',
    '.slide__body p',
    '.reveal p',
    'th',
  ];

  for (let s = 0; s < fromSelectors.length; s++) {
    const sel = fromSelectors[s];
    const nodes = slide.querySelectorAll(sel);
    for (let n = 0; n < nodes.length; n++) {
      const el = nodes[n];
      if (sel === 'th') {
        const row = el.closest('tr');
        if (row && row.querySelector('th') !== el) continue;
      }
      if (sel === '.reveal p' && el.closest('blockquote')) continue;
      const t = this.elementText(el);
      if (t.length > 2) {
        const title =
          sel === 'blockquote' || sel === '.reveal p' ? this.firstPhrase(t) : t;
        return this.truncateNavTitle(title);
      }
    }
  }

  const aria = slide.getAttribute('aria-label');
  if (aria) return this.truncateNavTitle(aria);

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
      const label = pick('.slide__label');
      if (label) return this.truncateNavTitle(label + ' — ' + typeFallback[cls]);
      return typeFallback[cls];
    }
  }

  return 'Part ' + (i + 1);
};

// Notes are read from <aside class="notes"> or .slide__notes inside the slide.
// Returns the inner HTML so the popup can render bold/links. No notes → ''.
SlideEngine.prototype.getSlideNotesHtml = function (slide) {
  if (window.PremiumSlideContent && typeof window.PremiumSlideContent.getNotesHtml === 'function') {
    return window.PremiumSlideContent.getNotesHtml(slide);
  }
  if (!slide) return '';
  const el = slide.querySelector('aside.notes, .slide__notes');
  return el ? el.innerHTML : '';
};

// Slide summary — used by the presenter popup as a fallback when no speaker
// notes have been authored. Delegates to PremiumSlideContent when available.
SlideEngine.prototype.getSlideSummaryHtml = function (slide) {
  if (window.PremiumSlideContent && typeof window.PremiumSlideContent.getSummaryHtml === 'function') {
    return window.PremiumSlideContent.getSummaryHtml(slide);
  }
  // Inline fallback for bundles without PremiumSlideContent.
  if (!slide) return '';
  const containers = [
    '.content-grid', '.slide__body', '.slide__points', '.slide__split', '.slide__quote',
  ];
  let body = null;
  for (const sel of containers) {
    body = slide.querySelector(sel);
    if (body) break;
  }
  if (!body) return '';
  const clone = body.cloneNode(true);
  clone.querySelectorAll(
    '.slide__label, .slide__heading, .slide__display, .slide__number, .slide__chrome, ' +
    '.slide__nav, .slide__dot-strip, .slide__notes, h1, h2, h3, h4, script, style, svg'
  ).forEach((n) => n.remove());
  const parts = [];
  const lead = clone.querySelector('p');
  if (lead) {
    const text = (lead.textContent || '').trim().replace(/\s+/g, ' ');
    const sentences = text.match(/[^.!?]+(?:[.!?]+|$)/g) || [text];
    const lead2 = sentences.slice(0, 2).join('').trim();
    if (lead2) parts.push('<p class="pp-summary__lead">' + escapeSummary(lead2) + '</p>');
    lead.remove();
  }
  const quote = clone.querySelector('blockquote');
  if (quote) {
    const text = (quote.textContent || '').trim();
    if (text) parts.push('<blockquote class="pp-summary__quote">' + escapeSummary(text) + '</blockquote>');
    quote.remove();
  }
  clone.querySelectorAll('ul, ol').forEach((list) => {
    const items = [...list.querySelectorAll(':scope > li')].slice(0, 4).map((li) => {
      const t = (li.textContent || '').trim().replace(/\s+/g, ' ');
      const short = t.length > 140 ? t.slice(0, 137) + '…' : t;
      return '<li>' + escapeSummary(short) + '</li>';
    }).join('');
    if (items) parts.push('<ul class="pp-summary__bullets">' + items + '</ul>');
  });
  return parts.join('') || '';
};

function escapeSummary(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

SlideEngine.prototype.getAllTitles = function () {
  return this.slides.map((s, i) => this.getSlideTitle(s, i));
};

SlideEngine.prototype.createDotItem = function (i) {
  const slide = this.slides[i];
  const title = this.getSlideTitle(slide, i);
  const item = document.createElement('div');
  item.className = 'deck-dot-item';

  const label = document.createElement('a');
  label.className = 'deck-dot-label';
  label.href = '#' + (slide.id || 'slide-' + (i + 1));
  label.textContent = title;
  label.addEventListener('click', (e) => {
    e.preventDefault();
    this.goTo(i);
    this.pushHash(slide);
  });

  const dot = document.createElement('button');
  dot.type = 'button';
  dot.className = 'deck-dot';
  dot.setAttribute('aria-label', title + ' — slide ' + (i + 1));
  dot.title = title;
  dot.addEventListener('click', () => this.goTo(i));

  item.appendChild(label);
  item.appendChild(dot);
  return item;
};

SlideEngine.prototype.buildChrome = function () {
  this.progress = document.createElement('div');
  this.progress.className = 'deck-progress';
  this.progress.id = 'progress';
  this.dots = document.createElement('nav');
  this.dots.className = 'deck-dots';
  this.dots.id = 'dots';
  this.dots.setAttribute('aria-label', 'Slide navigation');
  this.counter = document.createElement('div');
  this.counter.className = 'deck-counter';
  this.counter.id = 'counter';
  this.hints = document.createElement('div');
  this.hints.className = 'deck-hints';
  this.hints.id = 'hints';
  this.hints.textContent = '← → scroll · M L C H T 3 · + − 0 diagram';
  document.body.append(this.progress, this.dots, this.counter, this.hints);
  this.dotItems = [];
  this.slides.forEach((_, i) => {
    const item = this.createDotItem(i);
    this.dotItems.push(item);
    this.dots.appendChild(item);
  });
};

SlideEngine.prototype.inScrollRegion = function (el) {
  return (
    el &&
    (el.closest('.mermaid-wrap') ||
      el.closest('.diagram-viewport') ||
      el.closest('.diagram-zoom-pane') ||
      el.closest('.table-scroll') ||
      el.closest('.premium-controls') ||
      document.documentElement.dataset.marker === 'on')
  );
};

SlideEngine.prototype.goTo = function (i) {
  this.slides[i]?.scrollIntoView({ behavior: 'smooth' });
};

SlideEngine.prototype.pushHash = function (slide) {
  if (!slide || !slide.id) return;
  try {
    history.pushState(null, '', '#' + slide.id);
  } catch (_err) {
    try { history.replaceState(null, '', '#' + slide.id); } catch (_e) {}
  }
};

SlideEngine.prototype.onPopState = function () {
  const hash = (location.hash || '').replace(/^#/, '');
  if (!hash) return;
  const target = this.slides.findIndex((s) => s.id === hash);
  if (target >= 0 && target !== this.current) {
    this.slides[target]?.scrollIntoView({ behavior: 'smooth' });
  }
};

SlideEngine.prototype.next = function () {
  this.goTo(Math.min(this.current + 1, this.total - 1));
};

SlideEngine.prototype.prev = function () {
  this.goTo(Math.max(this.current - 1, 0));
};

SlideEngine.prototype.updateChrome = function () {
  if (!this.progress) return;
  this.progress.style.setProperty('--deck-progress', String((this.current + 1) / this.total));
  if (this.counter) this.counter.textContent = (this.current + 1) + ' / ' + this.total;
  if (this.dotItems.length) {
    this.dotItems.forEach((item, i) => {
      const active = i === this.current;
      item.classList.toggle('is-active', active);
      item.querySelector('.deck-dot')?.classList.toggle('active', active);
      const link = item.querySelector('.deck-dot-label');
      if (link) link.setAttribute('aria-current', active ? 'location' : 'false');
    });
  } else if (this.dots) {
    [...this.dots.querySelectorAll('.deck-dot')].forEach((d, i) =>
      d.classList.toggle('active', i === this.current)
    );
  }
  this.showDotNav();
};

// Send a full snapshot (titles, notes, current index, total) on the same
// channel the popup listens on. Prefer PremiumPresenter.postToPeer (global
// BC + postMessage + localStorage). Falls back to a per-session BC so older
// bundles without PremiumPresenter still work. Per-session BC was the bug:
// the popup listens on `premium-deck` (global) so `premium-deck:<sid>` posts
// never reached it.
SlideEngine.prototype.broadcastSnapshot = function () {
  const sessionId = document.documentElement.dataset.session;
  const seq = window.PremiumPresenter && typeof window.PremiumPresenter.nextStateSeq === 'function'
    ? window.PremiumPresenter.nextStateSeq() : undefined;
  const payload = {
    type: 'snapshot',
    sessionId,
    seq,
    index: this.current,
    total: this.total,
    titles: this.getAllTitles(),
    notes: this.slides.map((s) => this.getSlideNotesHtml(s)),
    bodyHtmls: this.slides.map((s) => this.getSlideSummaryHtml(s)),
  };
  if (window.PremiumPresenter && typeof window.PremiumPresenter.postToPeer === 'function') {
    try { window.PremiumPresenter.postToPeer(payload); return; } catch (_) {}
  }
  if (!sessionId) return;
  try {
    const ch = new BroadcastChannel('premium-deck:' + sessionId);
    ch.postMessage(payload);
    ch.close();
  } catch (_) {}
};

SlideEngine.prototype.broadcastSnapshotDebounced = function (ms) {
  clearTimeout(this._snapshotTimer);
  this._snapshotTimer = setTimeout(() => this.broadcastSnapshot(), ms || 50);
};

SlideEngine.prototype.observe = function () {
  const obs = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          // Only ONE slide is visible at a time. Remove .visible from siblings
          // so querySelector('.slide.visible') returns the actual current slide
          // (used by TTS, PNG export, etc.).
          this.slides.forEach((s) => {
            if (s !== e.target) s.classList.remove('visible');
          });
          e.target.classList.add('visible');
          this.current = this.slides.indexOf(e.target);
          this.updateChrome();
          this.pushHash(e.target);
          this.broadcastSlidechange(e.target);
          if (this.embedMode) {
            try {
              window.parent.postMessage({
                type: 'slidechange',
                index: this.current,
                id: e.target.id,
                title: this.getSlideTitle(e.target, this.current),
              }, '*');
            } catch (_) {}
          }
        }
      });
    },
    { root: this.deck, threshold: 0.5 }
  );
  this.slides.forEach((s) => obs.observe(s));
};

SlideEngine.prototype.broadcastSlidechange = function (slide) {
  const sessionId = document.documentElement.dataset.session;
  const idx = this.slides.indexOf(slide);
  const curTitle = this.getSlideTitle(slide, idx);
  const curNotes = this.getSlideNotesHtml(slide);
  const nextSlide = this.slides[idx + 1];
  const nextTitle = nextSlide ? this.getSlideTitle(nextSlide, idx + 1) : '';
  const nextNotes = nextSlide ? this.getSlideNotesHtml(nextSlide) : '';
  const seq = window.PremiumPresenter && typeof window.PremiumPresenter.nextStateSeq === 'function'
    ? window.PremiumPresenter.nextStateSeq() : undefined;
  const payload = {
    type: 'slidechange',
    sessionId,
    seq,
    index: idx,
    id: slide.id,
    total: this.total,
    title: curTitle,
    notes: curNotes,
    bodyHtml: this.getSlideSummaryHtml(slide),
    nextTitle: nextTitle || 'End of deck',
    nextNotes,
    nextBodyHtml: nextSlide ? this.getSlideSummaryHtml(nextSlide) : '',
  };
  // Same-window subscribers: BroadcastChannel does not echo to the sender,
  // so we also fire a CustomEvent on `window` for in-process listeners
  // (e.g. PremiumTts follow, future analytics hooks).
  try {
    window.dispatchEvent(new CustomEvent('premium:slidechange', { detail: payload }));
  } catch (_) {}
  // Cross-window: prefer PremiumPresenter.postToPeer (global BC + postMessage
  // to popup + localStorage — same 3 transports the popup listens on). Falls
  // back to a per-session BC so older bundles without PremiumPresenter still
  // work. Per-session BC was the bug: popup listens on `premium-deck` (global)
  // so `premium-deck:<sid>` posts never reached it.
  if (window.PremiumPresenter && typeof window.PremiumPresenter.postToPeer === 'function') {
    try { window.PremiumPresenter.postToPeer(payload); return; } catch (_) {}
  }
  if (!sessionId) return;
  try {
    const ch = new BroadcastChannel('premium-deck:' + sessionId);
    ch.postMessage(payload);
    ch.close();
  } catch (_) {}
};

SlideEngine.prototype.bindEvents = function () {
  document.addEventListener('keydown', (e) => {
    if (new URLSearchParams(location.search).get('presenter') === '1') return;
    if (this.inScrollRegion(document.activeElement)) return;
    if (['ArrowDown', 'ArrowRight', 'Space', 'PageDown'].includes(e.code)) {
      e.preventDefault();
      this.next();
    }
    if (['ArrowUp', 'ArrowLeft', 'PageUp'].includes(e.code)) {
      e.preventDefault();
      this.prev();
    }
    if (e.code === 'Home') {
      e.preventDefault();
      this.goTo(0);
    }
    if (e.code === 'End') {
      e.preventDefault();
      this.goTo(this.total - 1);
    }
    this.hints?.classList.add('faded');
  });
  let y = 0;
  this._touchStartedOnDiagram = false;
  this.deck.addEventListener(
    'touchstart',
    (e) => {
      y = e.touches[0].clientY;
      this._touchStartedOnDiagram = !!e.target.closest(
        '.mermaid-wrap, .diagram-viewport, .diagram-zoom-pane'
      );
    },
    { passive: true }
  );
  this.deck.addEventListener(
    'touchend',
    (e) => {
      if (this._touchStartedOnDiagram) return;
      const dy = y - e.changedTouches[0].clientY;
      if (Math.abs(dy) > 50) dy > 0 ? this.next() : this.prev();
    },
    { passive: true }
  );
  setTimeout(() => this.hints?.classList.add('faded'), 4000);
  window.addEventListener('popstate', () => this.onPopState());
};

SlideEngine.prototype.bindEmbed = function () {
  if (!this.embedMode) return;
  window.addEventListener('message', (e) => {
    if (!e.data || e.data.type !== 'goto') return;
    const idx = typeof e.data.index === 'number' ? e.data.index : null;
    const id = e.data.id || null;
    if (id) {
      const target = this.slides.find((s) => s.id === id);
      if (target) { target.scrollIntoView({ behavior: 'smooth' }); return; }
    }
    if (idx != null && idx >= 0 && idx < this.total) this.goTo(idx);
  });
  const sendResize = () => {
    try {
      const h = document.documentElement.scrollHeight;
      window.parent.postMessage({ type: 'resize', height: h }, '*');
    } catch (_) {}
  };
  sendResize();
  new ResizeObserver(sendResize).observe(document.body);
};

SlideEngine.prototype.showDotLabels = function () {
  if (!this.dots) return;
  this.showDotNav(SlideEngine.LABEL_HIDE_MS);
  this.dots.classList.add('deck-dots--labels-on');
  clearTimeout(this._labelHideTimer);
  this._labelHideTimer = setTimeout(() => {
    this.dots?.classList.remove('deck-dots--labels-on');
    this.scheduleDotNavHide(300);
  }, SlideEngine.LABEL_HIDE_MS);
};

SlideEngine.prototype.hideDotNav = function () {
  if (!this.dots) return;
  this.dots.classList.add('deck-dots--idle');
};

SlideEngine.prototype.scheduleDotNavHide = function (delay) {
  if (!this.dots) return;
  clearTimeout(this._dotNavTimer);
  this._dotNavTimer = setTimeout(() => this.hideDotNav(), delay ?? SlideEngine.NAV_HIDE_MS);
};

SlideEngine.prototype.showDotNav = function (delay) {
  if (!this.dots) return;
  clearTimeout(this._dotNavTimer);
  this.dots.classList.remove('deck-dots--idle');
  this.scheduleDotNavHide(delay ?? SlideEngine.NAV_HIDE_MS);
};

SlideEngine.prototype.bindDotLabels = function () {
  if (!this.dots) return;
  this.showDotLabels();
  this.dots.addEventListener('click', () => this.showDotLabels());
  this.dots.addEventListener('pointerenter', () => this.showDotNav());
  this.dots.addEventListener('pointermove', () => this.showDotNav());
  this.dots.addEventListener('pointerleave', () => this.scheduleDotNavHide(500));
  this.dots.addEventListener('focusin', () => this.showDotNav());
  this.dots.addEventListener('focusout', () => this.scheduleDotNavHide(500));
};

SlideEngine.prototype.exposeApi = function () {
  const self = this;
  const handlers = { slidechange: new Set(), tick: new Set() };
  window.PremiumDeckControls = {
    next() { self.next(); },
    prev() { self.prev(); },
    goTo(i) { self.goTo(i); },
    getTitles() { return self.getAllTitles(); },
    getNotes(index) {
      const s = self.slides[index];
      return s ? self.getSlideNotesHtml(s) : null;
    },
    getSummary(index) {
      const s = self.slides[index];
      return s ? self.getSlideSummaryHtml(s) : null;
    },
    getState() { return { index: self.current, total: self.total }; },
    on(type, handler) {
      if (handlers[type]) handlers[type].add(handler);
      return () => handlers[type] && handlers[type].delete(handler);
    },
  };
  // Re-broadcast on the global channel (PremiumPresenter.postToPeer) so
  // in-process subscribers (PremiumDeckControls.on('slidechange') — used by
  // TTS follow and any future analytics hooks) can pick up our own
  // broadcasts AND broadcasts from the popup. The popup is the only
  // legitimate sender, so sessionId filtering isn't required.
  try {
    const ch = new BroadcastChannel('premium-deck');
    ch.addEventListener('message', (e) => {
      if (!e.data) return;
      // Drop messages from other sessions. Legacy bundles without sessionId pass.
      const msgSid = e.data.sessionId;
      if (msgSid && msgSid !== document.documentElement.dataset.session) return;
      if (e.data.type === 'slidechange' && handlers.slidechange.size) {
        handlers.slidechange.forEach((h) => {
          try { h({ index: e.data.index, id: e.data.id, total: e.data.total, title: e.data.title, notes: e.data.notes, nextTitle: e.data.nextTitle, nextNotes: e.data.nextNotes }); } catch (_) {}
        });
      }
      if (e.data.type === 'tick' && handlers.tick.size) {
        handlers.tick.forEach((h) => {
          try { h({ remainingMs: e.data.remainingMs, elapsedMs: e.data.elapsedMs, running: e.data.running, state: e.data.state, mode: e.data.mode }); } catch (_) {}
        });
      }
    });
  } catch (_) {}
};

window.SlideEngine = SlideEngine;
