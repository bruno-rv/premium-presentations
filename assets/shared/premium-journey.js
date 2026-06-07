/**
 * Premium Presentations — journey path: full track through nodes + flowing particles.
 * Markup: .journey-stage > svg with circle.journey-node (sorted by cx).
 * Particle pattern (3 staggered dots + shadow path) from AL-0 slide 5 journey map.
 * Motion uses rAF (SMIL animateMotion can freeze under CSS transform/reveal).
 */

const DEFAULT_JOURNEY_MS = 10000;

/** AL-0 style: lead + two trailing particles (begin offsets 0, 1s, 2s on 4s → thirds of cycle). */
const FLOW_PARTICLES = [
  { r: 3.5, opacity: 0.8, className: 'journey-flow-dot--lead', phase: 0 },
  { r: 2.5, opacity: 0.55, className: 'journey-flow-dot--mid', phase: 1 / 3 },
  { r: 2, opacity: 0.45, className: 'journey-flow-dot--trail', phase: 2 / 3 },
];

export function initPremiumJourney(root = document) {
  root.querySelectorAll('.journey-stage').forEach(initJourneyStage);
}

function parseDurationMs(value) {
  if (value == null || value === '') return DEFAULT_JOURNEY_MS;
  const s = String(value).trim();
  const m = s.match(/^([\d.]+)\s*(ms|s)?$/i);
  if (!m) return DEFAULT_JOURNEY_MS;
  const n = parseFloat(m[1]);
  return (m[2] || 's').toLowerCase() === 'ms' ? n : n * 1000;
}

function initJourneyStage(stage) {
  const svg = stage.querySelector('svg');
  if (!svg || svg.dataset.journeyReady === '1') return;

  const nodes = [...svg.querySelectorAll('circle.journey-node')].sort(
    (a, b) => parseFloat(a.getAttribute('cx')) - parseFloat(b.getAttribute('cx'))
  );
  if (nodes.length < 2) return;

  const pad = parseFloat(svg.dataset.journeyPad || '56') || 56;
  const durationMs = parseDurationMs(svg.dataset.journeyDuration || '10s');
  const points = buildWaypoints(nodes, svg, pad);
  const d = buildSmoothPath(points);
  if (!d) return;

  const gradientId = svg.dataset.journeyGradient || findGradientId(svg);
  const strokeFlow = gradientId ? `url(#${gradientId})` : 'var(--accent)';
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  svg
    .querySelectorAll(
      'path.flow-r, path.journey-path-track, path.journey-path-shadow, path.journey-path-flow'
    )
    .forEach((p) => p.remove());
  stopDotLoop(svg);

  let layer = svg.querySelector('.journey-path-layer');
  if (!layer) {
    layer = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    layer.setAttribute('class', 'journey-path-layer');
    const defs = svg.querySelector('defs');
    if (defs?.nextSibling) svg.insertBefore(layer, defs.nextSibling);
    else svg.prepend(layer);
  }

  const shadow = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  shadow.setAttribute('d', d);
  shadow.setAttribute('class', 'journey-path-shadow');
  shadow.setAttribute('stroke', strokeFlow);
  shadow.setAttribute('fill', 'none');
  shadow.setAttribute('stroke-linecap', 'round');
  shadow.setAttribute('stroke-linejoin', 'round');

  const track = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  track.setAttribute('d', d);
  track.setAttribute('class', 'journey-path-track');

  const flow = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  flow.setAttribute('d', d);
  flow.setAttribute('class', 'journey-path-flow');
  flow.setAttribute('stroke', strokeFlow);
  flow.setAttribute('fill', 'none');
  flow.setAttribute('stroke-width', '4');
  flow.setAttribute('stroke-linecap', 'round');
  flow.setAttribute('stroke-linejoin', 'round');
  if (!reducedMotion) {
    flow.classList.add('flow-r');
    flow.style.setProperty('--journey-flow-duration', durationMs + 'ms');
    const len = flow.getTotalLength();
    if (len > 0) {
      const dash = Math.max(12, len * 0.06);
      const gap = Math.max(10, len * 0.04);
      flow.style.strokeDasharray = `${dash} ${gap}`;
      flow.style.strokeDashoffset = '0';
      flow.style.setProperty('--journey-path-len', len + 'px');
      flow.style.setProperty('--journey-flow-duration', durationMs + 'ms');
    }
  }

  layer.append(shadow, track, flow);

  svg.querySelectorAll('.journey-flow-dot').forEach((el) => el.remove());

  if (!reducedMotion) {
    const particleCount = Math.max(
      1,
      Math.min(3, parseInt(svg.dataset.journeyParticles || '3', 10) || 3)
    );
    const presets = FLOW_PARTICLES.slice(0, particleCount);

    let flowLayer = svg.querySelector('.journey-flow-layer');
    if (!flowLayer) {
      flowLayer = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      flowLayer.setAttribute('class', 'journey-flow-layer');
      svg.appendChild(flowLayer);
    } else {
      flowLayer.replaceChildren();
    }

    const particles = presets.map((preset) => {
      const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      dot.setAttribute('class', `journey-flow-dot ${preset.className}`);
      dot.setAttribute('r', String(preset.r));
      dot.setAttribute('opacity', String(preset.opacity));
      dot.setAttribute('aria-hidden', 'true');
      flowLayer.appendChild(dot);
      return { dot, phase: preset.phase };
    });

    startParticlesLoop(svg, stage, flow, particles, durationMs);
  }

  svg.dataset.journeyReady = '1';
}

