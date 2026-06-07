/**
 * Premium Presentations — Excalidraw-style Mermaid (hand-drawn look + theme sync).
 *
 * Usage in deck:
 * <link rel="stylesheet" href="../../shared/premium-diagrams.css">
 * <script type="module">
 *   import { initPremiumMermaid } from '../../shared/premium-mermaid.js';
 *   document.addEventListener('DOMContentLoaded', async () => {
 *     await initPremiumMermaid();
 *     new SlideEngine();
 *   });
 * <\/script>
 */

const MERMAID_CDN_ESM =
  'https://cdn.jsdelivr.net/npm/mermaid@11.4.0/dist/mermaid.esm.min.mjs';
const MERMAID_CDN_UMD =
  'https://cdn.jsdelivr.net/npm/mermaid@11.4.0/dist/mermaid.min.js';

function deckTheme() {
  const t = document.documentElement.dataset.theme;
  if (t === 'editorial') return 'editorial';
  if (t === 'red') return 'red';
  return 'warm';
}

/** @returns {Promise<import('mermaid').default>} */
async function loadMermaid() {
  if (globalThis.__premiumMermaid?.run) return globalThis.__premiumMermaid;
  if (globalThis.mermaid?.run) {
    globalThis.__premiumMermaid = globalThis.mermaid;
    return globalThis.__premiumMermaid;
  }

  try {
    const mod = await import(/* @vite-ignore */ MERMAID_CDN_ESM);
    globalThis.__premiumMermaid = mod.default ?? mod;
    return globalThis.__premiumMermaid;
  } catch (esmErr) {
    console.warn(
      '[Premium Presentations] Mermaid ESM import failed; loading UMD build.',
      esmErr
    );
    await new Promise((resolve, reject) => {
      const existing = document.querySelector('script[data-premium-mermaid-umd]');
      if (existing) {
        if (globalThis.mermaid) return resolve();
        existing.addEventListener('load', () => resolve(), { once: true });
        existing.addEventListener('error', reject, { once: true });
        return;
      }
      const script = document.createElement('script');
      script.src = MERMAID_CDN_UMD;
      script.dataset.premiumMermaidUmd = '1';
      script.onload = () => resolve();
      script.onerror = reject;
      document.head.appendChild(script);
    });
    if (!globalThis.mermaid?.run) {
      throw new Error('Mermaid UMD failed to load');
    }
    globalThis.__premiumMermaid = globalThis.mermaid;
    return globalThis.__premiumMermaid;
  }
}

function getMermaidNodes() {
  return document.querySelectorAll('.diagram-stage .mermaid-wrap pre.mermaid');
}

function stashMermaidSource(node) {
  const el = /** @type {HTMLElement} */ (node);
  if (!el.dataset.mermaidSrc) {
    el.dataset.mermaidSrc = (el.textContent || '').trim();
  }
  const wrap = el.closest('.mermaid-wrap');
  if (wrap && el.dataset.mermaidSrc) {
    wrap.dataset.mermaidSrc = el.dataset.mermaidSrc;
  }
}

/** Reset wrap to a single &lt;pre class="mermaid"&gt; (needed after zoom DOM / SVG render). */
function rebuildMermaidPresFromWraps() {
  document.querySelectorAll('.diagram-stage .mermaid-wrap').forEach((wrap) => {
    const pre = wrap.querySelector('pre.mermaid');
    if (pre) stashMermaidSource(pre);
    const source = wrap.dataset.mermaidSrc || pre?.dataset.mermaidSrc || '';
    if (!source) return;
    wrap.dataset.mermaidSrc = source;
    wrap.innerHTML = '';
    const next = document.createElement('pre');
    next.className = 'mermaid';
    next.dataset.mermaidSrc = source;
    next.textContent = source;
    wrap.appendChild(next);
    clearDiagramZoomBinding(wrap);
    delete wrap.dataset.diagramZoom;
    delete wrap.dataset.diagramZoomActive;
    delete wrap.dataset.diagramClipped;
    delete wrap.dataset.fitScale;
  });
}

