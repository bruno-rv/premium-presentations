// BC transport regression test: validates that popup rail click drives the
// deck AND deck slidechange updates the popup, using BroadcastChannel only
// (no localStorage, no window.opener). Complements test-popup-storage.mjs
// which tests the localStorage transport.

import { JSDOM } from 'jsdom';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHARED = join(__dirname, '..', 'shared');

// Polyfill BroadcastChannel as a cross-window router. Each window gets its
// own BroadcastChannel constructor; messages on the same name are delivered
// to all OTHER windows' listeners.
const windows = [];
function installBroadcastChannel(win) {
  win.BroadcastChannel = class {
    constructor(name) {
      this.name = name;
      this._listeners = new Set();
      this._win = win;
      win.__bcs = win.__bcs || new Map();
      if (!win.__bcs.has(name)) win.__bcs.set(name, new Set());
      win.__bcs.get(name).add(this);
    }
    postMessage(data) {
      for (const other of windows) {
        if (other === this._win) continue;
        const otherBcs = other.__bcs && other.__bcs.get(this.name);
        if (!otherBcs) continue;
        for (const bc of otherBcs) {
          for (const l of bc._listeners) {
            try { l({ data }); } catch (e) { console.error('BC listener threw:', e); }
          }
        }
      }
    }
    addEventListener(type, listener) {
      if (type === 'message') this._listeners.add(listener);
    }
    removeEventListener(type, listener) {
      if (type === 'message') this._listeners.delete(listener);
    }
    close() {
      this._win.__bcs.get(this.name).delete(this);
    }
  };
}

function makeWindow({ url, withSlides = true, focused = true } = {}) {
  const html = `<!doctype html><html><head></head><body>
    <div id="deck">
      ${withSlides ? `
      <section class="slide" id="slide-1"><h1 class="slide__display">One</h1><aside class="notes">Talk about one.</aside></section>
      <section class="slide" id="slide-2"><h1 class="slide__display">Two</h1></section>
      ` : ''}
    </div>
  </body></html>`;
  const dom = new JSDOM(html, {
    url, runScripts: 'outside-only', pretendToBeVisual: true,
  });
  if (!dom.window.crypto || !dom.window.crypto.randomUUID) {
    dom.window.crypto = dom.window.crypto || {};
    dom.window.crypto.randomUUID = () => 'sess-' + Math.random().toString(36).slice(2, 10);
  }
  Object.defineProperty(dom.window.document, 'hasFocus', { value: () => focused, configurable: true });
  installBroadcastChannel(dom.window);
  const ioInstances = [];
  dom.window.IntersectionObserver = class {
    constructor(cb) { this.cb = cb; ioInstances.push(this); }
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  dom.window.HTMLElement.prototype.scrollIntoView = function () {
    for (const io of ioInstances) try { io.cb([{ target: this, isIntersecting: true }]); } catch (_) {}
  };
  dom.window.requestAnimationFrame = (cb) => setTimeout(cb, 0);
  windows.push(dom.window);
  return dom;
}

function loadScript(dom, path) {
  dom.window.eval(readFileSync(join(SHARED, path), 'utf8'));
}

console.log('Test: BroadcastChannel transport only');
const deck = makeWindow({ url: 'http://localhost/deck.html', focused: true });
loadScript(deck, 'premium-controller.js');
loadScript(deck, 'premium-timer.js');
const slideEngineJs = readFileSync(join(SHARED, 'slide-engine.js'), 'utf8');
deck.window.eval(slideEngineJs);
deck.window.eval('new SlideEngine();');

const popup = makeWindow({
  url: 'http://localhost/deck.html?presenter=1&session=PLACEHOLDER',
  focused: true,
  withSlides: false,
});
loadScript(popup, 'premium-controller.js');
loadScript(popup, 'premium-presenter.js');
const deckSession = deck.window.document.documentElement.dataset.session;
console.log('  deck session:', deckSession);
popup.window.history.replaceState(null, '', 'http://localhost/deck.html?presenter=1&session=' + deckSession);

loadScript(deck, 'premium-presenter.js');

// Wait for handshake
await new Promise((r) => setTimeout(r, 300));

const list = popup.window.document.getElementById('pp-list');
if (!list) throw new Error('popup pp-list missing after handshake');
const items = list.querySelectorAll('li');
if (items.length !== 2) throw new Error('expected 2 rail items, got ' + items.length);
console.log('  PASS — popup received snapshot via BroadcastChannel');

// Test popup→deck: rail click drives deck
items[0].click();
await new Promise((r) => setTimeout(r, 200));
const state = deck.window.PremiumDeckControls.getState();
if (state.index !== 0) throw new Error('expected deck index=0 after popup click on first item, got ' + state.index);
console.log('  PASS — popup rail click drove deck via BC (item 0)');

items[1].click();
await new Promise((r) => setTimeout(r, 200));
const state2 = deck.window.PremiumDeckControls.getState();
if (state2.index !== 1) throw new Error('expected deck index=1 after popup click on second item, got ' + state2.index);
console.log('  PASS — popup rail click drove deck via BC (item 1)');

// Test deck→popup: trigger deck slidechange and verify popup receives
deck.window.PremiumDeckControls.goTo(0);
await new Promise((r) => setTimeout(r, 200));
const counter = popup.window.document.getElementById('pp-counter');
const counterText = counter ? counter.textContent : '(no counter)';
console.log('  popup counter after deck.goTo(0):', counterText);
if (!counterText.startsWith('1 /')) throw new Error('popup did not receive slidechange from deck; counter=' + counterText);
console.log('  PASS — deck slidechange drove popup counter via BC');

process.exit(0);
