// Shared JSDOM fixtures for the presenter/popup test suite.

import { JSDOM } from 'jsdom';
import { readFileSync } from 'fs';
import { join, dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
export const SHARED = join(ROOT, 'assets', 'shared');

// Minimal BroadcastChannel shim backed by a per-process map. All FakeBC
// instances on the same channel name see each other regardless of window.
export class FakeBC {
  constructor(name) {
    this.name = name;
    FakeBC.channels.set(name, FakeBC.channels.get(name) || []);
    FakeBC.channels.get(name).push(this);
    this.listeners = [];
  }
  postMessage(data) {
    const peers = FakeBC.channels.get(this.name) || [];
    for (const p of peers) {
      if (p === this) continue;
      for (const l of p.listeners) {
        try { l({ data }); } catch (e) { console.error('BC handler err', e); }
      }
    }
  }
  addEventListener(_, l) { this.listeners.push(l); }
  close() {}
}
FakeBC.channels = new Map();

export function installGlobalFakeBC() {
  globalThis.BroadcastChannel = FakeBC;
}

// Window-scoped BroadcastChannel router: each window gets its own constructor
// and messages on the same channel name are delivered to all OTHER windows'
// listeners. Use when a test needs strict cross-window (not cross-instance)
// delivery semantics.
export function installWindowRouterBC(win, windows) {
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

export function loadScript(dom, path) {
  dom.window.eval(readFileSync(join(SHARED, path), 'utf8'));
}

const DEFAULT_SLIDES = `
      <section class="slide" id="slide-1"><h1 class="slide__display">One</h1><aside class="notes">Talk about one.</aside></section>
      <section class="slide" id="slide-2"><h1 class="slide__display">Two</h1></section>
`;

// Build a JSDOM deck window with the standard stubs the runtime modules need:
// crypto.randomUUID, document.hasFocus, matchMedia, an IntersectionObserver
// whose registered callback is fired by scrollIntoView (mirrors the real
// browser scroll → IO path SlideEngine relies on), and requestAnimationFrame.
//
// Options:
//   url              — window URL (required)
//   slides           — slide markup inside #deck (default: two slides)
//   withSlides       — false renders an empty #deck (popup windows)
//   focused          — document.hasFocus() return value
//   bc               — BroadcastChannel constructor to install on the window,
//                      'none' to explicitly remove it, or omit to leave as-is
//   animationFrames  — false stubs rAF as a no-op (paused deck simulation)
export function makeWindow({
  url,
  slides = DEFAULT_SLIDES,
  withSlides = true,
  focused = true,
  bc,
  animationFrames = true,
} = {}) {
  const html = `<!doctype html><html><head></head><body>
    <div id="deck">
      ${withSlides ? slides : ''}
    </div>
  </body></html>`;
  const dom = new JSDOM(html, { url, runScripts: 'outside-only', pretendToBeVisual: true });
  if (!dom.window.crypto || !dom.window.crypto.randomUUID) {
    dom.window.crypto = dom.window.crypto || {};
    dom.window.crypto.randomUUID = () => 'sess-' + Math.random().toString(36).slice(2, 10);
  }
  Object.defineProperty(dom.window.document, 'hasFocus', { value: () => focused, configurable: true });
  dom.window.matchMedia = dom.window.matchMedia || (() => ({
    matches: false,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  const ioInstances = [];
  dom.window.IntersectionObserver = class {
    constructor(cb) { this.cb = cb; ioInstances.push(this); }
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  dom.window.HTMLElement.prototype.scrollIntoView = function () {
    for (const io of ioInstances) {
      try { io.cb([{ target: this, isIntersecting: true }]); } catch (_) {}
    }
  };
  dom.window.requestAnimationFrame = animationFrames ? ((cb) => setTimeout(cb, 0)) : (() => 0);
  dom.window.cancelAnimationFrame = (id) => clearTimeout(id);
  if (bc === 'none') {
    dom.window.BroadcastChannel = undefined;
  } else if (bc) {
    dom.window.BroadcastChannel = bc;
  }
  return dom;
}