function clearDiagramZoomBinding(wrap) {
  if (wrap._diagramZoomAbort) {
    wrap._diagramZoomAbort.abort();
    wrap._diagramZoomAbort = null;
  }
  delete wrap.dataset.diagramZoomBound;
  delete wrap._diagramZoomState;
  delete wrap._diagramZoomReset;
  delete wrap._diagramZoomStep;
}

function isDiagramSlideActive(wrap) {
  const slide = wrap.closest('.slide');
  return slide?.classList.contains('visible') === true;
}

function resetMermaidNode(node) {
  const el = /** @type {HTMLElement} */ (node);
  const src = el.dataset.mermaidSrc || (el.textContent || '').trim();
  el.removeAttribute('data-processed');
  el.textContent = src;
  el.classList.add('mermaid');
}

function showMermaidError(node, err) {
  const wrap = node.closest('.mermaid-wrap');
  if (!wrap) return;
  let box = wrap.querySelector('.mermaid-error');
  if (!box) {
    box = document.createElement('pre');
    box.className = 'mermaid-error';
    wrap.appendChild(box);
  }
  box.textContent =
    'Diagram could not be rendered.\n' + (err?.message || String(err));
}

/** @param {'editorial' | 'warm' | 'red'} [theme] */
export function getMermaidConfig(theme = deckTheme()) {
  const accent =
    theme === 'editorial' ? '#364fc7' : theme === 'red' ? '#FF0230' : '#c2410c';
  const accentSoft =
    theme === 'editorial'
      ? '#a5d8ff'
      : theme === 'red'
        ? '#ffd0d3'
        : '#ffc9c2';

  return {
    startOnLoad: false,
    look: 'handDrawn',
    theme: 'base',
    themeVariables: {
      darkMode: false,
      background: 'transparent',
      fontFamily: '"Patrick Hand", "Segoe Print", cursive',
      fontSize: '16px',
      primaryColor: accentSoft,
      primaryTextColor: '#1e1e1e',
      primaryBorderColor: accent,
      secondaryColor: '#b2f2bb',
      secondaryTextColor: '#1e1e1e',
      secondaryBorderColor: '#1e1e1e',
      tertiaryColor: '#ffec99',
      tertiaryTextColor: '#1e1e1e',
      tertiaryBorderColor: '#1e1e1e',
      lineColor: accent,
      textColor: '#1e1e1e',
      mainBkg: accentSoft,
      nodeBorder: accent,
      clusterBkg: '#f8f9fa',
      clusterBorder: '#868e96',
      titleColor: '#1e1e1e',
      edgeLabelBackground: '#fffef8',
    },
    flowchart: {
      curve: 'basis',
      padding: 12,
      htmlLabels: true,
      useMaxWidth: false,
      diagramPadding: 8,
    },
    securityLevel: 'strict',
  };
}

/** Hand-drawn Mermaid strokes often extend past viewBox — measure generously. */
function measureSvg(svg) {
  let w = 0;
  let h = 0;

  const vb = svg.viewBox?.baseVal;
  if (vb && vb.width > 0 && vb.height > 0) {
    w = vb.width;
    h = vb.height;
  }

  try {
    const b = svg.getBBox();
    if (b.width > 0 && b.height > 0) {
      w = Math.max(w, b.width);
      h = Math.max(h, b.height);
    }
  } catch (_) {}

  const graph = svg.querySelector('g');
  if (graph) {
    try {
      const gb = graph.getBBox();
      if (gb.width > 0 && gb.height > 0) {
        w = Math.max(w, gb.width);
        h = Math.max(h, gb.height);
      }
    } catch (_) {}
  }

  const rendered = svg.getBoundingClientRect();
  if (rendered.width > 0 && rendered.height > 0) {
    w = Math.max(w, rendered.width);
    h = Math.max(h, rendered.height);
  }

  const attrW = parseFloat(svg.getAttribute('width') || '0');
  const attrH = parseFloat(svg.getAttribute('height') || '0');
  if (attrW > 0) w = Math.max(w, attrW);
  if (attrH > 0) h = Math.max(h, attrH);

  // Safety margin for sketch filters / labels outside bbox
  w *= 1.1;
  h *= 1.08;

  return { w: w || 1, h: h || 1 };
}

