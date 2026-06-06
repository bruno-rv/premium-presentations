/**
 * Premium Presentations — two-window controller.
 *
 * State machine: 'deck' | 'popup' | 'none'.
 * - 'deck':  this window owns input (deck has focus, no popup alive OR popup open but unfocused).
 * - 'popup': this window owns input (popup has focus, popup is alive, deck is muted).
 * - 'none':  neither window owns input (both blurred). No shortcuts fire; safer than letting
 *            a stale 'deck' claim fire after the popup opened.
 *
 * Writes document.documentElement.dataset.controller.
 * Exposes window.PremiumController.isLocalOwner(role) for handlers.
 *
 * The deck also tracks `lastHeartbeatTs` and `lastHeartbeatFocused` from the popup's
 * `presenter.heartbeat` messages. The popup side ignores heartbeats and only computes
 * its own role from `document.hasFocus()`.
 *
 * Usage: <script src=".../premium-controller.js" defer></script>
 */
(function () {
  const FOCUS_POLL_MS = 500;
  const HEARTBEAT_TIMEOUT_MS = 2500;

  let lastHeartbeatTs = 0;        // wall-clock ms; 0 = never received
  let lastHeartbeatFocused = true; // popup's `popupFocused` flag from latest heartbeat
  let sessionId = '';              // set by init() with crypto.randomUUID()
  let pollTimer = 0;
  let inPopup = false;

  function isPopupAlive() {
    return lastHeartbeatTs > 0 && (Date.now() - lastHeartbeatTs) <= HEARTBEAT_TIMEOUT_MS;
  }

  function computeRole() {
    if (inPopup) {
      // Popup side: I am the controller iff I have focus AND the deck hasn't declared
      // me dead (deck never sends heartbeats to me, so just check focus).
      return document.hasFocus() ? 'popup' : 'none';
    }
    // Deck side: I am the controller iff I have focus AND (no popup alive OR popup open-but-unfocused).
    if (!document.hasFocus()) return 'none';
    if (!isPopupAlive()) return 'deck';
    // Popup is alive and recently said it has focus → popup owns.
    if (lastHeartbeatFocused) return 'none';
    // Popup is alive but said it's unfocused → deck takes over.
    return 'deck';
  }

  function applyRole() {
    const next = computeRole();
    if (document.documentElement.dataset.controller !== next) {
      document.documentElement.dataset.controller = next;
    }
  }

  function recordHeartbeat(popupFocused) {
    lastHeartbeatTs = Date.now();
    lastHeartbeatFocused = popupFocused !== false; // default true if undefined
    // Apply immediately so callers (and tests) don't have to wait for the poll.
    applyRole();
  }

  function onVisibility() {
    if (document.visibilityState === 'visible') applyRole();
  }

  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(applyRole, FOCUS_POLL_MS);
  }

  function isLocalOwner(role) {
    return document.documentElement.dataset.controller === role;
  }

  function getState() {
    return {
      role: document.documentElement.dataset.controller || 'none',
      sessionId,
      isPopupAlive: isPopupAlive(),
      lastHeartbeatTs,
      lastHeartbeatFocused,
    };
  }

  function init() {
    inPopup = new URLSearchParams(location.search).get('presenter') === '1';
    if (inPopup) {
      // Popup must use the deck's sessionId (passed via ?session=... in the URL)
      // so its BroadcastChannel lands on the same per-session channel the deck listens on.
      // Fall back to a fresh UUID if missing — popup will appear disconnected.
      const sidParam = new URLSearchParams(location.search).get('session');
      sessionId = sidParam || ((crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : ('sess-' + Math.random().toString(36).slice(2) + Date.now().toString(36)));
    } else {
      sessionId = (crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : ('sess-' + Math.random().toString(36).slice(2) + Date.now().toString(36));
    }
    document.documentElement.dataset.session = sessionId;
    document.documentElement.dataset.controller = 'none';

    // The popup is the local side iff it was opened with ?presenter=1.
    if (!inPopup) {
      // Listen for popup heartbeats on the global channel (the popup sends
      // via PremiumPresenter.postToPeer which posts on `premium-deck`, not
      // per-session). Per-session channel was the bug: the popup never
      // matched because postToPeer uses the global name.
      try {
        const ch = new BroadcastChannel('premium-deck');
        ch.addEventListener('message', (e) => {
          if (!e.data) return;
          if (e.data.type === 'presenter.heartbeat' && e.data.sessionId === sessionId) {
            recordHeartbeat(e.data.popupFocused);
            applyRole();
          }
        });
      } catch (_) {}
    }

    document.addEventListener('focus', applyRole, true);
    document.addEventListener('blur', applyRole, true);
    document.addEventListener('visibilitychange', onVisibility);
    startPolling();
    applyRole();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumController = {
    isLocalOwner,
    getState,
    recordHeartbeat,    // used by popup side to feed its own focus into the deck
  };
})();
