/**
 * Premium Presentations — theme switch + optional 3D parallax background.
 * Usage: <html data-theme="warm" data-parallax="off">
 *   <link rel="stylesheet" href=".../premium-themes.css">
 *   <script src=".../premium-controls.js" defer><\/script>
 */
(function () {
  const STORAGE_THEME = 'premium-theme';
  const STORAGE_PARALLAX = 'premium-parallax';
  const STORAGE_CONTROLS_HIDDEN = 'premium-controls-hidden';
  const SCRIPT_SRC = document.currentScript && document.currentScript.src
    ? document.currentScript.src
    : '';
  let cachedThemes = null;

  function scopedStorageKey(key) {
    const path = location && location.pathname ? location.pathname : 'document';
    return key + ':' + path;
  }

  function themeStorageKey() {
    return document.documentElement.dataset.themeStorageKey || scopedStorageKey(STORAGE_THEME);
  }

  function controlsShell() {
    return document.querySelector('.premium-controls-shell');
  }

  function isControlsHidden() {
    return document.documentElement.dataset.controlsHidden === 'on';
  }

  function setControlsOpen(open) {
    const shell = controlsShell();
    const tab = document.getElementById('premium-controls-tab');
    if (!shell) return;
    shell.classList.toggle('is-open', open);
    if (tab) tab.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  function setControlsHidden(hidden) {
    const shell = controlsShell();
    document.documentElement.dataset.controlsHidden = hidden ? 'on' : 'off';
    if (shell) {
      shell.classList.toggle('is-hidden', hidden);
      if (hidden) {
        setControlsOpen(false);
      } else {
        setControlsOpen(true);
      }
    }
    try {
      localStorage.setItem(STORAGE_CONTROLS_HIDDEN, hidden ? 'on' : 'off');
    } catch (_) {}
  }

  function toggleControlsHidden() {
    setControlsHidden(!isControlsHidden());
  }

  function isParallaxOn() {
    return document.documentElement.dataset.parallax === 'on';
  }

  function syncParallaxButton() {
    const btn = document.getElementById('premium-parallax-toggle');
    if (btn) btn.setAttribute('aria-pressed', isParallaxOn() ? 'true' : 'false');
  }

  function toggleParallax() {
    setParallax(!isParallaxOn());
    syncParallaxButton();
  }

  function isTypingTarget(el) {
    if (!el) return false;
    const tag = el.tagName;
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return true;
    if (el.isContentEditable) return true;
    return false;
  }

  function isPresenterPopup() {
    return new URLSearchParams(location.search).get('presenter') === '1';
  }

  function bindControlShortcuts() {
    if (document.documentElement.dataset.controlShortcutsBound) return;
    document.documentElement.dataset.controlShortcutsBound = '1';

    document.addEventListener('keydown', (e) => {
      if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
      if (isTypingTarget(e.target)) return;
      if (isPresenterPopup()) return;

      const key = e.key.toLowerCase();
      if (key === 'h') {
        e.preventDefault();
        toggleControlsHidden();
        return;
      }
      if (key === '3') {
        e.preventDefault();
        toggleParallax();
        return;
      }
      if (key === 'b' || key === '.') {
        e.preventDefault();
        toggleCurtain();
        return;
      }
      if (key === 't' && !e.shiftKey) {
        e.preventDefault();
        cycleTheme();
      }
      if (key === 't' && e.shiftKey) {
        e.preventDefault();
        if (window.PremiumTimer) {
          if (window.PremiumTimer.getState().running) {
            window.PremiumTimer.pause();
          } else {
            window.PremiumTimer.start();
          }
        }
        return;
      }
      if (key === 'e' && e.shiftKey) {
        e.preventDefault();
        const btn = document.getElementById('premium-print-pdf');
        if (btn) btn.click();
        return;
      }
    });
  }

  function normalizeTheme(name) {
    name = name || '';
    return document.documentElement.getAttribute('data-theme-alias-' + name) || name;
  }

  function isThemeName(name) {
    return /^[a-z0-9][a-z0-9-]*$/.test(name || '');
  }

  function addThemeFromSelector(selectorText, add) {
    const re = /html\[data-theme=(?:"([^"]+)"|'([^']+)'|([^\]\s]+))\]/g;
    let match;
    while ((match = re.exec(selectorText || ''))) {
      add(normalizeTheme(match[1] || match[2] || match[3] || ''));
    }
  }

  function readThemeRules(rules, add) {
    Array.from(rules || []).forEach((rule) => {
      if (rule.selectorText) addThemeFromSelector(rule.selectorText, add);
      if (rule.cssRules) {
        try { readThemeRules(rule.cssRules, add); } catch (_) {}
      }
    });
  }

  function discoverThemes() {
    if (cachedThemes && cachedThemes.length) return cachedThemes.slice();
    const root = document.documentElement;
    const themes = [];
    const add = (name) => {
      name = normalizeTheme((name || '').trim());
      if (isThemeName(name) && !themes.includes(name)) themes.push(name);
    };

    (root.dataset.themes || '').split(',').forEach(add);
    Array.from(document.styleSheets || []).forEach((sheet) => {
      try { readThemeRules(sheet.cssRules, add); } catch (_) {}
    });
    add(root.dataset.theme);
    if (!themes.length) add('warm');
    cachedThemes = themes;
    return themes.slice();
  }

  function humanizeTheme(name) {
    return (name || '')
      .split('-')
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  }

  function themeLabel(name) {
    return document.documentElement.getAttribute('data-theme-label-' + name) || humanizeTheme(name);
  }

  function refreshThemeSelect(select) {
    select = select || document.getElementById('premium-theme');
    if (!select) return;
    const root = document.documentElement;
    const current = normalizeTheme(root.dataset.theme || discoverThemes()[0]);
    const themes = discoverThemes();
    if (isThemeName(current) && !themes.includes(current)) themes.push(current);
    select.innerHTML = '';
    themes.forEach((theme) => {
      const opt = document.createElement('option');
      opt.value = theme;
      opt.textContent = themeLabel(theme);
      select.appendChild(opt);
    });
    select.value = current;
  }

  function mountBackground() {
    if (document.querySelector('.premium-bg-3d')) return;
    const wrap = document.createElement('div');
    wrap.className = 'premium-bg-3d';
    wrap.setAttribute('aria-hidden', 'true');
    wrap.innerHTML =
      '<div class="premium-bg-3d__canvas">' +
      '<div class="premium-bg-3d__glow premium-bg-3d__glow--a"></div>' +
      '<div class="premium-bg-3d__glow premium-bg-3d__glow--b"></div>' +
      '<div class="premium-bg-3d__grid"></div>' +
      '</div>';
    document.body.prepend(wrap);
  }

  function themeVisualBase() {
    const configured = document.documentElement.dataset.themeVisualBase;
    if (configured) return configured.replace(/\/?$/, '/');
    if (SCRIPT_SRC) return new URL('assets/chatgpt-theme-visuals/', SCRIPT_SRC).href;

    const path = location.pathname;
    if (path.includes('/decks/')) return '../../shared/assets/chatgpt-theme-visuals/';
    if (path.includes('/assets/studio/')) {
      return '../../shared/assets/chatgpt-theme-visuals/';
    }
    if (path.includes('/templates/')) {
      return '../shared/assets/chatgpt-theme-visuals/';
    }
    return 'shared/assets/chatgpt-theme-visuals/';
  }

  function themeVisualSrc(theme, role) {
    const root = document.documentElement;
    const normalized = normalizeTheme(theme || root.dataset.theme || discoverThemes()[0]);
    const fromAttr =
      root.getAttribute('data-theme-visual-' + normalized + '-' + role) ||
      root.getAttribute('data-theme-visual-' + normalized);
    const fromGlobal = window.PremiumThemeVisuals &&
      window.PremiumThemeVisuals[normalized] &&
      (window.PremiumThemeVisuals[normalized][role] || window.PremiumThemeVisuals[normalized].hero);
    const file = fromAttr || fromGlobal || (normalized + '-' + role + '.png');
    if (/^(?:https?:|file:|\/|\.\/|\.\.\/)/.test(file)) return file;
    return themeVisualBase() + file;
  }

  function syncThemeVisuals(theme) {
    const normalized = normalizeTheme(theme || document.documentElement.dataset.theme || discoverThemes()[0]);
    document.querySelectorAll('.theme-visual').forEach((visual) => {
      const role = visual.dataset.themeVisualRole || 'hero';
      const img = visual.querySelector('.theme-visual__image');
      if (!img) return;
      const src = themeVisualSrc(normalized, role);
      visual.hidden = false;
      img.dataset.themeVisualFallback = '';
      if (img.getAttribute('src') !== src) img.setAttribute('src', src);
    });
  }

  function injectThemeVisual(slide, role) {
    if (slide.dataset.themeVisual === 'off') return;
    if (slide.querySelector(':scope > .theme-visual')) return;

    const visual = document.createElement('figure');
    visual.className = 'theme-visual theme-visual--' + role;
    visual.dataset.themeVisualRole = role;
    visual.setAttribute('aria-hidden', 'true');

    const img = document.createElement('img');
    img.className = 'theme-visual__image';
    img.alt = '';
    img.decoding = 'async';
    img.loading = 'eager';
    img.addEventListener('error', () => {
      const current = normalizeTheme(document.documentElement.dataset.theme || discoverThemes()[0]);
      if (role !== 'hero' && img.dataset.themeVisualFallback !== 'hero') {
        img.dataset.themeVisualFallback = 'hero';
        img.setAttribute('src', themeVisualSrc(current, 'hero'));
        return;
      }
      visual.hidden = true;
    });
    visual.appendChild(img);

    slide.classList.add('has-theme-visual', 'has-theme-visual--' + role);
    slide.prepend(visual);
  }

  function mountThemeVisuals() {
    document.querySelectorAll('.slide--title').forEach((slide) => {
      injectThemeVisual(slide, 'hero');
    });
    document.querySelectorAll('.slide--divider').forEach((slide) => {
      injectThemeVisual(slide, 'map');
    });
    syncThemeVisuals(document.documentElement.dataset.theme);
  }

  function mountControls() {
    if (document.querySelector('.premium-controls-shell')) return;
    const root = document.documentElement;

    window.addEventListener('afterprint', () => {
      document.body.classList.remove('print-pdf');
    });

    const shell = document.createElement('div');
    shell.className = 'premium-controls-shell';

    const tab = document.createElement('button');
    tab.type = 'button';
    tab.className = 'premium-controls-tab';
    tab.id = 'premium-controls-tab';
    tab.setAttribute('aria-expanded', 'false');
    tab.setAttribute('aria-controls', 'premium-controls-panel');
    tab.title = 'Tools (hover or click to pin)';
    tab.innerHTML =
      '<span class="premium-controls-tab__icon" aria-hidden="true">◧</span>' +
      '<span class="premium-controls-tab__keys">MLCHT3</span>';

    const panel = document.createElement('div');
    panel.className = 'premium-controls';
    panel.id = 'premium-controls-panel';
    panel.setAttribute('role', 'group');
    panel.setAttribute('aria-label', 'Presentation controls');

    tab.addEventListener('click', () => {
      if (isControlsHidden()) setControlsHidden(false);
      setControlsOpen(!shell.classList.contains('is-open'));
    });

    const themeGroup = document.createElement('div');
    themeGroup.className = 'premium-controls__group';
    themeGroup.innerHTML = '<label for="premium-theme">Theme</label>';
    const select = document.createElement('select');
    select.id = 'premium-theme';
    refreshThemeSelect(select);
    select.addEventListener('change', () => setTheme(select.value));
    themeGroup.appendChild(select);

    const parallaxGroup = document.createElement('div');
    parallaxGroup.className = 'premium-controls__group';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'premium-parallax-toggle';
    btn.innerHTML = '3D<span class="premium-kbd">3</span>';
    btn.title = '3D parallax background (3)';
    btn.setAttribute('aria-pressed', root.dataset.parallax === 'on' ? 'true' : 'false');
    btn.addEventListener('click', toggleParallax);
    parallaxGroup.appendChild(btn);

    const curtainGroup = document.createElement('div');
    curtainGroup.className = 'premium-controls__group';
    const curtainBtn = document.createElement('button');
    curtainBtn.type = 'button';
    curtainBtn.id = 'premium-curtain-toggle';
    curtainBtn.innerHTML = 'Curtain<span class="premium-kbd">B</span>';
    curtainBtn.title = 'Blackout screen (B)';
    curtainBtn.addEventListener('click', toggleCurtain);
    curtainGroup.appendChild(curtainBtn);
    panel.appendChild(curtainGroup);
    syncCurtainButton();

    const timerGroup = document.createElement('div');
    timerGroup.className = 'premium-controls__group premium-controls__group--timer';
    const timerBtn = document.createElement('button');
    timerBtn.type = 'button';
    timerBtn.id = 'premium-timer-toggle';
    timerBtn.innerHTML = 'Timer<span class="premium-kbd">⇧T</span>';
    timerBtn.title = 'Start/pause speaker timer (Shift+T)';
    timerBtn.addEventListener('click', () => {
      if (!window.PremiumTimer) return;
      const st = window.PremiumTimer.getState();
      if (st && st.running) {
        window.PremiumTimer.pause();
      } else {
        // If duration is 0 or unset, apply the selected duration first.
        const sel = document.getElementById('premium-timer-duration');
        if (sel) {
          const m = parseFloat(sel.value);
          if (Number.isFinite(m) && m > 0) window.PremiumTimer.set(m);
        }
        window.PremiumTimer.start();
      }
    });
    timerGroup.appendChild(timerBtn);

    const durLabel = document.createElement('label');
    durLabel.htmlFor = 'premium-timer-duration';
    durLabel.textContent = 'min';
    const durSel = document.createElement('select');
    durSel.id = 'premium-timer-duration';
    durSel.title = 'Set presentation duration (minutes)';
    [
      { v: 5, t: '5' },
      { v: 10, t: '10' },
      { v: 15, t: '15' },
      { v: 20, t: '20' },
      { v: 25, t: '25' },
      { v: 30, t: '30' },
      { v: 45, t: '45' },
      { v: 60, t: '60' },
      { v: 90, t: '90' },
    ].forEach(({ v, t }) => {
      const opt = document.createElement('option');
      opt.value = String(v);
      opt.textContent = t;
      if (v === 30) opt.selected = true;
      durSel.appendChild(opt);
    });
    durSel.addEventListener('change', () => {
      const m = parseFloat(durSel.value);
      if (window.PremiumTimer && Number.isFinite(m) && m > 0) {
        window.PremiumTimer.set(m);
        // Persist the new duration for this deck so reloads keep it.
        try { window.PremiumTimer.writeOverride(m); } catch (_) {}
      }
    });
    timerGroup.appendChild(durLabel);
    timerGroup.appendChild(durSel);

    // Once the timer module loads, sync the dropdown to the active config
    // (so a <meta> tag override or localStorage preference is reflected).
    const syncDur = () => {
      if (!window.PremiumTimer) return;
      const st = window.PremiumTimer.getState();
      if (!st) return;
      const minutes = Math.round(st.totalMs / 60000);
      // Only sync if the user hasn't picked something else this session
      if (durSel.dataset.userSet === '1') return;
      const match = Array.from(durSel.options).find((o) => Number(o.value) === minutes);
      if (match) {
        durSel.value = match.value;
      } else {
        // Custom duration (e.g. 47min) — show it
        let opt = durSel.querySelector('option[data-custom]');
        if (!opt) {
          opt = document.createElement('option');
          opt.dataset.custom = '1';
          durSel.appendChild(opt);
        }
        opt.value = String(minutes);
        opt.textContent = String(minutes);
        durSel.value = String(minutes);
      }
    };
    durSel.addEventListener('change', () => { durSel.dataset.userSet = '1'; });
    if (window.PremiumTimer) syncDur();
    else {
      document.addEventListener('DOMContentLoaded', syncDur, { once: true });
      // PremiumTimer may load after this module; poll briefly.
      let tries = 0;
      const id = setInterval(() => {
        if (window.PremiumTimer || tries++ > 20) { clearInterval(id); syncDur(); }
      }, 100);
    }
    panel.appendChild(timerGroup);

    const printGroup = document.createElement('div');
    printGroup.className = 'premium-controls__group';
    const printBtn = document.createElement('button');
    printBtn.type = 'button';
    printBtn.id = 'premium-print-pdf';
    printBtn.innerHTML = 'PDF<span class="premium-kbd">⇧E</span>';
    printBtn.title = 'Export as PDF (Shift+E)';
    printBtn.addEventListener('click', () => {
      if (document.body.classList.contains('print-pdf')) return;
      document.body.classList.add('print-pdf');
      window.print();
    });
    printGroup.appendChild(printBtn);
    panel.appendChild(printGroup);

    const hint = document.createElement('p');
    hint.className = 'premium-controls__hint';
    hint.textContent = 'M marker · L laser · C clear · H hide · T theme · 3 parallax';

    panel.appendChild(themeGroup);
    panel.appendChild(parallaxGroup);
    panel.appendChild(hint);

    shell.appendChild(tab);
    shell.appendChild(panel);
    document.body.appendChild(shell);
    document.dispatchEvent(new CustomEvent('premium-controls-ready'));
  }

  function cycleTheme() {
    const themes = discoverThemes();
    if (!themes.length) return;
    const current = normalizeTheme(document.documentElement.dataset.theme || themes[0]);
    const idx = Math.max(0, themes.indexOf(current));
    setTheme(themes[(idx + 1) % themes.length]);
  }

  function setTheme(name) {
    name = normalizeTheme(name);
    if (!isThemeName(name)) return;
    if (cachedThemes && !cachedThemes.includes(name)) cachedThemes.push(name);
    document.documentElement.dataset.theme = name;
    try { localStorage.setItem(themeStorageKey(), name); } catch (_) {}
    refreshThemeSelect();
    syncFonts(name);
    syncThemeVisuals(name);
    document.documentElement.dispatchEvent(
      new CustomEvent('premium-theme-change', { detail: { theme: name } })
    );
  }

  function syncFonts(name) {
    const href = document.documentElement.getAttribute('data-theme-fonts-' + name);
    if (!href) return;
    const id = 'premium-theme-fonts';
    let link = document.getElementById(id);
    if (!link) {
      link = document.createElement('link');
      link.id = id;
      link.rel = 'stylesheet';
      document.head.appendChild(link);
    }
    if (link.href !== href) link.href = href;
  }

  function setParallax(on) {
    document.documentElement.dataset.parallax = on ? 'on' : 'off';
    try { localStorage.setItem(STORAGE_PARALLAX, on ? 'on' : 'off'); } catch (_) {}
    if (on) bindParallax();
    else unbindParallax();
    syncParallaxButton();
  }

  let parallaxBound = false;
  let raf = 0;
  let targetX = 0;
  let targetY = 0;
  let currentX = 0;
  let currentY = 0;

  function bindParallax() {
    if (parallaxBound || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    parallaxBound = true;
    document.addEventListener('mousemove', onMove, { passive: true });
    tick();
  }

  function unbindParallax() {
    parallaxBound = false;
    document.removeEventListener('mousemove', onMove);
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    const canvas = document.querySelector('.premium-bg-3d__canvas');
    if (canvas) canvas.style.transform = '';
  }

  function onMove(e) {
    const nx = (e.clientX / window.innerWidth - 0.5) * 2;
    const ny = (e.clientY / window.innerHeight - 0.5) * 2;
    targetX = nx;
    targetY = ny;
  }

  function tick() {
    if (!parallaxBound) return;
    currentX += (targetX - currentX) * 0.08;
    currentY += (targetY - currentY) * 0.08;
    const canvas = document.querySelector('.premium-bg-3d__canvas');
    if (canvas && document.documentElement.dataset.parallax === 'on') {
      const rotY = currentX * 6;
      const rotX = -currentY * 5;
      const tx = currentX * 18;
      const ty = currentY * 12;
      canvas.style.transform =
        'perspective(1200px) rotateX(' + rotX + 'deg) rotateY(' + rotY + 'deg) translate3d(' + tx + 'px,' + ty + 'px,0)';
    }
    raf = requestAnimationFrame(tick);
  }

  function restorePreferences() {
    const root = document.documentElement;
    const themes = discoverThemes();
    try {
      const t = normalizeTheme(localStorage.getItem(themeStorageKey()) || '');
      if (t && (themes.includes(t) || isThemeName(t))) root.dataset.theme = t;
      const p = localStorage.getItem(STORAGE_PARALLAX);
      if (p === 'on' || p === 'off') root.dataset.parallax = p;
    } catch (_) {}
    root.dataset.theme = normalizeTheme(root.dataset.theme || themes[0]);
    if (!isThemeName(root.dataset.theme)) root.dataset.theme = themes[0] || 'warm';
    if (!root.dataset.parallax) root.dataset.parallax = 'off';
    syncFonts(root.dataset.theme);
    if (root.dataset.parallax === 'on') bindParallax();
    const hidden = localStorage.getItem(STORAGE_CONTROLS_HIDDEN);
    if (hidden === 'on') setControlsHidden(true);
    else if (hidden === 'off') setControlsHidden(false);
  }

  function isCurtainOn() {
    return document.body.classList.contains('curtain');
  }

  function setCurtain(on, message) {
    document.body.classList.toggle('curtain', on);
    if (message) {
      document.body.dataset.curtainMessage = message;
      document.body.classList.add('curtain--message');
    } else {
      document.body.classList.remove('curtain--message');
      delete document.body.dataset.curtainMessage;
    }
  }

  function toggleCurtain() {
    setCurtain(!isCurtainOn());
    syncCurtainButton();
  }

  function syncCurtainButton() {
    const btn = document.getElementById('premium-curtain-toggle');
    if (btn) btn.setAttribute('aria-pressed', isCurtainOn() ? 'true' : 'false');
  }

  function init() {
    mountBackground();
    mountControls();
    bindControlShortcuts();
    restorePreferences();
    mountThemeVisuals();
    const sel = document.getElementById('premium-theme');
    if (sel) refreshThemeSelect(sel);
    syncParallaxButton();
  }

  // ?print-pdf query auto-activates print mode. Add the class as early as
  // possible (synchronously in the head if this script runs in the head,
  // otherwise at parse time) so the print stylesheet is applied before
  // layout, then trigger window.print() once everything is laid out.
  if (new URLSearchParams(location.search).get('print-pdf') === '1') {
    document.body.classList.add('print-pdf');
    if (document.readyState === 'complete') {
      window.print();
    } else {
      window.addEventListener('load', () => window.print(), { once: true });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumPresentations = {
    setTheme,
    cycleTheme,
    setParallax,
    toggleParallax,
    setControlsHidden,
    setControlsOpen,
    toggleControlsHidden,
    isControlsHidden,
    setCurtain,
    toggleCurtain,
    isCurtainOn,
    refreshThemeVisuals: mountThemeVisuals,
    getThemes: discoverThemes,
    THEMES: discoverThemes(),
  };
})();
/* Marker + laser: shared/premium-annotations.js */
