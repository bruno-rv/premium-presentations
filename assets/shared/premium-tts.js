/**
 * Premium Presentations — text-to-speech read-aloud.
 * Usage: <script src=".../premium-tts.js" defer></script>
 *
 * Read Aloud behavior (PowerPoint-style):
 *   - Press Listen (or Shift+R) once to start.
 *   - Current slide speaks. When it ends, the listener STAYS ON.
 *   - Navigate to the next slide (arrow / space / dot / touch) and the
 *     new slide is spoken automatically.
 *   - Press Stop (or Shift+R again) to silence.
 */
(function () {
  let userOn = false;            // user wants TTS active (set by toggle)
  let speaking = false;          // an utterance is currently playing
  let utterance = null;
  let lastSpokenSlideIndex = -1; // dedupe: don't re-speak the same slide
  let button = null;

  function isOn() { return userOn; }
  function isSpeaking() { return speaking; }
  function isSupported() { return 'speechSynthesis' in window; }

  function getVisibleSlide() {
    return document.querySelector('#deck .slide.visible');
  }

  function getVisibleText() {
    const slide = getVisibleSlide();
    if (!slide) return '';
    return slide.innerText.trim();
  }

  function stop() {
    if (!isSupported()) return;
    window.speechSynthesis.cancel();
    userOn = false;
    speaking = false;
    syncButton();
    document.querySelectorAll('.premium-tts-active').forEach((el) => {
      el.classList.remove('premium-tts-active');
    });
  }

  function play() {
    if (!isSupported()) {
      console.warn('[Premium TTS] Web Speech API not supported in this browser');
      return;
    }
    const slide = getVisibleSlide();
    if (!slide) return;
    // Compute index of currently visible slide.
    const allSlides = document.querySelectorAll('#deck .slide');
    const idx = Array.from(allSlides).indexOf(slide);
    // Dedupe: if we're already speaking this slide, don't restart.
    if (idx === lastSpokenSlideIndex && speaking) return;
    const text = (slide.innerText || '').trim();
    if (!text) {
      // Empty slide (e.g. section divider with no text) — don't block the
      // listener; just skip and stay armed.
      lastSpokenSlideIndex = idx;
      return;
    }
    window.speechSynthesis.cancel();
    lastSpokenSlideIndex = idx;
    utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    utterance.onstart = () => { speaking = true; syncButton(); };
    utterance.onend = () => { speaking = false; syncButton(); };
    utterance.onerror = () => { speaking = false; syncButton(); };
    userOn = true;
    window.speechSynthesis.speak(utterance);
    syncButton();
  }

  // Re-speak the new visible slide on every slide change while TTS is on.
  function followSlideChange() {
    if (!userOn) return;
    // Small delay so the new slide's layout/innerText is committed.
    setTimeout(() => {
      if (!userOn) return; // user toggled off in the gap
      play();
    }, 50);
  }

  function bindFollow() {
    // CustomEvent fires in the same window; BroadcastChannel does not echo.
    window.addEventListener('premium:slidechange', () => followSlideChange());
    if (window.PremiumDeckControls && typeof window.PremiumDeckControls.on === 'function') {
      window.PremiumDeckControls.on('slidechange', followSlideChange);
    }
  }

  function toggle() { userOn ? stop() : play(); }

  function syncButton() {
    if (!button) return;
    let label;
    if (userOn && speaking) label = 'Stop';
    else if (userOn) label = 'Stop'; // armed but between slides
    else label = 'Listen';
    button.setAttribute('aria-pressed', userOn ? 'true' : 'false');
    button.innerHTML = label + '<span class="premium-kbd">⇧R</span>';
  }

  function mount(panel) {
    if (!panel || document.getElementById('premium-tts-toggle')) return;
    if (!isSupported()) return;
    const group = document.createElement('div');
    group.className = 'premium-controls__group';
    button = document.createElement('button');
    button.type = 'button';
    button.id = 'premium-tts-toggle';
    button.innerHTML = 'Listen<span class="premium-kbd">⇧R</span>';
    button.title = 'Read slides aloud as you navigate (Shift+R)';
    button.addEventListener('click', toggle);
    group.appendChild(button);
    panel.appendChild(group);
    syncButton();
  }

  function init() {
    const panel = document.querySelector('.premium-controls');
    if (panel) mount(panel);
    document.addEventListener('premium-controls-ready', () => {
      const p = document.querySelector('.premium-controls');
      if (p) mount(p);
    });
    bindFollow();
    // PremiumDeckControls may not exist yet if scripts load after TTS.
    document.addEventListener('DOMContentLoaded', bindFollow);
    document.addEventListener('keydown', (e) => {
      if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      if (new URLSearchParams(location.search).get('presenter') === '1') return;
      if (e.key === 'R' && e.shiftKey) {
        e.preventDefault();
        toggle();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.PremiumTts = { play, stop, toggle, isOn, isSpeaking, isSupported };
})();
