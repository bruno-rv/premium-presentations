/**
 * Premium Presentations — theme switch + runtime 3D modes (off/ambient/tilt/depth/card).
 * Usage: <html data-theme="warm" data-3d="off">
 *   <link rel="stylesheet" href=".../premium-themes.css">
 *   <script src=".../premium-controls.js" defer><\/script>
 * Press 3 / Shift+3 to cycle 3D modes. Author default via data-3d="<mode>";
 * legacy data-parallax="on" maps to ambient. The old unscoped localStorage
 * parallax key is intentionally ignored (never migrated).
 *
 * card mode: each component tilts independently on pointer hover (ball-on-table).
 */
(function () {
  const STORAGE_THEME = 'premium-theme';
  const STORAGE_3D = 'premium-3d';
  const STORAGE_CONTROLS_HIDDEN = 'premium-controls-hidden';
  const MODES_3D = ['off', 'ambient', 'tilt', 'depth', 'card'];
  // Slide chrome that must stay a direct child of .slide (containing block
  // and direct-child CSS rules depend on it) — never moved into the 3D frame.
  const FRAME_CHROME_SELECTOR =
    '.theme-visual, .slide__glow, .slide__number, .geo-particle, .notes, .slide-3d-frame';
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

  function mode3dStorageKey() {
    return document.documentElement.dataset.mode3dStorageKey || scopedStorageKey(STORAGE_3D);
  }

  function normalize3dMode(value) {
    return MODES_3D.includes(value) ? value : 'off';
  }

  function get3dMode() {
    return normalize3dMode(document.documentElement.getAttribute('data-3d'));
  }

  function mode3dLabel(mode) {
    return mode.charAt(0).toUpperCase() + mode.slice(1);
  }

  function refresh3dSelect(select) {
    select = select || document.getElementById('premium-3d');
    if (!select) return;
    if (!select.options.length) {
      MODES_3D.forEach((mode) => {
        const opt = document.createElement('option');
        opt.value = mode;
        opt.textContent = mode3dLabel(mode);
        select.appendChild(opt);
      });
    }
    select.value = get3dMode();
  }

  let toastTimer = 0;

  function show3dToast(mode) {
    let toast = document.getElementById('premium-3d-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'premium-3d-toast';
      toast.className = 'premium-3d-toast';
      toast.setAttribute('role', 'status');
      toast.setAttribute('aria-live', 'polite');
      document.body.appendChild(toast);
    }
    toast.textContent = '3D: ' + mode.toUpperCase();
    toast.classList.add('is-visible');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 1200);
  }

  function apply3dMode(mode, opts) {
    mode = normalize3dMode(mode);
    const root = document.documentElement;
    root.setAttribute('data-3d', mode);
    // Mirror the legacy attribute for CSS/decks that key off data-parallax.
    root.dataset.parallax = mode === 'off' ? 'off' : 'on';
    if (!opts || opts.persist !== false) {
      try { localStorage.setItem(mode3dStorageKey(), mode); } catch (_) {}
    }
    refresh3dSelect();
    syncMotion();
    if (mode === 'card') mountCardTilt();
    else unmountCardTilt();
    root.dispatchEvent(new CustomEvent('premium-3d-change', { detail: { mode } }));
  }

  function set3dMode(mode) {
    apply3dMode(mode);
    show3dToast(get3dMode());
  }

  function cycle3d(dir) {
    dir = dir === -1 ? -1 : 1;
    const idx = MODES_3D.indexOf(get3dMode());
    set3dMode(MODES_3D[(idx + dir + MODES_3D.length) % MODES_3D.length]);
  }

  // Compatibility wrappers — presenter popup and external callers use these.
  function setParallax(on) {
    set3dMode(on ? 'ambient' : 'off');
  }

  function toggleParallax() {
    const mode = get3dMode();
    if (mode === 'off') set3dMode('ambient');
    else if (mode === 'ambient') set3dMode('off');
    else set3dMode('off');
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
      // e.code, not e.key: Shift+3 produces layout-specific characters ('#', etc.).
      if (e.code === 'Digit3') {
        e.preventDefault();
        cycle3d(e.shiftKey ? -1 : 1);
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

  let bgCanvas = null;

  function mountBackground() {
    if (document.querySelector('.premium-bg-3d')) {
      if (!bgCanvas) bgCanvas = document.querySelector('.premium-bg-3d__canvas');
      return;
    }
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
    bgCanvas = wrap.firstElementChild;
  }

  function themeVisualBase() {
    const configured = document.documentElement.dataset.themeVisualBase;
    if (configured) return configured.replace(/\/?$/, '/');
    if (SCRIPT_SRC) return new URL('assets/theme-visuals/', SCRIPT_SRC).href;

    const path = location.pathname;
    if (path.includes('/decks/')) return '../../shared/assets/theme-visuals/';
    if (path.includes('/studio/') || path.includes('/templates/')) {
      return '../shared/assets/theme-visuals/';
    }
    return 'shared/assets/theme-visuals/';
  }

  function safeThemeVisualValue(value) {
    const raw = String(value || '').trim();
    if (!raw) return '';
    if (/^data:image\//i.test(raw)) return raw;
    if (/^blob:/i.test(raw)) return raw;
    if (/^[a-z0-9][a-z0-9-]*-(?:hero|map)\.(?:webp|png|jpg|jpeg|gif|svg)$/i.test(raw)) {
      return raw;
    }
    return '';
  }

  function themeVisualSrc(theme, role) {
    const root = document.documentElement;
    const normalized = normalizeTheme(theme || root.dataset.theme || discoverThemes()[0]);
    const fromAttr =
      safeThemeVisualValue(root.getAttribute('data-theme-visual-' + normalized + '-' + role)) ||
      safeThemeVisualValue(root.getAttribute('data-theme-visual-' + normalized));
    const fromGlobal = window.PremiumThemeVisuals &&
      window.PremiumThemeVisuals[normalized] &&
      (safeThemeVisualValue(window.PremiumThemeVisuals[normalized][role]) ||
        safeThemeVisualValue(window.PremiumThemeVisuals[normalized].hero));
    const file = fromAttr || fromGlobal;
    if (!file) return '';
    if (/^data:image\//i.test(file) || /^blob:/i.test(file)) return file;
    return themeVisualBase() + file;
  }

  function syncThemeVisuals(theme) {
    const normalized = normalizeTheme(theme || document.documentElement.dataset.theme || discoverThemes()[0]);
    document.querySelectorAll('.theme-visual').forEach((visual) => {
      const role = visual.dataset.themeVisualRole || 'hero';
      const img = visual.querySelector('.theme-visual__image');
      if (!img) return;
      const src = themeVisualSrc(normalized, role);
      if (!src) {
        img.removeAttribute('src');
        visual.hidden = true;
        return;
      }
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
        const fallback = themeVisualSrc(current, 'hero');
        if (fallback) {
          img.setAttribute('src', fallback);
          return;
        }
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

  async function prepareAndPrintPdf() {
    if (document.body.classList.contains('print-pdf')) return;
    document.body.classList.add('print-pdf');

    document.querySelectorAll('#deck .slide').forEach((s) => s.classList.add('visible'));

    if (document.fonts && document.fonts.ready) {
      try { await document.fonts.ready; } catch (_) {}
    }

    await Promise.all(
      [...document.images].map((img) =>
        img.complete
          ? Promise.resolve()
          : new Promise((resolve) => {
              img.onload = resolve;
              img.onerror = resolve;
            })
      )
    );

    const pendingMermaid = document.querySelectorAll('.mermaid-wrap pre.mermaid');
    let needsMermaidWait = false;
    pendingMermaid.forEach((el) => {
      if (!el.querySelector('svg')) needsMermaidWait = true;
    });
    if (needsMermaidWait) {
      await new Promise((resolve) => setTimeout(resolve, 500));
    }

    await new Promise((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(resolve));
    });

    window.print();
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

    const mode3dGroup = document.createElement('div');
    mode3dGroup.className = 'premium-controls__group';
    mode3dGroup.innerHTML = '<label for="premium-3d">3D</label>';
    const mode3dSelect = document.createElement('select');
    mode3dSelect.id = 'premium-3d';
    mode3dSelect.title = '3D mode (3 / Shift+3)';
    refresh3dSelect(mode3dSelect);
    mode3dSelect.addEventListener('change', () => set3dMode(mode3dSelect.value));
    mode3dGroup.appendChild(mode3dSelect);

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
      prepareAndPrintPdf();
    });
    printGroup.appendChild(printBtn);
    panel.appendChild(printGroup);

    const hint = document.createElement('p');
    hint.className = 'premium-controls__hint';
    hint.textContent = 'M marker · L laser · C clear · H hide · T theme · 3 3D mode';

    panel.appendChild(themeGroup);
    panel.appendChild(mode3dGroup);
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

  // ---------- card mode: per-element tilt (ball-on-table) ----------
  // Each tiltable component tracks the pointer relative to its own center,
  // writes --card-rx / --card-ry / --card-glare CSS vars, and lets CSS
  // handle perspective + transition. No RAF needed — each element is independent.
  const CARD_TILT_TARGETS = [
    '.stat-card', '.glass-card', '.compare-panel', '.stage-card',
    '.code-window', '.terminal-window', '.flow-node', '.kpi',
    '.setup-step', '.pipeline-stage', '.checklist-item',
    '.tl-col', '.aside-card', '.why-panel'
  ].join(',');
  const CARD_MAX_TILT = 14; // degrees
  let cardTiltBound = false;

  // CSS transitions don't re-fire on var() changes without @property registration.
  // Set style.transform directly: instant tracking on move, eased return on leave.
  function onCardPointerMove(e) {
    const el = e.currentTarget;
    const r = el.getBoundingClientRect();
    const nx = (e.clientX - (r.left + r.width * 0.5)) / (r.width * 0.5);
    const ny = (e.clientY - (r.top + r.height * 0.5)) / (r.height * 0.5);
    const rx = (-ny * CARD_MAX_TILT).toFixed(2);
    const ry = (nx * CARD_MAX_TILT).toFixed(2);
    el.style.transition = 'none';
    el.style.transform = 'perspective(700px) rotateX(' + rx + 'deg) rotateY(' + ry + 'deg) translateZ(2px)';
    el.style.setProperty('--card-glare', ((nx * 0.5 + 0.5) * 100).toFixed(1) + '%');
  }

  function onCardPointerLeave(e) {
    const el = e.currentTarget;
    // Force reflow so the browser captures the current transform as "from" state,
    // then re-enable transition for the eased return to flat.
    el.offsetHeight; // eslint-disable-line no-unused-expressions
    el.style.transition = 'transform 0.35s ease-out';
    el.style.transform = '';
    el.style.removeProperty('--card-glare');
  }

  function mountCardTilt() {
    if (cardTiltBound || reducedMotionQuery.matches || !finePointerQuery.matches) return;
    cardTiltBound = true;
    document.querySelectorAll(CARD_TILT_TARGETS).forEach(function (el) {
      el.addEventListener('pointermove', onCardPointerMove, { passive: true });
      el.addEventListener('pointerleave', onCardPointerLeave, { passive: true });
    });
  }

  function unmountCardTilt() {
    if (!cardTiltBound) return;
    cardTiltBound = false;
    document.querySelectorAll(CARD_TILT_TARGETS).forEach(function (el) {
      el.removeEventListener('pointermove', onCardPointerMove);
      el.removeEventListener('pointerleave', onCardPointerLeave);
      el.style.removeProperty('transition');
      el.style.removeProperty('transform');
      el.style.removeProperty('--card-glare');
    });
  }

  // ---------- 3D motion engine ----------
  // One eased cursor state drives the ambient canvas, tilt vars, and depth
  // parallax. JS writes custom properties; CSS owns the transforms.
  let motionBound = false;
  let settling = false;
  let raf = 0;
  let targetX = 0;
  let targetY = 0;
  let currentX = 0;
  let currentY = 0;
  let activeFrame = null;
  let lifecycleBound = false;

  // Guarded: environments without matchMedia (JSDOM) must not kill the module.
  function safeMatchMedia(query) {
    try {
      if (typeof window.matchMedia === 'function') return window.matchMedia(query);
    } catch (_) {}
    return { matches: false, addEventListener: function () {}, removeEventListener: function () {} };
  }
  const reducedMotionQuery = safeMatchMedia('(prefers-reduced-motion: reduce)');
  const finePointerQuery = safeMatchMedia('(any-hover: hover) and (any-pointer: fine)');

  function motionAllowed() {
    return get3dMode() !== 'off' &&
      !reducedMotionQuery.matches &&
      finePointerQuery.matches &&
      !document.hidden;
  }

  function syncMotion() {
    if (motionAllowed()) bindMotion();
    else unbindMotion();
  }

  function bindMotion() {
    settling = false;
    if (motionBound) return;
    motionBound = true;
    document.addEventListener('pointermove', onMove, { passive: true });
    if (!raf) tick();
  }

  function unbindMotion() {
    motionBound = false;
    settling = false;
    document.removeEventListener('pointermove', onMove);
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    targetX = targetY = currentX = currentY = 0;
    if (bgCanvas) bgCanvas.style.transform = '';
    clearFrameVars(activeFrame);
  }

  // Ease back to neutral, then stop the loop (pointer left / window blurred).
  function settleMotion() {
    if (!motionBound) return;
    targetX = 0;
    targetY = 0;
    settling = true;
  }

  function clearFrameVars(frame) {
    if (!frame) return;
    frame.style.removeProperty('--tilt-x');
    frame.style.removeProperty('--tilt-y');
  }

  function retargetFrame() {
    const next = document.querySelector('.slide.visible .slide-3d-frame');
    if (next === activeFrame) return;
    clearFrameVars(activeFrame);
    activeFrame = next;
  }

  function onMove(e) {
    targetX = (e.clientX / window.innerWidth - 0.5) * 2;
    targetY = (e.clientY / window.innerHeight - 0.5) * 2;
    settling = false;
    retargetFrame();
    // The settle path stops the loop but keeps this listener attached so the
    // pointer returning revives motion without re-binding.
    if (!raf && motionAllowed()) {
      motionBound = true;
      tick();
    }
  }

  function tick() {
    if (!motionBound) { raf = 0; return; }
    currentX += (targetX - currentX) * 0.08;
    currentY += (targetY - currentY) * 0.08;
    const mode = get3dMode();
    if (bgCanvas && mode !== 'off') {
      const rotY = currentX * 6;
      const rotX = -currentY * 5;
      const tx = currentX * 18;
      const ty = currentY * 12;
      bgCanvas.style.transform =
        'perspective(1200px) rotateX(' + rotX + 'deg) rotateY(' + rotY + 'deg) translate3d(' + tx + 'px,' + ty + 'px,0)';
    }
    if (mode === 'tilt' || mode === 'depth') {
      if (activeFrame) {
        // ≤4° — small angles limit text rasterization blur.
        activeFrame.style.setProperty('--tilt-x', (-currentY * 4).toFixed(3) + 'deg');
        activeFrame.style.setProperty('--tilt-y', (currentX * 4).toFixed(3) + 'deg');
      }
    }
    if (settling && Math.abs(currentX) < 0.001 && Math.abs(currentY) < 0.001) {
      motionBound = false;
      settling = false;
      raf = 0;
      return;
    }
    raf = requestAnimationFrame(tick);
  }

  function bindMotionLifecycle() {
    if (lifecycleBound) return;
    lifecycleBound = true;
    document.addEventListener('pointerleave', settleMotion);
    window.addEventListener('blur', settleMotion);
    document.addEventListener('visibilitychange', syncMotion);
    window.addEventListener('premium:slidechange', retargetFrame);
    try {
      reducedMotionQuery.addEventListener('change', syncMotion);
      finePointerQuery.addEventListener('change', syncMotion);
    } catch (_) {
      // Older Safari: addListener fallback.
      try {
        reducedMotionQuery.addListener(syncMotion);
        finePointerQuery.addListener(syncMotion);
      } catch (_e) {}
    }
  }

  // Wrap each slide's content children in a .slide-3d-frame so tilt/depth
  // transforms never touch the scroll-snap / IntersectionObserver target.
  // Chrome (theme visuals, glow, numbers, particles, notes) stays a direct
  // child of .slide — its containing block and the direct-child CSS rules
  // in premium-deck.css are unaffected.
  function mount3dFrames() {
    document.querySelectorAll('.slide').forEach((slide) => {
      if (slide.querySelector(':scope > .slide-3d-frame')) return;
      const frame = document.createElement('div');
      frame.className = 'slide-3d-frame';
      const content = Array.from(slide.children).filter(
        (child) => !child.matches(FRAME_CHROME_SELECTOR)
      );
      content.forEach((child) => frame.appendChild(child));
      slide.appendChild(frame);
    });
  }

  function restorePreferences() {
    const root = document.documentElement;
    const themes = discoverThemes();
    try {
      const t = normalizeTheme(localStorage.getItem(themeStorageKey()) || '');
      if (t && (themes.includes(t) || isThemeName(t))) root.dataset.theme = t;
    } catch (_) {}
    root.dataset.theme = normalizeTheme(root.dataset.theme || themes[0]);
    if (!isThemeName(root.dataset.theme)) root.dataset.theme = themes[0] || 'warm';
    syncFonts(root.dataset.theme);

    // 3D mode resolution: stored (scoped) → author data-3d → legacy
    // data-parallax="on" attr → off. The old unscoped localStorage parallax
    // key is intentionally NOT read (re-globalizing it across decks is worse
    // than asking the user to press 3 once).
    let stored = null;
    try { stored = localStorage.getItem(mode3dStorageKey()); } catch (_) {}
    let mode;
    if (stored !== null && MODES_3D.includes(stored)) {
      mode = stored;
    } else if (MODES_3D.includes(root.getAttribute('data-3d'))) {
      mode = root.getAttribute('data-3d');
    } else if (root.dataset.parallax === 'on') {
      mode = 'ambient';
    } else {
      mode = 'off';
    }
    apply3dMode(mode, { persist: false });

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
    mount3dFrames();
    // Skip shell mount in presenter popup — the popup has its own instrument
    // panel and we don't want a 3D select or toast overlaid on it.
    if (!isPresenterPopup()) mountControls();
    bindControlShortcuts();
    bindMotionLifecycle();
    restorePreferences();
    mountThemeVisuals();
    const sel = document.getElementById('premium-theme');
    if (sel) refreshThemeSelect(sel);
    refresh3dSelect();
  }

  // ?print-pdf query auto-activates print mode once the deck is laid out.
  if (new URLSearchParams(location.search).get('print-pdf') === '1') {
    const runPrint = () => { prepareAndPrintPdf(); };
    if (document.readyState === 'complete') {
      runPrint();
    } else {
      window.addEventListener('load', runPrint, { once: true });
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
    set3dMode,
    cycle3d,
    get3dMode,
    MODES_3D: MODES_3D.slice(),
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
    exportPdf: prepareAndPrintPdf,
  };
})();
/* Marker + laser: shared/premium-annotations.js */