function diagramAvailSize(wrap, stage) {
  const pad = 32;
  wrap.style.width = '100%';
  wrap.style.maxWidth = '100%';
  const stageW = stage.clientWidth || wrap.clientWidth;
  const wrapW = wrap.clientWidth || stageW;
  const stageH = stage.clientHeight;
  return {
    w: Math.max(80, Math.min(stageW, wrapW) - pad),
    h: Math.max(80, stageH - pad),
  };
}

function applySvgSize(svg, scaledW, scaledH) {
  svg.style.display = 'block';
  svg.style.margin = '0 auto';
  svg.style.transform = '';
  svg.style.transformOrigin = '';
  svg.setAttribute('width', String(scaledW));
  svg.setAttribute('height', String(scaledH));
  svg.style.width = scaledW + 'px';
  svg.style.height = scaledH + 'px';
  svg.style.maxWidth = '100%';
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
}

function isDiagramClipped(wrap, svg) {
  const pad = 3;
  const sRect = svg.getBoundingClientRect();
  const wRect = wrap.getBoundingClientRect();
  if (sRect.width < 1 || wRect.width < 1) return false;
  return (
    sRect.bottom > wRect.bottom + pad ||
    sRect.top < wRect.top - pad ||
    sRect.right > wRect.right + pad ||
    sRect.left < wRect.left - pad
  );
}

function reportDiagramFit(wrap, svg) {
  const clipped = isDiagramClipped(wrap, svg);
  wrap.dataset.diagramClipped = clipped ? 'true' : 'false';

  if (clipped) {
    console.warn(
      '[Premium Presentations] Diagram clipped after fit — refitting.',
      { scale: wrap.dataset.fitScale, wrap }
    );
    document.documentElement.dispatchEvent(
      new CustomEvent('premium-diagram-clip', { detail: { wrap } })
    );
  }
  return clipped;
}

function fitOneMermaidWrap(wrap) {
  const svg = wrap.querySelector('svg');
  const stage = wrap.closest('.diagram-stage');
  if (!svg || !stage) return;

  svg.style.transform = '';
  svg.style.width = '';
  svg.style.height = '';
  svg.style.maxWidth = '';
  wrap.style.height = '';
  wrap.style.minHeight = '';
  wrap.style.width = '100%';

  const { w: availW, h: availH } = diagramAvailSize(wrap, stage);
  if (availH < 60 || availW < 60) return;

  const { w: svgW, h: svgH } = measureSvg(svg);
  if (!svgW || !svgH) return;

  const scale = Math.min(1, availW / svgW, availH / svgH) * 0.97;
  const scaledW = Math.max(1, Math.round(svgW * scale));
  const scaledH = Math.max(1, Math.round(svgH * scale));

  applySvgSize(svg, scaledW, scaledH);

  const pad = 32;
  wrap.style.height = scaledH + pad + 'px';
  wrap.style.maxHeight = '100%';
  wrap.dataset.fitScale = String(scale);
}

function refineOneMermaidWrap(wrap) {
  const svg = wrap.querySelector('svg');
  const stage = wrap.closest('.diagram-stage');
  if (!svg || !stage) return;

  if (!isDiagramClipped(wrap, svg)) {
    wrap.dataset.diagramClipped = 'false';
    return;
  }

  const { w: availW, h: availH } = diagramAvailSize(wrap, stage);
  const sRect = svg.getBoundingClientRect();
  if (sRect.width < 1 || sRect.height < 1) return;

  const factor = Math.min(availW / sRect.width, availH / sRect.height, 1) * 0.96;
  if (factor >= 0.995) return;

  const curW = parseFloat(svg.getAttribute('width') || '0') || sRect.width;
  const curH = parseFloat(svg.getAttribute('height') || '0') || sRect.height;
  const scaledW = Math.max(1, Math.round(curW * factor));
  const scaledH = Math.max(1, Math.round(curH * factor));

  applySvgSize(svg, scaledW, scaledH);
  wrap.style.height = scaledH + 32 + 'px';
  wrap.dataset.fitScale = String(
    parseFloat(wrap.dataset.fitScale || '1') * factor
  );

  reportDiagramFit(wrap, svg);
}

