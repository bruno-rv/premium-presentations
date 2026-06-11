// Tests for premium-slide-content.js — PremiumSlideContent pure functions.
// Covers: getTitle, getNotesHtml, getSummaryHtml with various slide markup patterns.

import { makeWindow, loadScript } from './_helpers.mjs';

function makeSlide(html) {
  const dom = makeWindow({
    url: 'http://localhost/test.html',
    slides: `<section class="slide">${html}</section>`,
    withSlides: true,
  });
  loadScript(dom, 'premium-slide-content.js');
  const slide = dom.window.document.querySelector('.slide');
  return { win: dom.window, slide };
}

let passed = 0;
let failed = 0;

function assert(label, condition, detail) {
  if (condition) {
    console.log('  PASS — ' + label);
    passed++;
  } else {
    console.error('  FAIL — ' + label + (detail ? ': ' + detail : ''));
    failed++;
  }
}

// ── getTitle ─────────────────────────────────────────────────────────────────

console.log('Test: getTitle — data-nav-title takes priority');
{
  const { win, slide } = makeSlide('<h2 class="slide__heading">Heading</h2>');
  slide.dataset.navTitle = 'Custom Nav Title';
  assert('data-nav-title', win.PremiumSlideContent.getTitle(slide, 0) === 'Custom Nav Title');
}

console.log('Test: getTitle — .slide__heading');
{
  const { win, slide } = makeSlide('<h2 class="slide__heading">My Heading</h2>');
  assert('slide__heading', win.PremiumSlideContent.getTitle(slide, 0) === 'My Heading');
}

console.log('Test: getTitle — .slide__display fallback');
{
  const { win, slide } = makeSlide('<h1 class="slide__display">Display Title</h1>');
  assert('slide__display', win.PremiumSlideContent.getTitle(slide, 0) === 'Display Title');
}

console.log('Test: getTitle — type-class fallback');
{
  const { win, slide } = makeSlide('<p>No heading here</p>');
  slide.classList.add('slide--divider');
  const title = win.PremiumSlideContent.getTitle(slide, 0);
  assert('slide--divider fallback', title === 'Section', 'got: ' + title);
}

console.log('Test: getTitle — index fallback');
{
  const { win, slide } = makeSlide('<p><!-- nothing useful --></p>');
  const title = win.PremiumSlideContent.getTitle(slide, 4);
  assert('Part N fallback', title === 'Part 5', 'got: ' + title);
}

console.log('Test: getTitle — truncates long titles');
{
  const long = 'A'.repeat(60);
  const { win, slide } = makeSlide(`<h2 class="slide__heading">${long}</h2>`);
  const title = win.PremiumSlideContent.getTitle(slide, 0);
  assert('truncates at 52 chars', title.length <= 52 && title.endsWith('…'), 'len=' + title.length + ' val=' + title);
}

// ── getNotesHtml ──────────────────────────────────────────────────────────────

console.log('Test: getNotesHtml — aside.notes');
{
  const { win, slide } = makeSlide('<aside class="notes">Speaker <strong>note</strong>.</aside>');
  const html = win.PremiumSlideContent.getNotesHtml(slide);
  assert('aside.notes innerHTML', html.includes('Speaker') && html.includes('<strong>'));
}

console.log('Test: getNotesHtml — .slide__notes');
{
  const { win, slide } = makeSlide('<div class="slide__notes">Alt notes.</div>');
  const html = win.PremiumSlideContent.getNotesHtml(slide);
  assert('.slide__notes', html.includes('Alt notes.'));
}

console.log('Test: getNotesHtml — empty when absent');
{
  const { win, slide } = makeSlide('<h2>No notes slide</h2>');
  const html = win.PremiumSlideContent.getNotesHtml(slide);
  assert('no notes → empty string', html === '');
}

// ── getSummaryHtml ────────────────────────────────────────────────────────────

