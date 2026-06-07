/**
 * Premium Presentations — text marker (selection → highlight) + laser pointer.
 */
(function () {
  const STORAGE_MARKER = 'premium-marker';
  const STORAGE_LASER = 'premium-laser';

  const SKIP_SEL =
    '.premium-controls, .deck-dots, .deck-dot, .deck-dot-label, .mermaid-wrap, .diagram-zoom-toolbar, .diagram-zoom-btn, button, select, input, textarea';

  let laserEl = null;
  let laserDot = null;
  let laserRingWrap = null;
  let laserTrails = [];
  let laserX = 0;
  let laserY = 0;
  let laserTargetX = 0;
  let laserTargetY = 0;
  let laserRaf = 0;
  let laserBound = false;
  let laserClickBound = false;
  const LASER_TRAIL_COUNT = 3;

  const LASER_SKIP_CLICK =
    'a[href], button, select, input, textarea, .deck-dot, .deck-dot-label, .deck-dots, .premium-controls, .premium-controls-shell, .mermaid-wrap, .diagram-zoom-toolbar, .diagram-zoom-btn';

  function deck() {
    return document.getElementById('deck');
  }

  function markerOn() {
    return document.documentElement.dataset.marker === 'on';
  }

  function laserOn() {
    return document.documentElement.dataset.laser === 'on';
  }

  function shouldSkip(node) {
    if (!node) return true;
    const el = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
    return el && el.closest(SKIP_SEL);
  }

  function applyMarkerFromSelection() {
    if (!markerOn()) return;
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return;

    const range = sel.getRangeAt(0);
    const d = deck();
    if (!d || !d.contains(range.commonAncestorContainer)) return;
    if (shouldSkip(range.commonAncestorContainer)) return;

    const text = sel.toString().trim();
    if (!text) return;

    const mark = document.createElement('mark');
    mark.className = 'premium-mark';

    try {
      range.surroundContents(mark);
    } catch {
      const fragment = range.extractContents();
      if (!fragment.textContent.trim()) return;
      mark.appendChild(fragment);
      range.insertNode(mark);
    }

    sel.removeAllRanges();
    mark.classList.add('premium-mark--ghost');
    requestAnimationFrame(() => mark.classList.remove('premium-mark--ghost'));
  }

  function clearSelection() {
    const sel = window.getSelection();
    if (sel && !sel.isCollapsed) sel.removeAllRanges();
  }

  function bindMarker() {
    const d = deck();
    if (!d || d.dataset.markerBound) return;
    d.dataset.markerBound = '1';
    d.addEventListener('mouseup', (e) => {
      if (e.button !== 0) return;
      if (laserOn()) return;
      setTimeout(applyMarkerFromSelection, 10);
    });
    d.addEventListener('selectstart', (e) => {
      if (laserOn()) e.preventDefault();
    });
  }

  function laserSetPos(el, x, y) {
    if (el) el.style.transform = 'translate(' + x + 'px,' + y + 'px)';
  }

  function shouldSkipLaserClick(node) {
    if (!node) return true;
    const el = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
    return el && el.closest(LASER_SKIP_CLICK);
  }

  function spawnLaserPulse(x, y) {
    const pulse = document.createElement('div');
    pulse.className = 'premium-laser-pulse';
    pulse.setAttribute('aria-hidden', 'true');
    pulse.style.transform = 'translate(' + x + 'px,' + y + 'px)';
    pulse.innerHTML = '<div class="premium-laser-pulse__ring"></div>';
    document.body.appendChild(pulse);
    const ring = pulse.querySelector('.premium-laser-pulse__ring');
    if (ring) {
      ring.addEventListener('animationend', () => pulse.remove(), { once: true });
    }
  }

  function onLaserClick(e) {
    if (!laserOn() || e.button !== 0) return;
    const d = deck();
    if (!d || !d.contains(e.target)) return;
    if (shouldSkipLaserClick(e.target)) return;

    clearSelection();
    spawnLaserPulse(e.clientX, e.clientY);
    e.preventDefault();
  }

  function bindLaserClick() {
    if (laserClickBound) return;
    laserClickBound = true;
    document.addEventListener('click', onLaserClick, true);
  }

  function unbindLaserClick() {
    if (!laserClickBound) return;
    laserClickBound = false;
    document.removeEventListener('click', onLaserClick, true);
    document.querySelectorAll('.premium-laser-pulse').forEach((el) => el.remove());
  }

  function mountLaser() {
    if (laserEl) return;
    laserEl = document.createElement('div');
    laserEl.className = 'premium-laser';
    laserEl.setAttribute('aria-hidden', 'true');

    laserTrails = [];
    for (let i = 0; i < LASER_TRAIL_COUNT; i++) {
      const trail = document.createElement('div');
      trail.className = 'premium-laser__trail';
      trail.style.setProperty('--trail-index', String(i));
      laserEl.appendChild(trail);
      laserTrails.push({ el: trail, x: 0, y: 0 });
    }

    laserRingWrap = document.createElement('div');
    laserRingWrap.className = 'premium-laser__ring-wrap';
    const ring = document.createElement('div');
    ring.className = 'premium-laser__ring';
    laserRingWrap.appendChild(ring);
    laserEl.appendChild(laserRingWrap);

    laserDot = document.createElement('div');
    laserDot.className = 'premium-laser__dot';
    laserEl.appendChild(laserDot);

    document.body.appendChild(laserEl);
  }

  function onLaserMove(e) {
    laserTargetX = e.clientX;
    laserTargetY = e.clientY;
    if (laserX === 0 && laserY === 0) {
      laserX = laserTargetX;
      laserY = laserTargetY;
      laserTrails.forEach((t) => {
        t.x = laserX;
        t.y = laserY;
      });
    }
  }

  function laserTick() {
    if (!laserBound) return;
    laserX += (laserTargetX - laserX) * 0.28;
    laserY += (laserTargetY - laserY) * 0.28;

    let fx = laserX;
    let fy = laserY;
    laserTrails.forEach((t, i) => {
      const ease = 0.13 - i * 0.025;
      t.x += (fx - t.x) * ease;
      t.y += (fy - t.y) * ease;
      laserSetPos(t.el, t.x, t.y);
      fx = t.x;
      fy = t.y;
    });

    laserSetPos(laserRingWrap, laserX, laserY);
    laserSetPos(laserDot, laserX, laserY);

    laserRaf = requestAnimationFrame(laserTick);
  }

  function bindLaser() {
    if (laserBound || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    mountLaser();
    laserBound = true;
    document.addEventListener('mousemove', onLaserMove, { passive: true });
    bindLaserClick();
    laserRaf = requestAnimationFrame(laserTick);
  }

  function unbindLaser() {
    laserBound = false;
    document.removeEventListener('mousemove', onLaserMove);
    unbindLaserClick();
    if (laserRaf) cancelAnimationFrame(laserRaf);
    laserRaf = 0;
    if (laserEl) laserEl.style.opacity = '';
    laserX = 0;
    laserY = 0;
    laserTrails.forEach((t) => {
      t.x = 0;
      t.y = 0;
      laserSetPos(t.el, 0, 0);
    });
  }

  function setMarker(on) {
    document.documentElement.dataset.marker = on ? 'on' : 'off';
    try {
      localStorage.setItem(STORAGE_MARKER, on ? 'on' : 'off');
    } catch (_) {}
    if (on) bindMarker();
    syncControlButtons();
  }

  function toggleMarker() {
    const next = !markerOn();
    if (next && laserOn()) setLaser(false);
    setMarker(next);
  }

  function setLaser(on) {
    document.documentElement.dataset.laser = on ? 'on' : 'off';
    try {
      localStorage.setItem(STORAGE_LASER, on ? 'on' : 'off');
    } catch (_) {}
    if (on) {
      if (markerOn()) setMarker(false);
      clearSelection();
      bindLaser();
    } else {
      unbindLaser();
    }
    syncControlButtons();
  }

  function clearMarks() {
    document.querySelectorAll('#deck .premium-mark').forEach((m) => {
      const parent = m.parentNode;
      while (m.firstChild) parent.insertBefore(m.firstChild, m);
      parent.removeChild(m);
      parent.normalize();
    });
  }

  function syncControlButtons() {
    const markerBtn = document.getElementById('premium-marker-toggle');
    const laserBtn = document.getElementById('premium-laser-toggle');
    if (markerBtn) {
      markerBtn.setAttribute('aria-pressed', markerOn() ? 'true' : 'false');
      markerBtn.disabled = laserOn();
    }
    if (laserBtn) {
      laserBtn.setAttribute('aria-pressed', laserOn() ? 'true' : 'false');
    }
  }

  function mountControlButtons(panel) {
    if (!panel || document.getElementById('premium-marker-toggle')) return;

    const markerGroup = document.createElement('div');
    markerGroup.className = 'premium-controls__group';
    const markerBtn = document.createElement('button');
    markerBtn.type = 'button';
    markerBtn.id = 'premium-marker-toggle';
    markerBtn.innerHTML = 'Marker<span class="premium-kbd">M</span>';
    markerBtn.title = 'Select text to highlight (M)';
    markerBtn.addEventListener('click', toggleMarker);
    markerGroup.appendChild(markerBtn);

    const clearBtn = document.createElement('button');
    clearBtn.type = 'button';
    clearBtn.id = 'premium-marker-clear';
    clearBtn.innerHTML = 'Clear<span class="premium-kbd">C</span>';
    clearBtn.title = 'Remove all highlights (C)';
    clearBtn.addEventListener('click', clearMarks);
    markerGroup.appendChild(clearBtn);

    const laserGroup = document.createElement('div');
    laserGroup.className = 'premium-controls__group';
    const laserBtn = document.createElement('button');
    laserBtn.type = 'button';
    laserBtn.id = 'premium-laser-toggle';
    laserBtn.innerHTML = 'Laser<span class="premium-kbd">L</span>';
    laserBtn.title = 'Pointer mode — click slide for attention pulse (L)';
    laserBtn.addEventListener('click', () => setLaser(!laserOn()));
    laserGroup.appendChild(laserBtn);

    panel.appendChild(markerGroup);
    panel.appendChild(laserGroup);
    syncControlButtons();
  }

  function restorePreferences() {
    const root = document.documentElement;
    try {
      const m = localStorage.getItem(STORAGE_MARKER);
      if (m === 'on' || m === 'off') root.dataset.marker = m;
      const l = localStorage.getItem(STORAGE_LASER);
      if (l === 'on' || l === 'off') root.dataset.laser = l;
    } catch (_) {}
    if (!root.dataset.marker) root.dataset.marker = 'off';
    if (!root.dataset.laser) root.dataset.laser = 'off';
    if (root.dataset.marker === 'on') bindMarker();
    if (root.dataset.laser === 'on') bindLaser();
  }

  function isTypingTarget(el) {
    if (!el) return false;
    const tag = el.tagName;
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return true;
    if (el.isContentEditable) return true;
    return false;
  }

  function bindShortcuts() {
    if (document.documentElement.dataset.shortcutsBound) return;
    document.documentElement.dataset.shortcutsBound = '1';

    document.addEventListener('keydown', (e) => {
      if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
      if (isTypingTarget(e.target)) return;

      const key = e.key.toLowerCase();
      if (key === 'm') {
        e.preventDefault();
        toggleMarker();
        return;
      }
      if (key === 'l') {
        e.preventDefault();
        setLaser(!laserOn());
        return;
      }
      if (key === 'c') {
        e.preventDefault();
        clearMarks();
      }
    });
  }

  function init() {
    restorePreferences();
    bindMarker();
    bindShortcuts();
    const panel = document.querySelector('.premium-controls');
    if (panel) mountControlButtons(panel);
    else {
      document.addEventListener(
        'DOMContentLoaded',
        () => {
          const p = document.querySelector('.premium-controls');
          if (p) mountControlButtons(p);
        },
        { once: true }
      );
    }
    document.addEventListener('premium-controls-ready', () => {
      const p = document.querySelector('.premium-controls');
      if (p) mountControlButtons(p);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumAnnotations = {
    setMarker,
    setLaser,
    toggleMarker,
    clearMarks,
    markerOn,
    laserOn,
    mountControlButtons,
  };
})();