export function fitMermaidDiagrams() {
  const wraps = document.querySelectorAll('.diagram-stage .mermaid-wrap');
  wraps.forEach(fitOneMermaidWrap);
  requestAnimationFrame(() => {
    wraps.forEach(refineOneMermaidWrap);
    requestAnimationFrame(() => {
      wraps.forEach((wrap) => {
        const svg = wrap.querySelector('svg');
        if (svg) reportDiagramFit(wrap, svg);
      });
    });
  });
}

const DIAGRAM_ZOOM_MIN = 0.4;
const DIAGRAM_ZOOM_MAX = 4;
const DIAGRAM_ZOOM_STEP = 1.14;

function clampZoom(z) {
  return Math.min(DIAGRAM_ZOOM_MAX, Math.max(DIAGRAM_ZOOM_MIN, z));
}

/** Wrap diagram content for pan/zoom (idempotent). Call after Mermaid has rendered SVG. */
export function prepareDiagramZoomDOM() {
  document.querySelectorAll('.diagram-stage .mermaid-wrap').forEach((wrap) => {
    if (wrap.querySelector('.diagram-viewport')) return;
    if (!wrap.querySelector('svg')) return;

    const toolbar = document.createElement('div');
    toolbar.className = 'diagram-zoom-toolbar';
    toolbar.setAttribute('role', 'toolbar');
    toolbar.setAttribute('aria-label', 'Diagram zoom');
    toolbar.innerHTML =
      '<button type="button" class="diagram-zoom-btn" data-zoom="out" aria-label="Zoom out">−</button>' +
      '<button type="button" class="diagram-zoom-btn" data-zoom="reset" aria-label="Reset zoom">100%</button>' +
      '<button type="button" class="diagram-zoom-btn" data-zoom="in" aria-label="Zoom in">+</button>';

    const viewport = document.createElement('div');
    viewport.className = 'diagram-viewport';
    const pane = document.createElement('div');
    pane.className = 'diagram-zoom-pane';

    while (wrap.firstChild) {
      pane.appendChild(wrap.firstChild);
    }
    viewport.appendChild(pane);
    wrap.appendChild(viewport);
    wrap.appendChild(toolbar);
    wrap.dataset.diagramZoom = '1';
  });
}

function syncZoomChrome(wrap, state) {
  wrap.dataset.diagramZoom = String(Math.round(state.zoom * 100) / 100);
  wrap.dataset.diagramZoomActive =
    state.zoom !== 1 || state.panX !== 0 || state.panY !== 0 ? '1' : '0';
  const resetBtn = wrap.querySelector('[data-zoom="reset"]');
  if (resetBtn) {
    resetBtn.textContent = Math.round(state.zoom * 100) + '%';
  }
}

function applyDiagramTransform(wrap, state) {
  const pane = wrap.querySelector('.diagram-zoom-pane');
  if (!pane) return;
  pane.style.transform =
    'translate(' + state.panX + 'px,' + state.panY + 'px) scale(' + state.zoom + ')';
  syncZoomChrome(wrap, state);
}

function zoomDiagramAt(wrap, state, nextZoom, clientX, clientY) {
  const viewport = wrap.querySelector('.diagram-viewport');
  const old = state.zoom;
  const zoom = clampZoom(nextZoom);
  if (viewport && clientX != null && old > 0 && zoom !== old) {
    const rect = viewport.getBoundingClientRect();
    const cx = clientX - rect.left - rect.width / 2;
    const cy = clientY - rect.top - rect.height / 2;
    const ratio = zoom / old;
    state.panX = cx - (cx - state.panX) * ratio;
    state.panY = cy - (cy - state.panY) * ratio;
  }
  state.zoom = zoom;
  applyDiagramTransform(wrap, state);
}