console.log('Test: getSummaryHtml — lead paragraph, 2 sentences only');
{
  const { win, slide } = makeSlide(`
    <div class="slide__body">
      <p>First sentence about the topic. Second sentence adds detail. Third sentence should be cut.</p>
    </div>
  `);
  const html = win.PremiumSlideContent.getSummaryHtml(slide);
  assert('lead has first 2 sentences', /First sentence.*Second sentence/.test(html));
  assert('lead cuts third sentence', !/Third sentence/.test(html));
  assert('wrapped in pp-summary__lead', html.includes('pp-summary__lead'));
}

console.log('Test: getSummaryHtml — bullets up to 4 items');
{
  const { win, slide } = makeSlide(`
    <div class="slide__body">
      <ul><li>One</li><li>Two</li><li>Three</li><li>Four</li><li>Five (cut)</li></ul>
    </div>
  `);
  const html = win.PremiumSlideContent.getSummaryHtml(slide);
  assert('has bullet one', html.includes('One'));
  assert('has bullet four', html.includes('Four'));
  assert('cuts bullet five', !html.includes('Five (cut)'));
  assert('wrapped in pp-summary__bullets', html.includes('pp-summary__bullets'));
}

console.log('Test: getSummaryHtml — blockquote callout');
{
  const { win, slide } = makeSlide(`
    <div class="slide__body">
      <blockquote>"Knowledge is power."</blockquote>
    </div>
  `);
  const html = win.PremiumSlideContent.getSummaryHtml(slide);
  assert('blockquote captured', html.includes('Knowledge is power'));
  assert('wrapped in pp-summary__quote', html.includes('pp-summary__quote'));
}

console.log('Test: getSummaryHtml — .reveal content is NOT removed');
{
  const { win, slide } = makeSlide(`
    <div class="slide__body">
      <p class="reveal">Reveal paragraph with real content.</p>
    </div>
  `);
  const html = win.PremiumSlideContent.getSummaryHtml(slide);
  assert('.reveal paragraph included in summary', html.includes('Reveal paragraph'));
}

console.log('Test: getSummaryHtml — headings are stripped (already in rail title)');
{
  const { win, slide } = makeSlide(`
    <div class="slide__body">
      <h2>Slide Heading</h2>
      <p>Body content here.</p>
    </div>
  `);
  const html = win.PremiumSlideContent.getSummaryHtml(slide);
  assert('heading not in summary', !html.includes('Slide Heading'));
  assert('body content included', html.includes('Body content here'));
}

console.log('Test: getSummaryHtml — notes aside removed from summary');
{
  const { win, slide } = makeSlide(`
    <div class="slide__body">
      <p>Main content.</p>
      <aside class="notes">Private notes.</aside>
    </div>
  `);
  const html = win.PremiumSlideContent.getSummaryHtml(slide);
  assert('notes not in summary', !html.includes('Private notes'));
  assert('content included', html.includes('Main content'));
}

console.log('Test: getSummaryHtml — last-resort title fallback when no extractable body content');
{
  const { win, slide } = makeSlide('<h2 class="slide__heading">Title Only</h2>');
  const html = win.PremiumSlideContent.getSummaryHtml(slide);
  assert('title fallback present', html.includes('Title Only'), 'got: ' + html);
  assert('wrapped in pp-summary__lead', html.includes('pp-summary__lead'));
}

console.log('Test: getSummaryHtml — table summary when no list/para');
{
  const { win, slide } = makeSlide(`
    <div class="slide__body">
      <table>
        <thead><tr><th>Col A</th><th>Col B</th></tr></thead>
        <tbody>
          <tr><td>R1A</td><td>R1B</td></tr>
          <tr><td>R2A</td><td>R2B</td></tr>
          <tr><td>R3A (cut)</td><td>R3B</td></tr>
        </tbody>
      </table>
    </div>
  `);
  const html = win.PremiumSlideContent.getSummaryHtml(slide);
  assert('table headers captured', html.includes('Col A'));
  assert('first row captured', html.includes('R1A'));
  assert('third row cut', !html.includes('R3A'));
}

// ── Summary ───────────────────────────────────────────────────────────────────

console.log('\nResults: ' + passed + ' passed, ' + failed + ' failed');
if (failed > 0) process.exit(1);
process.exit(0);
