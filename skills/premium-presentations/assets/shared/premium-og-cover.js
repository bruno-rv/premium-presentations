/**
 * Premium Presentations — portable PNG export.
 * Trigger: control panel "PNG" button.
 */
(function () {
  function styleText() {
    const chunks = [...document.querySelectorAll('style')].map((s) => s.textContent || '');
    for (const sheet of document.styleSheets) {
      try {
        if (sheet.cssRules) {
          chunks.push([...sheet.cssRules].map((rule) => rule.cssText).join('\n'));
        }
      } catch (_) {
        // Cross-origin sheets cannot be inspected; portable bundles inline CSS.
      }
    }
    return chunks.join('\n');
  }

  function escapeXmlAttr(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function cdata(text) {
    return '<![CDATA[' + String(text || '').replace(/\]\]>/g, ']]]]><![CDATA[>') + ']]>';
  }

  function serializeSnapshotHtml(clone) {
    const computed = getComputedStyle(document.documentElement);
    const vars = [];
    for (let i = 0; i < computed.length; i++) {
      const name = computed[i];
      if (name.startsWith('--')) {
        vars.push(name + ':' + escapeXmlAttr(computed.getPropertyValue(name)) + ';');
      }
    }
    const attrs = document.documentElement.getAttributeNames()
      .filter((name) => /^data-|^lang$|^dir$/.test(name))
      .map((name) => name + '="' + escapeXmlAttr(document.documentElement.getAttribute(name)) + '"')
      .join(' ');
    const slide = clone.cloneNode(true);
    slide.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml');
    const slideHtml = new XMLSerializer().serializeToString(slide);
    return (
      '<div xmlns="http://www.w3.org/1999/xhtml" class="premium-export-root" ' + attrs + ' style="' + vars.join('') + '">' +
      '<style>' + cdata(styleText()) + '</style>' +
      '<div class="deck" id="deck">' +
      slideHtml +
      '</div></div>'
    );
  }

  function canvasToBlob(canvas) {
    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (blob) resolve(blob);
        else reject(new Error('Canvas did not produce a PNG blob'));
      }, 'image/png');
    });
  }

  async function nativeSnap(node, options = {}) {
    const scale = options.scale || 2;
    const width = 1280;
    const height = 720;
    const snapshotHtml = serializeSnapshotHtml(node);
    const svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="' + width + '" height="' + height + '" viewBox="0 0 ' + width + ' ' + height + '">' +
      '<foreignObject width="100%" height="100%">' + snapshotHtml + '</foreignObject>' +
      '</svg>';
    const img = new Image();
    const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    await new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = () => reject(new Error('Native PNG export image decode failed'));
      img.src = url;
    });

    const canvas = document.createElement('canvas');
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas 2D context unavailable');
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const blob = await canvasToBlob(canvas);

    return {
      download({ filename = 'slide.png' } = {}) {
        const href = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = href;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(href), 1000);
      },
    };
  }

  async function exportSlidePng(slide, scale = 2, index) {
    const i = index != null ? index : Array.from(slide.parentNode.children).indexOf(slide);
    const base = slide.id || (i >= 0 ? 'slide-' + (i + 1) : 'slide');
    // Non-visible slides have opacity:0 / transform translateY. The exporter snapshots
    // a cloned element, so off-screen slides render correctly. Clone into a
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
      const result = await nativeSnap(clone, { scale, format: 'png' });
      if (result && result.download) {
        result.download({ filename: base + '.png' });
      }
    } catch (err) {
      console.error('[Premium Export] slide export failed', err);
      throw err;
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
    btn.title = 'Export all slides as PNG';
    btn.addEventListener('click', async () => {
      const slides = document.querySelectorAll('#deck .slide');
      if (!slides.length) return;
      console.log('[Premium Export] exporting', slides.length, 'slides');
      btn.disabled = true;
      const originalLabel = btn.textContent;
      let exported = 0;
      let failed = 0;
      btn.textContent = '…';
      try {
        for (let i = 0; i < slides.length; i++) {
          btn.textContent = `… ${i + 1}/${slides.length}`;
          try {
            console.log('[Premium Export] snap slide', i + 1, 'id=' + (slides[i].id || 'none'));
            await exportSlidePng(slides[i], 1.5, i);
            exported++;
            console.log('[Premium Export] download triggered for slide', i + 1);
          } catch (err) {
            failed++;
            console.error('[Premium Export] slide ' + (i + 1) + ' failed', err);
          }
          // Longer delay: Chrome blocks rapid successive downloads
          // ("Download multiple files" prompt) and may silently drop them.
          await new Promise((r) => setTimeout(r, 800));
        }
        btn.textContent = failed ? ('! ' + exported + '/' + slides.length) : ('✓ ' + slides.length);
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
