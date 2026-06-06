/**
 * Red brand chrome — top bar for data-theme="red".
 * Visual style: red bar + red square mark on the left, optional right label.
 * No wordmark text (per spec).
 *
 * Optional (set on <html>):
 *   data-red-chrome="off"
 *   data-red-hero="on"            — large mark on title slides
 *   data-red-bar-right="…"        — right label (deck title, date)
 *   data-red-bar-mark="off"       — hide the mark in the bar
 */
(function () {
  const RED_THEMES = ['red'];
  const MARK_SRC = '../../shared/assets/red-mark.svg';
  const MARK_SRC_LIGHT = '../../shared/assets/red-mark.svg';

  function markImg(className, alt, src) {
    return (
      '<img class="red-mark ' +
      className +
      '" src="' +
      (src || MARK_SRC) +
      '" width="48" height="48" alt="' +
      escapeHtml(alt) +
      '" decoding="async" />'
    );
  }

  function isRedTheme() {
    return RED_THEMES.includes(document.documentElement.dataset.theme);
  }

  function chromeEnabled() {
    return document.documentElement.dataset.redChrome !== 'off';
  }

  function resolveMarkSrc() {
    const custom = document.documentElement.dataset.redMarkSrc;
    if (custom) return custom;
    const bar = document.querySelector('.red-brand-bar img.red-mark');
    if (bar?.getAttribute('src')) return bar.getAttribute('src');
    const sample = document.querySelector('img.red-mark[src]');
    if (sample?.getAttribute('src')) return sample.getAttribute('src');
    return MARK_SRC;
  }

  /** Title slides: mark in the chosen chrome variant. */
  function resolveHeroMarkSrc() {
    if (document.documentElement.dataset.redHeroMark === 'header') {
      return resolveMarkSrc();
    }
    return MARK_SRC_LIGHT;
  }

  function mountBrandBar() {
    if (!isRedTheme() || !chromeEnabled()) {
      document.querySelector('.red-brand-bar')?.remove();
      return;
    }

    const existing = document.querySelector('.red-brand-bar');
    const right =
      document.documentElement.dataset.redBarRight ||
      document.querySelector('[data-red-bar-right]')?.textContent?.trim() ||
      '';
    const src = resolveMarkSrc();
    const showMark = document.documentElement.dataset.redBarMark !== 'off';

    const startHtml = showMark
      ? '<div class="red-brand-bar__start">' +
        '<img class="red-mark red-mark--sm" src="' +
        escapeHtml(src) +
        '" width="32" height="32" alt="" decoding="async" />' +
        '</div>'
      : '';

    const html =
      startHtml +
      '<span class="red-brand-bar__right">' +
      (right ? escapeHtml(right) : '') +
      '</span>';

    if (existing) {
      existing.innerHTML = html;
      return;
    }

    const bar = document.createElement('header');
    bar.className = 'red-brand-bar';
    bar.setAttribute('role', 'banner');
    bar.innerHTML = html;
    document.body.appendChild(bar);
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function heroEnabled() {
    return document.documentElement.dataset.redHero === 'on';
  }

  function injectHeroMarks() {
    document.querySelectorAll('.red-mark-hero[data-red-injected]').forEach((el) => {
      el.remove();
    });
    if (!isRedTheme() || !heroEnabled()) return;

    const src = resolveHeroMarkSrc();
    document.querySelectorAll('.slide--title').forEach((slide) => {
      if (slide.querySelector('.theme-visual')) return;
      if (slide.querySelector('.red-mark-hero')) return;
      const hero = document.createElement('div');
      hero.className = 'red-mark-hero reveal';
      hero.dataset.redInjected = 'true';
      hero.innerHTML = markImg('red-mark--xl', 'Red', src);
      const first = slide.querySelector('.slide__glow, .slide__subtitle, .reveal, h1');
      if (first) slide.insertBefore(hero, first);
      else slide.prepend(hero);
    });
  }

  function refresh() {
    mountBrandBar();
    injectHeroMarks();
  }

  function init() {
    refresh();
    document.documentElement.addEventListener('premium-theme-change', refresh);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }

  window.PremiumRedChrome = { refresh, mountBrandBar, injectHeroMarks };
})();
