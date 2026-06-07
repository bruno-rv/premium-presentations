/**
 * Premium Presentations — clicker / wireless remote support.
 * Tries WebHID first (Chrome/Edge); falls back to keyboard page-nav.
 *
 * WebHID mappings (Consumer Control usagePage 0x0C):
 *   0xB5 Scan Next Track  -> next slide
 *   0xB6 Scan Previous    -> prev slide
 *   0xCD Play/Pause       -> toggle laser pointer
 */
(function () {
  let device = null;
  let statusEl = null;
  let statusTimer = 0;
  const bindings = { next: 0xb5, prev: 0xb6, laser: 0xcd };

  function showStatus(msg, ms) {
    if (!statusEl) {
      statusEl = document.createElement('div');
      statusEl.className = 'premium-clicker-status';
      document.body.appendChild(statusEl);
    }
    statusEl.textContent = msg;
    statusEl.classList.add('is-visible');
    clearTimeout(statusTimer);
    statusTimer = setTimeout(() => statusEl.classList.remove('is-visible'), ms || 2400);
  }

  function isPresenterPopup() {
    return new URLSearchParams(location.search).get('presenter') === '1';
  }

  function nav(direction) {
    if (isPresenterPopup()) return;
    if (!window.PremiumDeckControls) return;
    if (direction === 'next') window.PremiumDeckControls.next();
    else if (direction === 'prev') window.PremiumDeckControls.prev();
  }

  function toggleLaser() {
    if (isPresenterPopup()) return;
    if (window.PremiumAnnotations && typeof window.PremiumAnnotations.setLaser === 'function') {
      const on = document.documentElement.dataset.laser === 'on';
      window.PremiumAnnotations.setLaser(!on);
    }
  }

  async function bindHID() {
    if (!('hid' in navigator)) {
      showStatus('WebHID not supported — keyboard fallback active');
      return;
    }
    try {
      const devices = await navigator.hid.requestDevice({ filters: [{ usagePage: 0x0c }] });
      if (!devices || !devices.length) {
        showStatus('No device selected — keyboard fallback active');
        return;
      }
      device = devices[0];
      await device.open();
      showStatus('Clicker bound: ' + (device.productName || 'HID device'));
      device.addEventListener('inputreport', (e) => {
        const data = new Uint8Array(e.data.buffer);
        if (data[1] === bindings.next) nav('next');
        else if (data[1] === bindings.prev) nav('prev');
        else if (data[1] === bindings.laser) toggleLaser();
      });
    } catch (_err) {
      showStatus('Clicker bind failed — keyboard fallback active');
    }
  }

  function init() {
    document.addEventListener('keydown', (e) => {
      if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      if (isPresenterPopup()) return;
      if (e.shiftKey && (e.key === 'C' || e.key === 'c')) {
        e.preventDefault();
        bindHID();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumClicker = { bindHID, nav, toggleLaser };
})();
