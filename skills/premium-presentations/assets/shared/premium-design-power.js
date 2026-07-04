(function () {
  'use strict';

  var MOTION_PROFILES = {
    calm: {
      label: 'Calm',
      revealMs: 420,
      depth: 0.55,
      default3d: 'off',
    },
    cinematic: {
      label: 'Cinematic',
      revealMs: 760,
      depth: 1.35,
      default3d: 'depth',
    },
    technical: {
      label: 'Technical',
      revealMs: 280,
      depth: 0.35,
      default3d: 'tilt',
    },
    workshop: {
      label: 'Workshop',
      revealMs: 360,
      depth: 0.2,
      default3d: 'off',
    },
    pitch: {
      label: 'Pitch',
      revealMs: 540,
      depth: 0.95,
      default3d: 'card',
    },
  };

  var MOTION_3D_MODES = { off: true, ambient: true, tilt: true, depth: true, card: true };

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function slugify(value) {
    var slug = String(value || 'custom-theme')
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
    return slug || 'custom-theme';
  }

  function safeCssIdent(value) {
    return slugify(value).replace(/^-?([0-9])/, 'theme-$1');
  }

  function safeColor(value, fallback) {
    var raw = String(value || '').trim();
    if (/^#[0-9a-f]{3}(?:[0-9a-f]{3})?$/i.test(raw)) return raw;
    if (/^(?:rgb|hsl)a?\([\d\s.,%/-]+\)$/i.test(raw)) return raw;
    if (/^var\(--[a-z0-9-]+\)$/i.test(raw)) return raw;
    return fallback;
  }

  function safeFont(value, fallback) {
    var raw = String(value || '').trim();
    if (!raw) return fallback;
    if (/^[a-z0-9\s"',._-]+$/i.test(raw)) return raw;
    return fallback;
  }

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function toFiniteNumber(value, fallback) {
    var n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function buildThemeCss(config) {
    config = config || {};
    var id = safeCssIdent(config.id || config.label || 'custom-theme');
    var bg = safeColor(config.bg, '#101820');
    var text = safeColor(config.text, '#f7fafc');
    var accent = safeColor(config.accent, '#4a9eff');
    var surface = safeColor(config.surface, '#182838');
    var surface2 = safeColor(config.surface2, surface);
    var border = safeColor(config.border, 'rgba(255,255,255,0.16)');
    var borderBright = safeColor(config.borderBright, accent);
    var textDim = safeColor(config.textDim, 'rgba(247,250,252,0.72)');
    var fontDisplay = safeFont(config.fontDisplay, 'system-ui, sans-serif');
    var fontBody = safeFont(config.fontBody, 'system-ui, sans-serif');
    var fontMono = safeFont(config.fontMono, 'ui-monospace, monospace');

    return [
      'html[data-theme="' + id + '"] {',
      '  --bg: ' + bg + ';',
      '  --text: ' + text + ';',
      '  --text-dim: ' + textDim + ';',
      '  --accent: ' + accent + ';',
      '  --surface: ' + surface + ';',
      '  --surface2: ' + surface2 + ';',
      '  --border: ' + border + ';',
      '  --border-bright: ' + borderBright + ';',
      '  --font-display: ' + fontDisplay + ';',
      '  --font-body: ' + fontBody + ';',
      '  --font-mono: ' + fontMono + ';',
      '}',
    ].join('\n');
  }

  function applyTheme(config, doc) {
    doc = doc || document;
    var id = safeCssIdent((config || {}).id || (config || {}).label || 'custom-theme');
    var styleId = 'premium-theme-composer-' + id;
    var style = doc.getElementById(styleId);
    if (!style) {
      style = doc.createElement('style');
      style.id = styleId;
      doc.head.appendChild(style);
    }
    style.textContent = buildThemeCss(config);
    doc.documentElement.setAttribute('data-theme', id);
    if ((config || {}).label) {
      doc.documentElement.setAttribute('data-theme-label-' + id, String(config.label));
    }
    return { id: id, css: style.textContent };
  }

  function applyMotionProfile(name, doc) {
    doc = doc || document;
    var profileName = MOTION_PROFILES[name] ? name : 'calm';
    var profile = MOTION_PROFILES[profileName];
    var root = doc.documentElement;
    root.setAttribute('data-motion-profile', profileName);
    root.style.setProperty('--motion-reveal-ms', profile.revealMs + 'ms');
    root.style.setProperty('--motion-depth', String(profile.depth));
    if (MOTION_3D_MODES[profile.default3d]) {
      root.setAttribute('data-3d', profile.default3d);
      root.setAttribute('data-parallax', profile.default3d === 'off' ? 'off' : 'on');
    }
    if (window.PremiumPresentations && typeof window.PremiumPresentations.set3dMode === 'function') {
      try { window.PremiumPresentations.set3dMode(profile.default3d); } catch (_) {}
    }
    return profile;
  }

  function textForDensity(slide) {
    var clone = slide.cloneNode(true);
    clone.querySelectorAll('aside.notes,.slide__notes,script,style,svg').forEach(function (el) {
      el.remove();
    });
    return (clone.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function analyzeSlide(slide) {
    var text = textForDensity(slide);
    var words = text ? text.split(/\s+/).filter(Boolean).length : 0;
    var revealCount = slide.querySelectorAll('.reveal').length;
    var cardCount = slide.querySelectorAll('.stat-card,.glass-card,.kpi,.compare-panel,.setup-step,.pipeline-stage,.checklist-item,.tl-col,.aside-card,.why-panel,.dp-card,.dp-metric').length;
    var tableCount = slide.querySelectorAll('table,.data-table').length;
    var headingCount = slide.querySelectorAll('h1,h2,h3,.slide__display,.slide__heading').length;
    var warnings = [];
    var score = 0;

    if (words > 120) {
      score += 3;
      warnings.push({ type: 'text', message: 'Shorten text or split this into two slides.' });
    } else if (words > 80) {
      score += 1;
      warnings.push({ type: 'text', message: 'Text is getting dense; consider a tighter layout.' });
    }
    if (revealCount > 6) {
      score += 2;
      warnings.push({ type: 'reveals', message: 'Too many reveals; group or reduce reveal steps.' });
    }
    if (cardCount > 6) {
      score += 2;
      warnings.push({ type: 'cards', message: 'Too many cards; collapse into a table or matrix.' });
    }
    if (tableCount > 1) {
      score += 1;
      warnings.push({ type: 'tables', message: 'Multiple tables compete for attention.' });
    }
    if (headingCount > 2) {
      score += 1;
      warnings.push({ type: 'hierarchy', message: 'Too many title-like elements on one slide.' });
    }

    return {
      level: score >= 4 ? 'high' : (score >= 2 ? 'medium' : 'low'),
      score: score,
      metrics: {
        words: words,
        reveals: revealCount,
        cards: cardCount,
        tables: tableCount,
        headings: headingCount,
      },
      warnings: warnings,
    };
  }

  function analyzeDeck(doc) {
    doc = doc || document;
    return Array.from(doc.querySelectorAll('.slide')).map(function (slide, index) {
      var report = analyzeSlide(slide);
      report.index = index + 1;
      report.title = (slide.getAttribute('data-nav-title') || slide.querySelector('h1,h2,.slide__heading,.slide__display')?.textContent || ('Slide ' + (index + 1))).trim();
      return report;
    });
  }

  function renderChecklist(data) {
    var items = asArray(data.items).map(function (item) {
      return '<li><span aria-hidden="true"></span>' + escapeHtml(item) + '</li>';
    }).join('');
    return '<div class="dp-component dp-component--checklist"><h3>' + escapeHtml(data.title || 'Checklist') + '</h3><ul>' + items + '</ul></div>';
  }

  function renderStats(data) {
    return '<div class="dp-component dp-component--stats">' + asArray(data.items).map(function (item) {
      return '<div class="dp-metric"><strong>' + escapeHtml(item.value || item[0] || '') + '</strong><span>' + escapeHtml(item.label || item[1] || '') + '</span></div>';
    }).join('') + '</div>';
  }

  function renderCompare(data) {
    var left = data.left || {};
    var right = data.right || {};
    return '<div class="dp-component dp-component--compare">'
      + '<section><h3>' + escapeHtml(left.title || 'Before') + '</h3><p>' + escapeHtml(left.body || '') + '</p></section>'
      + '<section><h3>' + escapeHtml(right.title || 'After') + '</h3><p>' + escapeHtml(right.body || '') + '</p></section>'
      + '</div>';
  }

  function renderTimeline(data) {
    return '<ol class="dp-component dp-component--timeline">' + asArray(data.items).map(function (item, index) {
      return '<li><span>' + String(index + 1).padStart(2, '0') + '</span><strong>' + escapeHtml(item.title || item) + '</strong><p>' + escapeHtml(item.body || '') + '</p></li>';
    }).join('') + '</ol>';
  }

  function renderCode(data) {
    return '<div class="dp-component dp-component--code"><div>' + escapeHtml(data.title || 'Code') + '</div><pre><code>' + escapeHtml(data.code || '') + '</code></pre></div>';
  }

  var COMPONENT_RENDERERS = {
    checklist: renderChecklist,
    stats: renderStats,
    compare: renderCompare,
    timeline: renderTimeline,
    code: renderCode,
  };

  function renderComponent(name, data) {
    data = data || {};
    var renderer = COMPONENT_RENDERERS[name] || renderChecklist;
    return renderer(data);
  }

  function renderExecutiveSummary(data) {
    return '<div class="dp-layout dp-layout--executive-summary"><h3>' + escapeHtml(data.title || 'Executive summary') + '</h3><div>' + renderStats({ items: data.metrics || [] }) + '</div><p>' + escapeHtml(data.summary || '') + '</p></div>';
  }

  function renderDecisionMatrix(data) {
    var columns = asArray(data.columns);
    var rows = asArray(data.rows);
    var head = '<tr><th>Option</th>' + columns.map(function (col) { return '<th>' + escapeHtml(col) + '</th>'; }).join('') + '</tr>';
    var body = rows.map(function (row) {
      row = asArray(row);
      return '<tr>' + row.map(function (cell, index) {
        return index === 0 ? '<th>' + escapeHtml(cell) + '</th>' : '<td>' + escapeHtml(cell) + '</td>';
      }).join('') + '</tr>';
    }).join('');
    return '<div class="dp-layout dp-layout--decision-matrix"><h3>' + escapeHtml(data.title || 'Decision matrix') + '</h3><table><thead>' + head + '</thead><tbody>' + body + '</tbody></table></div>';
  }

  function renderEvidenceWall(data) {
    return '<div class="dp-layout dp-layout--evidence-wall"><h3>' + escapeHtml(data.title || 'Evidence wall') + '</h3><div>' + asArray(data.items).map(function (item) {
      return '<article><strong>' + escapeHtml(item.title || item) + '</strong><p>' + escapeHtml(item.body || '') + '</p></article>';
    }).join('') + '</div></div>';
  }

  function renderBeforeAfter(data) {
    return '<div class="dp-layout dp-layout--before-after"><h3>' + escapeHtml(data.title || 'Before / after') + '</h3>' + renderCompare({ left: data.before || {}, right: data.after || {} }) + '</div>';
  }

  function renderProcessLadder(data) {
    return '<div class="dp-layout dp-layout--process-ladder"><h3>' + escapeHtml(data.title || 'Process ladder') + '</h3>' + renderTimeline({ items: data.steps || data.items || [] }) + '</div>';
  }

  function renderGenericLayout(name, data) {
    return '<div class="dp-layout dp-layout--' + safeCssIdent(name) + '"><h3>' + escapeHtml(data.title || name.replace(/-/g, ' ')) + '</h3><p>' + escapeHtml(data.body || '') + '</p></div>';
  }

  var LAYOUT_RENDERERS = {
    'executive-summary': renderExecutiveSummary,
    'evidence-wall': renderEvidenceWall,
    'quote-proof': function (data) { return renderGenericLayout('quote-proof', data); },
    'split-argument': function (data) { return renderGenericLayout('split-argument', data); },
    teardown: function (data) { return renderGenericLayout('teardown', data); },
    'benchmark-table': renderDecisionMatrix,
    'architecture-map': function (data) { return renderGenericLayout('architecture-map', data); },
    'process-ladder': renderProcessLadder,
    'case-study': function (data) { return renderGenericLayout('case-study', data); },
    'before-after': renderBeforeAfter,
    'decision-matrix': renderDecisionMatrix,
  };

  function renderLayout(name, data) {
    data = data || {};
    var renderer = LAYOUT_RENDERERS[name] || renderGenericLayout.bind(null, name || 'layout');
    return renderer(data);
  }

  function normalizeSeries(values) {
    values = asArray(values).map(function (value) { return toFiniteNumber(value, 0); });
    if (!values.length) values = [0, 1];
    var min = Math.min.apply(Math, values);
    var max = Math.max.apply(Math, values);
    if (min === max) max = min + 1;
    return { values: values, min: min, max: max };
  }

  function renderLineViz(data) {
    var series = normalizeSeries(data.values);
    var width = 320;
    var height = 130;
    var points = series.values.map(function (value, index) {
      var x = series.values.length === 1 ? width / 2 : (index / (series.values.length - 1)) * width;
      var y = height - ((value - series.min) / (series.max - series.min)) * height;
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    return '<figure class="dp-viz dp-viz--line" role="img" aria-label="' + escapeHtml(data.title || 'Line chart') + '"><figcaption>' + escapeHtml(data.title || 'Line chart') + '</figcaption><svg viewBox="0 0 320 150" aria-hidden="true"><polyline points="' + points + '"></polyline></svg></figure>';
  }

  function renderScatterViz(data) {
    var points = asArray(data.points).map(function (point) {
      var x = clamp(toFiniteNumber(point[0], 0), 0, 100);
      var y = 100 - clamp(toFiniteNumber(point[1], 0), 0, 100);
      return '<circle cx="' + x + '%" cy="' + y + '%" r="5"></circle>';
    }).join('');
    return '<figure class="dp-viz dp-viz--scatter"><figcaption>' + escapeHtml(data.title || 'Scatter') + '</figcaption><svg viewBox="0 0 100 100" aria-hidden="true">' + points + '</svg></figure>';
  }

  function renderWaterfallViz(data) {
    var values = asArray(data.values);
    return '<figure class="dp-viz dp-viz--waterfall"><figcaption>' + escapeHtml(data.title || 'Waterfall') + '</figcaption><div>' + values.map(function (value) {
      var n = toFiniteNumber(value, 0);
      var h = clamp(Math.abs(n), 10, 100);
      return '<span style="--v:' + h + '%" data-dir="' + (n < 0 ? 'down' : 'up') + '">' + escapeHtml(n) + '</span>';
    }).join('') + '</div></figure>';
  }

  function renderFunnelViz(data) {
    var values = asArray(data.values);
    var max = Math.max.apply(Math, values.map(function (value) { return toFiniteNumber(value, 0); }).concat([1]));
    return '<figure class="dp-viz dp-viz--funnel"><figcaption>' + escapeHtml(data.title || 'Funnel') + '</figcaption><ol>' + values.map(function (value, index) {
      var n = toFiniteNumber(value, 0);
      var pct = clamp((n / max) * 100, 12, 100);
      return '<li style="--w:' + pct.toFixed(1) + '%"><span>Step ' + (index + 1) + '</span><strong>' + escapeHtml(n) + '</strong></li>';
    }).join('') + '</ol></figure>';
  }

  function renderHeatmapViz(data) {
    var rows = asArray(data.rows);
    var cells = [];
    rows.forEach(function (row) {
      asArray(row).slice(1).forEach(function (value) { cells.push(toFiniteNumber(value, 0)); });
    });
    var max = Math.max.apply(Math, cells.concat([1]));
    return '<figure class="dp-viz dp-viz--heatmap"><figcaption>' + escapeHtml(data.title || 'Heatmap') + '</figcaption><div>' + rows.map(function (row) {
      row = asArray(row);
      return '<section><strong>' + escapeHtml(row[0] || '') + '</strong>' + row.slice(1).map(function (value) {
        var n = toFiniteNumber(value, 0);
        return '<span style="--heat:' + clamp(n / max, 0, 1).toFixed(2) + '">' + escapeHtml(n) + '</span>';
      }).join('') + '</section>';
    }).join('') + '</div></figure>';
  }

  function renderSankeyViz(data) {
    return '<figure class="dp-viz dp-viz--sankey"><figcaption>' + escapeHtml(data.title || 'Flow') + '</figcaption><div>' + asArray(data.links).map(function (link) {
      var from = link[0];
      var to = link[1];
      var value = toFiniteNumber(link[2], 1);
      return '<span style="--weight:' + clamp(value, 1, 10) + '"><b>' + escapeHtml(from) + '</b><i></i><b>' + escapeHtml(to) + '</b></span>';
    }).join('') + '</div></figure>';
  }

  function renderKpiTrendViz(data) {
    return '<figure class="dp-viz dp-viz--kpi-trend"><figcaption>' + escapeHtml(data.title || 'KPI trend') + '</figcaption>' + renderStats({ items: data.items || [] }) + '</figure>';
  }

  var VIZ_RENDERERS = {
    line: renderLineViz,
    scatter: renderScatterViz,
    waterfall: renderWaterfallViz,
    funnel: renderFunnelViz,
    heatmap: renderHeatmapViz,
    sankey: renderSankeyViz,
    'kpi-trend': renderKpiTrendViz,
  };

  function renderDataViz(type, data) {
    data = data || {};
    var renderer = VIZ_RENDERERS[type] || renderLineViz;
    return renderer(data);
  }

  function sourceKind(src) {
    if (!src) return 'missing';
    if (/^data:/i.test(src)) return 'embedded';
    if (/^(?:https?:)?\/\//i.test(src)) return 'remote';
    if (/^(?:blob:|file:|\/)/i.test(src)) return 'absolute';
    return 'relative';
  }

  function auditAssets(doc) {
    doc = doc || document;
    var assets = [];
    var warnings = [];
    var nodes = Array.from(doc.querySelectorAll('img[src],video[src],source[src],[data-visual-asset][data-asset-src]'));
    nodes.forEach(function (node, index) {
      var src = node.getAttribute('src') || node.getAttribute('data-asset-src') || '';
      var role = node.getAttribute('data-visual-asset') || node.getAttribute('alt') || node.tagName.toLowerCase();
      var kind = sourceKind(src);
      assets.push({ index: index + 1, role: role, src: src, kind: kind });
      if (kind === 'remote') {
        warnings.push({ type: 'remote', message: 'Remote asset should be embedded or bundled: ' + src });
      } else if (kind === 'relative') {
        warnings.push({ type: 'relative', message: 'Relative asset needs a portable bundle path or data URI: ' + src });
      } else if (kind === 'missing') {
        warnings.push({ type: 'missing', message: 'Visual asset is missing a source.' });
      }
    });
    return { assets: assets, warnings: warnings };
  }

  function setHtml(el, html) {
    if (el) el.innerHTML = html;
  }

  function bindStudio(doc) {
    if (!doc.getElementById('design-power-studio')) return;
    var api = window.PremiumDesignPower;
    var themeOutput = doc.getElementById('theme-css-output');
    var componentPreview = doc.getElementById('component-preview');
    var componentCode = doc.getElementById('component-code');
    var layoutPreview = doc.getElementById('layout-preview');
    var layoutCode = doc.getElementById('layout-code');
    var densityOutput = doc.getElementById('density-output');
    var vizPreview = doc.getElementById('viz-preview');
    var vizCode = doc.getElementById('viz-code');
    var assetOutput = doc.getElementById('asset-output');

    function themeConfig() {
      return {
        id: doc.getElementById('theme-id')?.value || 'studio-custom',
        bg: doc.getElementById('theme-bg')?.value || '#101820',
        text: doc.getElementById('theme-text')?.value || '#f7fafc',
        accent: doc.getElementById('theme-accent')?.value || '#4a9eff',
        surface: doc.getElementById('theme-surface')?.value || '#182838',
      };
    }

    function refreshTheme() {
      var result = api.themeComposer.applyTheme(themeConfig(), doc);
      if (themeOutput) themeOutput.value = result.css;
    }

    function refreshComponent() {
      var html = api.components.render(doc.getElementById('component-kind')?.value || 'checklist', {
        title: 'Design gate',
        items: ['Theme tokens', 'Motion profile', 'Density pass'],
        left: { title: 'Raw', body: 'Static HTML fragments' },
        right: { title: 'Runtime', body: 'Shared, tested renderers' },
        code: '<' + 'section class="slide">...</' + 'section>',
      });
      setHtml(componentPreview, html);
      if (componentCode) componentCode.value = html;
    }

    function refreshLayout() {
      var kind = doc.getElementById('layout-kind')?.value || 'decision-matrix';
      var html = api.layouts.render(kind, {
        title: 'Design choice',
        columns: ['Impact', 'Risk', 'Effort'],
        rows: [
          ['Theme composer', 'High', 'Low', 'Medium'],
          ['Presenter polish', 'Medium', 'Low', 'Low'],
        ],
        items: [
          { title: 'Signal', body: 'One idea per block' },
          { title: 'Proof', body: 'Evidence beside claim' },
        ],
      });
      setHtml(layoutPreview, html);
      if (layoutCode) layoutCode.value = html;
    }

    function refreshDensity() {
      var fixture = doc.createElement('section');
      fixture.className = 'slide';
      fixture.innerHTML = doc.getElementById('density-html')?.value || '';
      var report = api.density.analyzeSlide(fixture);
      if (densityOutput) {
        densityOutput.textContent = JSON.stringify(report, null, 2);
      }
    }

    function refreshViz() {
      var kind = doc.getElementById('viz-kind')?.value || 'line';
      var data = {
        title: 'Design system adoption',
        values: [12, 18, 32, 51],
        rows: [['A', 1, 4, 2], ['B', 3, 2, 5], ['C', 4, 5, 3]],
        links: [['Ideas', 'Slides', 5], ['Slides', 'Rehearsal', 3], ['Rehearsal', 'Talk', 4]],
        points: [[10, 20], [32, 58], [62, 43], [90, 81]],
        items: [{ value: '+38%', label: 'Adoption' }, { value: '12', label: 'Decks' }],
      };
      var html = api.dataViz.render(kind, data);
      setHtml(vizPreview, html);
      if (vizCode) vizCode.value = html;
    }

    function refreshAssets() {
      var fixture = doc.createElement('template');
      fixture.innerHTML = doc.getElementById('asset-html')?.value || '';
      var report = api.assets.audit(fixture.content);
      if (assetOutput) assetOutput.textContent = JSON.stringify(report, null, 2);
    }

    Array.from(doc.querySelectorAll('[data-motion-profile-button]')).forEach(function (button) {
      button.addEventListener('click', function () {
        api.motionProfiles.apply(button.getAttribute('data-motion-profile-button'), doc);
      });
    });
    Array.from(doc.querySelectorAll('#theme-composer input')).forEach(function (input) {
      input.addEventListener('input', refreshTheme);
    });
    doc.getElementById('component-kind')?.addEventListener('change', refreshComponent);
    doc.getElementById('layout-kind')?.addEventListener('change', refreshLayout);
    doc.getElementById('density-html')?.addEventListener('input', refreshDensity);
    doc.getElementById('viz-kind')?.addEventListener('change', refreshViz);
    doc.getElementById('asset-html')?.addEventListener('input', refreshAssets);

    refreshTheme();
    refreshComponent();
    refreshLayout();
    refreshDensity();
    refreshViz();
    refreshAssets();
  }

  function init(doc) {
    doc = doc || document;
    var profile = doc.documentElement.getAttribute('data-motion-profile');
    if (profile) applyMotionProfile(profile, doc);
    if (doc.documentElement.getAttribute('data-density-auto') === 'on') {
      analyzeDeck(doc).forEach(function (report) {
        var slide = doc.querySelectorAll('.slide')[report.index - 1];
        if (slide) slide.setAttribute('data-density-level', report.level);
      });
    }
    bindStudio(doc);
  }

  window.PremiumDesignPower = {
    themeComposer: {
      sanitizeId: safeCssIdent,
      buildThemeCss: buildThemeCss,
      applyTheme: applyTheme,
    },
    motionProfiles: {
      all: MOTION_PROFILES,
      apply: applyMotionProfile,
    },
    density: {
      analyzeSlide: analyzeSlide,
      analyzeDeck: analyzeDeck,
    },
    components: {
      names: Object.keys(COMPONENT_RENDERERS),
      render: renderComponent,
    },
    layouts: {
      names: Object.keys(LAYOUT_RENDERERS),
      render: renderLayout,
    },
    dataViz: {
      names: Object.keys(VIZ_RENDERERS),
      render: renderDataViz,
    },
    assets: {
      audit: auditAssets,
    },
    init: init,
  };

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () { init(document); });
    } else {
      init(document);
    }
  }
})();
