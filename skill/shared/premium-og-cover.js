/**
 * Premium Presentations — PNG export.
 * Lazy-loads SnapDOM from CDN (~10 KB gz) and exports slides as PNG.
 * Trigger: control panel "PNG" button.
 */
(function () {
  const SNAPDOM_URL = 'https://cdn.jsdelivr.net/npm/@zumer/snapdom@2/dist/snapdom.min.js';
  let snapLib = null;
  let loadingPromise = null;

  async function loadSnap() {
    if (snapLib) return snapLib;
    if (loadingPromise) return loadingPromise;
    loadingPromise = new Promise((resolve, reject) => {
      if (window.snapdom) { snapLib = window.snapdom; resolve(snapLib); return; }
      const s = document.createElement('script');
      s.src = SNAPDOM_URL;
      s.onload = () => {
        if (window.snapdom) { snapLib = window.snapdom; resolve(snapLib); }
        else { loadingPromise = null; reject(new Error('SnapDOM script loaded but window.snapdom is undefined')); }
      };
      s.onerror = () => { loadingPromise = null; reject(new Error('Failed to load SnapDOM')); };
      document.head.appendChild(s);
    });
    return loadingPromise;
  }

  async function exportSlidePng(slide, scale = 2, index) {
    const snap = await loadSnap();
    const i = index != null ? index : Array.from(slide.parentNode.children).indexOf(slide);
    const base = slide.id || (i >= 0 ? 'slide-' + (i + 1) : 'slide');
    // Non-visible slides have opacity:0 / transform translateY. SnapDOM snapshots
    // the live element, so off-screen slides would render empty. Clone into a
    // hidden offscreen container, force visible, snap, then drop the clone.
    const host = document.createElement('div');
    host.setAttribute('aria-hidden', 'true');
    Object.assign(host.style, {
      position: 'fixed',
      top: '0',
      left: '-10000px',
      width: '1280px',
      height: '720px',
      overflow: 'hidden',
      pointerEvents: 'none',
      zIndex: '-1',
    });
    const clone = slide.cloneNode(true);
    clone.classList.add('visible');
    // Strip reveal-state classes that may have been left by previous slides
    // so the clone renders in its final state regardless of which slide was last visible.
    clone.querySelectorAll('.reveal').forEach((el) => {
      el.style.opacity = '1';
      el.style.transform = 'none';
    });
    host.appendChild(clone);
    document.body.appendChild(host);
    try {
      const result = await snap(clone, { scale, format: 'png' });
      if (result && result.download) {
        result.download({ filename: base + '.png' });
      }
    } catch (err) {
      console.error('[Premium Export] slide export failed', err);
    } finally {
      host.remove();
    }
  }

  async function exportDeckPng() {
    const slides = document.querySelectorAll('#deck .slide');
    if (!slides.length) return;
    for (let i = 0; i < slides.length; i++) {
      await exportSlidePng(slides[i], 1.5, i);
      await new Promise((r) => setTimeout(r, 200));
    }
  }

  function mountButton(panel) {
    if (!panel || document.getElementById('premium-export-png')) return;
    const group = document.createElement('div');
    group.className = 'premium-controls__group';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'premium-export-png';
    btn.textContent = 'PNG';
    btn.title = 'Export all slides as PNG (uses SnapDOM CDN)';
    btn.addEventListener('click', async () => {
      const slides = document.querySelectorAll('#deck .slide');
      if (!slides.length) return;
      console.log('[Premium Export] exporting', slides.length, 'slides');
      btn.disabled = true;
      const originalLabel = btn.textContent;
      btn.textContent = '…';
      try {
        for (let i = 0; i < slides.length; i++) {
          btn.textContent = `… ${i + 1}/${slides.length}`;
          try {
            console.log('[Premium Export] snap slide', i + 1, 'id=' + (slides[i].id || 'none'));
            await exportSlidePng(slides[i], 1.5, i);
            console.log('[Premium Export] download triggered for slide', i + 1);
          } catch (err) {
            console.error('[Premium Export] slide ' + (i + 1) + ' failed', err);
          }
          // Longer delay: Chrome blocks rapid successive downloads
          // ("Download multiple files" prompt) and may silently drop them.
          await new Promise((r) => setTimeout(r, 800));
        }
        btn.textContent = '✓ ' + slides.length;
        setTimeout(() => { btn.textContent = originalLabel; }, 2000);
      } finally {
        btn.disabled = false;
      }
    });
    group.appendChild(btn);
    panel.appendChild(group);
  }

  function init() {
    const panel = document.querySelector('.premium-controls');
    if (panel) mountButton(panel);
    document.addEventListener('premium-controls-ready', () => {
      const p = document.querySelector('.premium-controls');
      if (p) mountButton(p);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumExport = { exportSlidePng, exportDeckPng };
})();
