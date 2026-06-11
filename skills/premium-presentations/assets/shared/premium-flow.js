/**
 * Premium Presentations — live flow: phase spotlight over flow nodes + shimmer arrows.
 * Markup: .live-flow[data-flow-phases] containing .flow-node / .flow-arrow elements with ids.
 * data-flow-phases: JSON array of {label, color?, nodes: [ids], arrows: [ids]}.
 * data-flow-interval: ms per phase (default 1800).
 * Pauses when off-screen (IntersectionObserver); reduced motion lights everything statically.
 */

const DEFAULT_FLOW_INTERVAL_MS = 1800;

export function initPremiumFlow(root = document) {
  root.querySelectorAll('.live-flow[data-flow-phases]').forEach(initLiveFlow);
}

function parsePhases(container) {
  try {
    const phases = JSON.parse(container.dataset.flowPhases);
    return Array.isArray(phases) && phases.length > 0 ? phases : null;
  } catch (err) {
    console.error('[PremiumFlow] invalid data-flow-phases JSON', err, container);
    return null;
  }
}

/** Static fallback: light every node/arrow, no cycling. */
function lightAll(container) {
  container
    .querySelectorAll('.flow-node, .flow-arrow')
    .forEach((el) => el.classList.add('is-active'));
}

function byId(container, id) {
  const escaped = window.CSS && CSS.escape ? CSS.escape(id) : id;
  return container.querySelector('#' + escaped);
}

function initLiveFlow(container) {
  if (container.dataset.flowInit === '1') return;
  container.dataset.flowInit = '1';

  const phases = parsePhases(container);
  if (!phases) {
    lightAll(container);
    return;
  }

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    lightAll(container);
    return;
  }

  const banner = container.querySelector('[data-flow-banner]');
  const intervalMs =
    parseInt(container.dataset.flowInterval, 10) || DEFAULT_FLOW_INTERVAL_MS;
  const state = { phase: -1, timer: 0 };

  function applyNextPhase() {
    state.phase = (state.phase + 1) % phases.length;
    const phase = phases[state.phase] || {};
    container
      .querySelectorAll('.is-active')
      .forEach((el) => el.classList.remove('is-active'));
    [...(phase.nodes || []), ...(phase.arrows || [])].forEach((id) => {
      const el = byId(container, String(id));
      if (el) el.classList.add('is-active');
    });
    if (banner) {
      banner.textContent = phase.label || '';
      banner.style.color = phase.color || 'var(--accent)';
    }
  }

  function start() {
    if (state.timer) return;
    applyNextPhase();
    state.timer = window.setInterval(applyNextPhase, intervalMs);
  }

  function stop() {
    if (!state.timer) return;
    window.clearInterval(state.timer);
    state.timer = 0;
  }

  const observer = new IntersectionObserver(
    (entries) => entries.forEach((e) => (e.isIntersecting ? start() : stop())),
    { root: container.closest('.deck') || null, threshold: 0.3 }
  );
  observer.observe(container);
}

if (typeof window !== 'undefined') {
  window.initPremiumFlow = initPremiumFlow;
  document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.live-flow[data-flow-phases]')) initPremiumFlow();
  });
}