function stopDotLoop(svg) {
  const state = svg._journeyDotState;
  if (!state) return;
  state.running = false;
  if (state.rafId) cancelAnimationFrame(state.rafId);
  state.observer?.disconnect();
  svg._journeyDotState = null;
}

function startParticlesLoop(svg, stage, pathEl, particles, durationMs) {
  stopDotLoop(svg);

  const slide = stage.closest('.slide') || stage;
  const state = {
    active: false,
    startTs: null,
    rafId: 0,
    observer: null,
    particles,
    pathEl,
    durationMs,
    len: 0,
  };
  svg._journeyDotState = state;

  state.len = pathEl.getTotalLength();
  if (state.len < 2) return;

  function tick(ts) {
    state.rafId = requestAnimationFrame(tick);
    if (!state.active) return;
    if (state.startTs == null) state.startTs = ts;
    for (const p of state.particles) {
      const elapsed = (ts - state.startTs + p.phase * state.durationMs) % state.durationMs;
      const t = elapsed / state.durationMs;
      const pt = state.pathEl.getPointAtLength(t * state.len);
      p.dot.setAttribute('cx', String(round(pt.x)));
      p.dot.setAttribute('cy', String(round(pt.y)));
    }
  }

  state.observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          state.active = true;
          state.startTs = null;
        } else {
          state.active = false;
          state.startTs = null;
        }
      });
    },
    { root: slide.closest('.deck') || null, threshold: 0.4 }
  );
  state.observer.observe(slide);
  state.active = true;
  state.rafId = requestAnimationFrame(tick);
}

function findGradientId(svg) {
  const g = svg.querySelector('linearGradient[id]');
  return g ? g.id : '';
}

function buildWaypoints(nodes, svg, pad) {
  const vb = svg.viewBox.baseVal;
  const maxX = vb.width > 0 ? vb.width : 960;
  const minX = 0;

  const pts = nodes.map((c) => ({
    x: parseFloat(c.getAttribute('cx')),
    y: parseFloat(c.getAttribute('cy')),
  }));

  const first = pts[0];
  const last = pts[pts.length - 1];
  const start = { x: Math.max(minX + 20, first.x - pad), y: first.y };
  const end = { x: Math.min(maxX - 20, last.x + pad), y: last.y };

  return [start, ...pts, end];
}

function buildSmoothPath(points, tension = 0.38) {
  if (points.length < 2) return '';
  let d = `M ${round(points[0].x)} ${round(points[0].y)}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];
    const cp1x = p1.x + (p2.x - p0.x) * tension;
    const cp1y = p1.y + (p2.y - p0.y) * tension;
    const cp2x = p2.x - (p3.x - p1.x) * tension;
    const cp2y = p2.y - (p3.y - p1.y) * tension;
    d += ` C ${round(cp1x)} ${round(cp1y)}, ${round(cp2x)} ${round(cp2y)}, ${round(p2.x)} ${round(p2.y)}`;
  }
  return d;
}

function round(n) {
  return Math.round(n * 10) / 10;
}

if (typeof window !== 'undefined') {
  window.initPremiumJourney = initPremiumJourney;
  document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.journey-stage')) initPremiumJourney();
  });
}