function bindOneDiagramZoom(wrap) {
  const viewport = wrap.querySelector('.diagram-viewport');
  const toolbar = wrap.querySelector('.diagram-zoom-toolbar');
  if (!viewport) {
    clearDiagramZoomBinding(wrap);
    return;
  }

  clearDiagramZoomBinding(wrap);
  wrap.dataset.diagramZoomBound = '1';

  const ac = new AbortController();
  wrap._diagramZoomAbort = ac;
  const opts = { signal: ac.signal };

  const state = { zoom: 1, panX: 0, panY: 0 };

  const reset = () => {
    state.zoom = 1;
    state.panX = 0;
    state.panY = 0;
    applyDiagramTransform(wrap, state);
  };

  const step = (dir, clientX, clientY) => {
    const factor = dir > 0 ? DIAGRAM_ZOOM_STEP : 1 / DIAGRAM_ZOOM_STEP;
    zoomDiagramAt(wrap, state, state.zoom * factor, clientX, clientY);
  };

  toolbar?.addEventListener(
    'click',
    (e) => {
      const btn = e.target.closest('[data-zoom]');
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();
      const action = btn.getAttribute('data-zoom');
      if (action === 'in') step(1);
      else if (action === 'out') step(-1);
      else reset();
    },
    opts
  );

  viewport.addEventListener(
    'wheel',
    (e) => {
      if (!isDiagramSlideActive(wrap)) return;
      e.preventDefault();
      e.stopPropagation();
      wrap.dataset.diagramZooming = '1';
      step(e.deltaY < 0 ? 1 : -1, e.clientX, e.clientY);
      clearTimeout(wrap._diagramZoomWheelEnd);
      wrap._diagramZoomWheelEnd = setTimeout(() => {
        delete wrap.dataset.diagramZooming;
      }, 120);
    },
    { passive: false, ...opts }
  );

  viewport.addEventListener(
    'dblclick',
    (e) => {
      if (e.target.closest('.diagram-zoom-toolbar')) return;
      e.preventDefault();
      reset();
    },
    opts
  );

  let panning = false;
  let panPointerId = null;
  let panStartX = 0;
  let panStartY = 0;
  let panOriginX = 0;
  let panOriginY = 0;

  const endPan = () => {
    if (!panning) return;
    const id = panPointerId;
    panning = false;
    panPointerId = null;
    viewport.classList.remove('is-panning');
    if (id != null) {
      try {
        viewport.releasePointerCapture(id);
      } catch (_) {}
    }
  };

  viewport.addEventListener(
    'pointerdown',
    (e) => {
      if (e.button !== 0 || e.target.closest('.diagram-zoom-toolbar')) return;
      if (!isDiagramSlideActive(wrap)) return;
      panning = true;
      panPointerId = e.pointerId;
      viewport.classList.add('is-panning');
      panStartX = e.clientX;
      panStartY = e.clientY;
      panOriginX = state.panX;
      panOriginY = state.panY;
      viewport.setPointerCapture(e.pointerId);
      e.preventDefault();
      e.stopPropagation();
    },
    opts
  );

  viewport.addEventListener(
    'pointermove',
    (e) => {
      if (!panning || e.pointerId !== panPointerId) return;
      state.panX = panOriginX + (e.clientX - panStartX);
      state.panY = panOriginY + (e.clientY - panStartY);
      applyDiagramTransform(wrap, state);
      e.preventDefault();
    },
    opts
  );

  viewport.addEventListener('pointerup', endPan, opts);
  viewport.addEventListener('pointercancel', endPan, opts);

  let pinchStart = 0;
  let pinchZoom = 1;

  viewport.addEventListener(
    'touchstart',
    (e) => {
      if (e.touches.length === 2) {
        const [a, b] = e.touches;
        pinchStart = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
        pinchZoom = state.zoom;
        wrap.dataset.diagramZooming = '1';
        e.stopPropagation();
      } else if (e.touches.length === 1) {
        e.stopPropagation();
      }
    },
    { passive: true, ...opts }
  );

  viewport.addEventListener(
    'touchmove',
    (e) => {
      if (e.touches.length !== 2 || pinchStart < 1) return;
      e.preventDefault();
      e.stopPropagation();
      const [a, b] = e.touches;
      const dist = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
      const midX = (a.clientX + b.clientX) / 2;
      const midY = (a.clientY + b.clientY) / 2;
      zoomDiagramAt(wrap, state, pinchZoom * (dist / pinchStart), midX, midY);
    },
    { passive: false, ...opts }
  );

  viewport.addEventListener(
    'touchend',
    (e) => {
      pinchStart = 0;
      delete wrap.dataset.diagramZooming;
      e.stopPropagation();
    },
    opts
  );

  wrap._diagramZoomState = state;
  wrap._diagramZoomReset = reset;
  wrap._diagramZoomStep = step;
  applyDiagramTransform(wrap, state);
}

