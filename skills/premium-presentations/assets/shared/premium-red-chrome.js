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
  const RED_MARK_SVG =
    '<svg class="red-mark {{CLASS}}" width="48" height="48" viewBox="0 0 48 48" ' +
    'xmlns="http://www.w3.org/2000/svg" {{ARIA}}>' +
    '<rect x="0" y="0" width="48" height="48" rx="10" ry="10" fill="#FF0230"></rect>' +
    '<rect x="16" y="16" width="16" height="16" rx="2" ry="2" fill="#FFFFFF"></rect>' +
    '</svg>';

  function markImg(className, alt, src) {
    if (isPortableImageSrc(src)) {
      return (
        '<img class="red-mark ' +
        className +
        '" src="' +
        escapeHtml(src) +
        '" width="48" height="48" alt="' +
        escapeHtml(alt) +
        '" decoding="async" />'
      );
    }

    const aria = alt
      ? 'role="img" aria-label="' + escapeHtml(alt) + '"'
      : 'aria-hidden="true" focusable="false"';
    return (
      RED_MARK_SVG
        .replace('{{CLASS}}', escapeHtml(className))
        .replace('{{ARIA}}', aria)
    );
  }

  function isPortableImageSrc(src) {
    return /^data:image\//i.test(src || '');
  }

  function isRedTheme() {
    return RED_THEMES.includes(document.documentElement.dataset.theme);
  }

  function chromeEnabled() {
    return document.documentElement.dataset.redChrome !== 'off';
  }

  function resolveMarkSrc() {
    const custom = document.documentElement.dataset.redMarkSrc;
    if (isPortableImageSrc(custom)) return custom;
    const bar = document.querySelector('.red-brand-bar img.red-mark');
    if (isPortableImageSrc(bar?.getAttribute('src'))) return bar.getAttribute('src');
    const sample = document.querySelector('img.red-mark[src]');
    if (isPortableImageSrc(sample?.getAttribute('src'))) return sample.getAttribute('src');
    return '';
  }

  /** Title slides: mark in the chosen chrome variant. */
  function resolveHeroMarkSrc() {
    if (document.documentElement.dataset.redHeroMark === 'header') {
      return resolveMarkSrc();
    }
    return '';
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
        markImg('red-mark--sm', '', src) +
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