let diagramZoomBound = false;

export function bindDiagramZoom() {
  prepareDiagramZoomDOM();
  document.querySelectorAll('.diagram-stage .mermaid-wrap').forEach(bindOneDiagramZoom);

  if (diagramZoomBound) return;
  diagramZoomBound = true;

  document.addEventListener('keydown', (e) => {
    if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
    const tag = e.target?.tagName;
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;

    const slide = document.querySelector('.slide--diagram.visible');
    const wrap = slide?.querySelector('.mermaid-wrap');
    if (!wrap?._diagramZoomStep) return;

    const key = e.key;
    if (key === '=' || key === '+') {
      e.preventDefault();
      wrap._diagramZoomStep(1);
    } else if (key === '-') {
      e.preventDefault();
      wrap._diagramZoomStep(-1);
    } else if (key === '0') {
      e.preventDefault();
      wrap._diagramZoomReset?.();
    }
  });
}

let mermaidFitBound = false;

export function bindMermaidFit() {
  if (mermaidFitBound) return;
  mermaidFitBound = true;

  const run = () => requestAnimationFrame(fitMermaidDiagrams);

  window.addEventListener('resize', run);
  document.querySelectorAll('.slide--diagram').forEach((slide) => {
    new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        run();
        requestAnimationFrame(() => {
          prepareDiagramZoomDOM();
          bindDiagramZoom();
        });
      },
      { threshold: 0.2 }
    ).observe(slide);
  });

  if (document.fonts?.ready) {
    document.fonts.ready.then(run).catch(() => {});
  }
}

/**
 * @param {import('mermaid').default} mermaid
 */
export async function renderPremiumMermaid(mermaid) {
  rebuildMermaidPresFromWraps();
  const nodes = getMermaidNodes();
  if (!nodes.length) return;

  nodes.forEach((node) => {
    stashMermaidSource(node);
    node.closest('.mermaid-wrap')?.querySelector('.mermaid-error')?.remove();
    if (node.getAttribute('data-processed')) resetMermaidNode(node);
  });

  const baseConfig = getMermaidConfig();
  const attempts = [baseConfig, { ...baseConfig, look: undefined }];
  let lastErr = null;

  for (const config of attempts) {
    nodes.forEach(resetMermaidNode);
    mermaid.initialize(config);
    try {
      await mermaid.run({ nodes: [...nodes] });
      lastErr = null;
      break;
    } catch (err) {
      lastErr = err;
      console.warn('[Premium Presentations] Mermaid render attempt failed.', err);
    }
  }

  if (lastErr) {
    nodes.forEach((node) => showMermaidError(node, lastErr));
    return;
  }

  prepareDiagramZoomDOM();
  fitMermaidDiagrams();
  bindDiagramZoom();
  requestAnimationFrame(() => {
    fitMermaidDiagrams();
    bindDiagramZoom();
  });
}

/**
 * @param {{ beforeRender?: () => void | Promise<void>; afterRender?: () => void | Promise<void> }} [hooks]
 */
export async function initPremiumMermaid(hooks = {}) {
  const mermaid = await loadMermaid();

  const run = async () => {
    await hooks.beforeRender?.();
    await renderPremiumMermaid(mermaid);
    await hooks.afterRender?.();
  };

  const start = async () => {
    bindMermaidFit();
    await run();
    document.documentElement.addEventListener('premium-theme-change', run);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    await start();
  }

  return { mermaid, render: run };
}
