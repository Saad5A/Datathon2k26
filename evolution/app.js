/* pancakess — Evolution Braid
 * A custom SVG ancestry visualization. Data is built by build_data.py.
 */
(() => {
  "use strict";

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const fmt = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v) ? "—" : Number(v).toFixed(d));
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const familyInk = { gam:'#9A610B',extra_trees:'#087E72',logistic:'#0873A6',xgboost:'#BD5800',hgb:'#B93056',catboost:'#6743AA',random_forest:'#4F7910',adaboost:'#B33379',mlp:'#53616C',lightgbm:'#58770A',gradient_boosting:'#9A5B0D',unknown:'#586A64' };
  const familyColor = family => familyInk[family] || familyInk.unknown;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const VIEWS = {
    blind: {
      kicker: "01 / Blind search",
      title: "The Ascent<br>of the <em>GAM</em>",
      lede: "A blind search through 2,403 genomes, eleven model families, and eighty generations. One lineage rises above the field.",
      stats: "2,403 genomes · 80 generations · 4,322 edges",
    },
    c1opt: {
      kicker: "02 / C1-seeded search",
      title: "The Second<br><em>Ascent</em>",
      lede: "C1 was seeded into the population. From a different start, the same GAM genome re-emerges.",
      stats: "1,102 genomes · 50 generations · 1,963 edges",
    },
    arena: {
      kicker: "03 / Racing arena",
      title: "The<br><em>Knockout</em>",
      lede: "2,130 enter. Half are killed on the screening fold. Two survive. The champion is the same GAM.",
      stats: "2,130 genomes · 80 generations · 2 alive",
    },
  };

  const state = {
    meta: null,
    data: {},
    view: "blind",
    mode: "curated",
    selected: null,
    hover: null,
    hiddenFamilies: new Set(),
    showC1: true,
    search: "",
    reveal: 80,
    dossierOpen: true,
    playing: false,
    playRAF: null,
    transform: null,
    prepared: null,
    animateNext: true,
    zoom: null,
    svg: null,
  };

  const els = {};
  window.__errors = [];
  window.addEventListener("error", (e) => {
    window.__errors.push({ message: e.message, stack: e.error?.stack, filename: e.filename, lineno: e.lineno });
  });
  window.addEventListener("unhandledrejection", (e) => {
    window.__errors.push({ message: String(e.reason), stack: e.reason?.stack });
  });
  let resizeTimer = null;

  /* ------------------------------------------------------------------ */
  /* boot                                                               */
  /* ------------------------------------------------------------------ */

  async function boot() {
    const [meta, blind, c1opt, arena] = await Promise.all([
      d3.json("assets/meta.json"),
      d3.json("assets/blind.json"),
      d3.json("assets/c1opt.json"),
      d3.json("assets/arena.json"),
    ]);
    state.meta = meta;
    state.data = { blind, c1opt, arena };
    cacheEls();
    bind();
    const params = new URLSearchParams(location.search);
    if (params.get("ui") === "1") document.body.classList.remove("focus");
    const qv = params.get("view");
    if (qv && state.data[qv]) state.view = qv;
    const qm = params.get("mode");
    if (qm === "full" || qm === "curated") state.mode = qm;
    state.reveal = state.data[state.view].stats.generations;
    if (window.matchMedia("(max-width: 900px)").matches) {
      state.dossierOpen = false;
      els.dossier.classList.add("hidden");
      document.body.classList.add("dossier-closed");
    }
    render();
    animateChampion();
  }

  function cacheEls() {
    els.railTitle = $("#railTitle");
    els.railLede = $("#railLede");
    els.figureList = $("#figureList");
    els.viewNav = $("#viewNav");
    els.canvasKicker = $("#canvasKicker");
    els.canvasStats = $("#canvasStats");
    els.canvasWrap = $("#canvasWrap");
    els.svg = $("#braid");
    els.tooltip = $("#tooltip");
    els.dossier = $("#dossier");
    els.canvasCorner = $("#canvasCorner");
    els.timeRange = $("#timeRange");
    els.timeLabel = $("#timeLabel");
    els.timelineTicks = $("#timelineTicks");
    els.btnPlay = $("#btnPlay");
    els.btnReset = $("#btnReset");
    els.playText = $("#playText");
    els.btnIsolate = $("#btnIsolate");
    els.btnC1 = $("#btnC1");
    els.familyLegend = $("#familyLegend");
    els.search = $("#search");
    els.searchCount = $("#searchCount");
    els.toast = $("#toast");
  }

  /* ------------------------------------------------------------------ */
  /* data preparation                                                   */
  /* ------------------------------------------------------------------ */

  function metric(n, key = "top243") {
    if (key === "top500") return n.top500 ?? n.screen_top500 ?? null;
    if (key === "avg_precision") return n.avg_precision ?? n.screen_ap ?? null;
    return n.top243 ?? n.screen_top243 ?? null;
  }

  function prepare() {
    const data = state.data[state.view];
    const rect = els.canvasWrap.getBoundingClientRect();
    const W = Math.max(640, rect.width || 900);
    const H = Math.max(480, rect.height || 620);
    const left = 62;
    const right = state.showC1 ? 250 : 62;
    const top = 66;
    const bottom = 56;
    const treeW = Math.max(120, W - left - right);
    const maxGen = Math.max(1, data.stats.generations);

    // Compress the plateau: most of the story happens before generation 22.
    const breakGen = Math.min(22, maxGen);
    const split = maxGen <= breakGen ? 1 : 0.56;
    const x = (g) => {
      if (g <= breakGen) return left + (g / Math.max(1, breakGen)) * treeW * split;
      return left + treeW * split + ((g - breakGen) / Math.max(1, maxGen - breakGen)) * treeW * (1 - split);
    };
    const genFromX = (px) => {
      const t = clamp((px - left) / Math.max(1, treeW), 0, 1);
      if (t <= split) return (t / Math.max(0.0001, split)) * breakGen;
      return breakGen + ((t - split) / Math.max(0.0001, 1 - split)) * (maxGen - breakGen);
    };

    const nodes = data.nodes.filter((n) => !n.is_control);
    const byId = new Map(nodes.map((n) => [n.id, n]));

    // Story / champion lineage (primary-parent chain).
    let story = (data.story || []).map((s) => byId.get(s.id)).filter(Boolean);
    if (story.length < 2) {
      const chain = [];
      let cur = data.champion && byId.get(data.champion.id);
      while (cur) {
        chain.push(cur);
        cur = (cur.parent_a && byId.get(cur.parent_a)) || (cur.parent_b && byId.get(cur.parent_b));
      }
      story = chain.reverse();
    }
    const storyIds = new Set(story.map((n) => n.id));
    const lineageIds = new Set(story.map((n) => n.id));
    const champion = data.champion && byId.get(data.champion.id);
    const control = data.control || {};

    // Primary-parent cladogram. A node's vertical position is the mean of its
    // children; leaves are spread across the field. This keeps ancestry stable
    // instead of letting every generation re-order itself.
    const childrenMap = new Map();
    const roots = [];
    for (const n of nodes) {
      const pa = n.parent_a && byId.get(n.parent_a) ? byId.get(n.parent_a) : null;
      const pb = n.parent_b && byId.get(n.parent_b) ? byId.get(n.parent_b) : null;
      const parent = pa || pb;
      if (parent) {
        if (!childrenMap.has(parent.id)) childrenMap.set(parent.id, []);
        childrenMap.get(parent.id).push(n);
      } else {
        roots.push(n);
      }
    }
    const maxMemo = new Map();
    const subtreeMax = (n, seen = new Set()) => {
      if (maxMemo.has(n.id)) return maxMemo.get(n.id);
      if (seen.has(n.id)) return metric(n) ?? -1;
      seen.add(n.id);
      let best = metric(n) ?? -1;
      for (const c of childrenMap.get(n.id) || []) best = Math.max(best, subtreeMax(c, seen));
      maxMemo.set(n.id, best);
      return best;
    };
    for (const arr of childrenMap.values()) arr.sort((a, b) => subtreeMax(b) - subtreeMax(a));
    roots.sort((a, b) => subtreeMax(b) - subtreeMax(a));
    // Put the champion's root around the lower third so the story has room.
    let champRoot = null;
    if (data.champion && byId.get(data.champion.id)) {
      let cur = byId.get(data.champion.id);
      const seen = new Set();
      while (cur && !seen.has(cur.id)) {
        seen.add(cur.id);
        const parent = (cur.parent_a && byId.get(cur.parent_a)) || (cur.parent_b && byId.get(cur.parent_b));
        if (!parent) { champRoot = cur; break; }
        cur = parent;
      }
    }
    if (champRoot) {
      const idx = roots.indexOf(champRoot);
      if (idx >= 0) {
        roots.splice(idx, 1);
        roots.splice(Math.max(0, Math.floor(roots.length * 0.34)), 0, champRoot);
      }
    }
    let leafIndex = 0;
    const countLeaves = (n, seen = new Set()) => {
      if (seen.has(n.id)) return 1;
      seen.add(n.id);
      const kids = childrenMap.get(n.id) || [];
      if (!kids.length) return 1;
      return kids.reduce((sum, c) => sum + countLeaves(c, seen), 0);
    };
    const totalLeaves = Math.max(1, roots.reduce((sum, r) => sum + countLeaves(r), 0));
    const yForLeaf = (i) => top + ((i + 0.5) / totalLeaves) * (H - top - bottom);
    const placed = new Set();
    const walk = (n) => {
      if (placed.has(n.id)) return n._y ?? top;
      placed.add(n.id);
      const kids = (childrenMap.get(n.id) || []).filter((c) => !placed.has(c.id));
      if (!kids.length) {
        n._y = yForLeaf(leafIndex++);
      } else {
        const ys = kids.map(walk);
        n._y = ys.reduce((a, b) => a + b, 0) / Math.max(1, ys.length);
      }
      n._x = x(n.generation);
      return n._y;
    };
    for (const r of roots) walk(r);
    // Any unplaced nodes (cycles or missing parents) get a leaf slot.
    for (const n of nodes) {
      if (!placed.has(n.id)) {
        n._y = yForLeaf(leafIndex++);
        n._x = x(n.generation);
      }
    }
    const groups = d3.group(nodes, (d) => d.generation);
    const gens = Array.from(groups.keys()).sort((a, b) => a - b);

    // Curated sides: the two strongest siblings at each step of the trunk.
    const sideIds = new Set();
    const metricKey = (n) => [metric(n) ?? -1, metric(n, "top500") ?? -1];
    for (let i = 1; i < story.length; i++) {
      const p = story[i - 1];
      const c = story[i];
      const kids = (childrenMap.get(p.id) || []).filter((k) => k.id !== c.id && !lineageIds.has(k.id));
      kids.sort((a, b) => {
        const [a1, a2] = metricKey(a);
        const [b1, b2] = metricKey(b);
        return b1 - a1 || b2 - a2;
      });
      for (const k of kids.slice(0, 3)) sideIds.add(k.id);
    }
    const curatedIds = new Set([...lineageIds, ...sideIds]);

    // The champion lineage is the trunk. Pin it to a smooth spine and arrange
    // the rest of each generation above and below it. This keeps the gold path
    // readable while preserving the ancestry ordering from the cladogram.
    const champGen = data.champion ? Math.max(1, data.champion.generation) : Math.round(maxGen * 0.4);
    const spine = (g) => {
      const t = clamp(g / champGen, 0, 1);
      const ratio = 0.50 + 0.02 * Math.sin(t * Math.PI);
      return top + ratio * (H - top - bottom);
    };
    const gap = Math.max(10, (H - top - bottom) * 0.022);
    for (const g of gens) {
      const cy = spine(g);
      const arr = groups.get(g);
      const lineageHere = arr.filter((n) => storyIds.has(n.id));
      const sideHere = arr.filter((n) => sideIds.has(n.id));
      const above = [];
      const below = [];
      for (const n of arr) {
        if (storyIds.has(n.id) || sideIds.has(n.id)) continue;
        if ((n._y ?? cy) < cy) above.push(n);
        else below.push(n);
      }
      above.sort((a, b) => (a._y ?? 0) - (b._y ?? 0));
      below.sort((a, b) => (a._y ?? 0) - (b._y ?? 0));
      const topSpace = Math.max(8, cy - gap - top);
      const botSpace = Math.max(8, H - bottom - (cy + gap));
      above.forEach((n, i) => { n._y = top + ((i + 0.5) / Math.max(1, above.length)) * topSpace; });
      below.forEach((n, i) => { n._y = cy + gap + ((i + 0.5) / Math.max(1, below.length)) * botSpace; });
      lineageHere.forEach((n, i) => {
        n._y = cy + (i - (lineageHere.length - 1) / 2) * 5;
      });
      sideHere.forEach((n, i) => {
        const dir = i % 2 ? 1 : -1;
        n._y = clamp(cy + dir * (gap + 30 + Math.floor(i / 3) * 20), top + 8, H - bottom - 8);
      });
      for (const n of arr) n._x = x(n.generation);
    }

    // Give the curated sides visible sub-branches so the default reads as a tree.
    const addBranch = (root, depth, limit, base) => {
      if (!root) return;
      const kids = (childrenMap.get(root.id) || []).filter((k) => !curatedIds.has(k.id));
      kids.sort((a, b) => (metric(b) ?? -1) - (metric(a) ?? -1));
      kids.slice(0, limit).forEach((k, i) => {
        curatedIds.add(k.id);
        k._x = x(k.generation);
        k._y = clamp(root._y + (i % 2 ? 1 : -1) * (base + Math.floor(i / 2) * 16), top + 8, H - bottom - 8);
        if (depth > 0) addBranch(k, depth - 1, 1, Math.max(10, base * 0.55));
      });
    };
    for (const id of sideIds) addBranch(byId.get(id), 1, 2, 16);
    addBranch(champion, 1, 12, 30);

    // Primary and secondary edges. Primary parent = parent_a when possible.
    const primary = [];
    const secondary = [];
    for (const n of nodes) {
      const pa = n.parent_a && byId.get(n.parent_a) ? byId.get(n.parent_a) : null;
      const pb = n.parent_b && byId.get(n.parent_b) ? byId.get(n.parent_b) : null;
      const p = pa || pb;
      if (p) primary.push({ p, c: n });
      const other = p === pa ? pb : pa;
      if (other) secondary.push({ p: other, c: n });
    }

    const edgePath = (p, c) => {
      const px = Number.isFinite(p._x) ? p._x : x(p.generation || 0);
      const py = Number.isFinite(p._y) ? p._y : (top + bottom) / 2;
      const cx = Number.isFinite(c._x) ? c._x : x(c.generation || 0);
      const cy = Number.isFinite(c._y) ? c._y : (top + bottom) / 2;
      if (!Number.isFinite(px) || !Number.isFinite(cx)) return "";
      const dx = cx - px;
      const bend = Math.max(16, Math.abs(dx) * 0.42);
      return `M${px.toFixed(2)},${py.toFixed(2)}C${(px + bend).toFixed(2)},${py.toFixed(2)} ${(cx - bend).toFixed(2)},${cy.toFixed(2)} ${cx.toFixed(2)},${cy.toFixed(2)}`;
    };

    const familyOf = (n) => (state.meta.family_colors[n.family] ? n.family : "unknown");
    const primaryByFamily = new Map();
    for (const e of primary) {
      const f = familyOf(e.c);
      if (!primaryByFamily.has(f)) primaryByFamily.set(f, []);
      primaryByFamily.get(f).push(edgePath(e.p, e.c));
    }
    const secondaryPath = secondary.map((e) => edgePath(e.p, e.c)).join("");

    // One best descendant chain continues to the right: real ancestry, not a fan.
    const legacyChain = [];
    if (champion) {
      let cur = champion;
      const seen = new Set([champion.id]);
      while (cur) {
        const kids = (childrenMap.get(cur.id) || []).filter((k) => !seen.has(k.id));
        if (!kids.length) break;
        kids.sort((a, b) => (metric(b) ?? -1) - (metric(a) ?? -1));
        cur = kids[0];
        seen.add(cur.id);
        legacyChain.push(cur);
      }
    }
    let legacyPath = "";
    if (champion) {
      let prev = champion;
      for (const n of legacyChain) {
        legacyPath += edgePath(prev, n);
        prev = n;
      }
    }
    const legacyEnd = legacyChain.length ? legacyChain[legacyChain.length - 1] : champion;

    // Curated side branches: only the trunk + the two best siblings at each step.
    const curatedByFamily = new Map();
    for (const e of primary) {
      if (!curatedIds.has(e.c.id)) continue;
      const f = familyOf(e.c);
      if (!curatedByFamily.has(f)) curatedByFamily.set(f, []);
      curatedByFamily.get(f).push(edgePath(e.p, e.c));
    }

    // Focus: champion lineage + best genome per generation.
    const bestPerGen = [];
    for (const g of gens) {
      const arr = groups.get(g);
      let best = null;
      for (const n of arr) {
        if (!best || (metric(n) ?? -1) > (metric(best) ?? -1) || ((metric(n) ?? -1) === (metric(best) ?? -1) && (metric(n, "top500") ?? -1) > (metric(best, "top500") ?? -1))) best = n;
      }
      if (best) bestPerGen.push(best);
    }
    const focusIds = new Set([...lineageIds, ...bestPerGen.map((n) => n.id)]);
    if (champion) focusIds.add(champion.id);
    const focusByFamily = new Map();
    for (const e of primary) {
      if (!focusIds.has(e.c.id)) continue;
      const f = familyOf(e.c);
      if (!focusByFamily.has(f)) focusByFamily.set(f, []);
      focusByFamily.get(f).push(edgePath(e.p, e.c));
    }

    // Champion path: continuous curve through the lineage.
    let champPath = "";
    for (let i = 1; i < story.length; i++) {
      const p = story[i - 1];
      const c = story[i];
      champPath += edgePath(p, c);
    }
    const lineagePairs = new Set();
    for (let i = 1; i < story.length; i++) lineagePairs.add(`${story[i - 1].id}>${story[i].id}`);

    // Milestones.
    const seed = story[0];
    const firstGam = story.find((n) => n.model === "gam");
    const record = story.reduce((a, b) => ((metric(b) ?? -1) > (metric(a) ?? -1) ? b : a), story[0]);
    const milestones = [];
    if (seed) milestones.push({ n: seed, kicker: "SEED", title: seed.model, place: "below" });
    if (firstGam && firstGam.id !== seed?.id) milestones.push({ n: firstGam, kicker: "FIRST GAM", title: firstGam.model, place: "above" });
        if (champion) milestones.push({ n: champion, kicker: "CHAMPION", title: "the ascent", place: "above" });

    // C1 specimen at the right margin.
    const c1x = W - 96;
    const c1y = clamp((champion ? champion._y : H / 2) + 58, top + 40, H - bottom - 40);

    return {
      data, W, H, left, right, top, bottom, treeW, maxGen, x, genFromX, split,
      nodes, byId, groups, gens, primary, secondary, primaryByFamily, secondaryPath,
      story, lineageIds, champion, control, bestPerGen, focusIds, focusByFamily,
      sideIds, curatedIds, curatedByFamily, legacyChain, legacyPath, legacyEnd, champPath, lineagePairs, milestones, c1x, c1y,
    };
  }

  /* ------------------------------------------------------------------ */
  /* render                                                             */
  /* ------------------------------------------------------------------ */

  function render() {
    const p = prepare();
    state.prepared = p;
    state.reveal = clamp(state.reveal, 0, p.maxGen);

    const data = p.data;
    els.railTitle.innerHTML = VIEWS[state.view].title;
    els.railLede.textContent = VIEWS[state.view].lede;
    els.canvasKicker.textContent = VIEWS[state.view].kicker;
    els.canvasStats.textContent = VIEWS[state.view].stats;
    renderFigures();
    renderLegend();
    renderTimeline(p);
    updateViewNav();

    const svg = d3.select(els.svg);
    svg.selectAll("*").remove();
    svg.attr("viewBox", `0 0 ${p.W} ${p.H}`).attr("width", p.W).attr("height", p.H);
    addDefs(svg, p);

    const scene = svg.append("g").attr("class", "scene" + (state.animateNext ? " scene-in" : ""));
    state.animateNext = false;

    const zoom = d3.zoom().scaleExtent([0.65, 9]).on("zoom", (event) => {
      state.transform = event.transform;
      scene.attr("transform", event.transform);
    });
    state.zoom = zoom;
    state.svg = svg;
    svg.call(zoom).on("click", (event) => {
      if (event.target === svg.node()) {
        state.selected = null;
        renderDossier();
        render();
      }
    });

    const clipId = "revealClip";
    const clip = svg.select("defs").append("clipPath").attr("id", clipId);
    const clipRect = clip.append("rect").attr("x", 0).attr("y", 0).attr("height", p.H).attr("width", p.x(state.reveal));
    state.clipRect = clipRect;

    drawGrid(scene, p);
    const population = scene.append("g").attr("clip-path", `url(#${clipId})`);
    drawPopulation(population, p);
    const nodesLayer = scene.append("g").attr("clip-path", `url(#${clipId})`);
    drawNodes(nodesLayer, p);
    const mileLayer = scene.append("g").attr("clip-path", `url(#${clipId})`);
    drawMilestones(mileLayer, p);
    drawC1(scene, p);
    drawAxis(scene, p);

    if (state.selected) drawSelection(scene, p, state.selected);
    applySelectionClasses(p);

    if (state.transform) {
      scene.attr("transform", state.transform);
      svg.call(zoom.transform, state.transform);
    } else {
      scene.attr("transform", null);
    }

    updateRevealVisuals();
    renderDossier();
    renderSearch();
    els.canvasCorner.textContent = "Drag to pan · scroll to zoom · click a specimen";
    els.timeLabel.textContent = timeLabel(p);
  }

  function addDefs(svg, p) {
    const defs = svg.append("defs");
    defs.append("filter").attr("id", "blurSoft").attr("x", "-20%").attr("y", "-40%").attr("width", "140%").attr("height", "180%")
      .html('<feGaussianBlur stdDeviation="3.4"/>');
    defs.append("filter").attr("id", "glowGold").attr("x", "-200%").attr("y", "-200%").attr("width", "500%").attr("height", "500%")
      .html('<feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>');
    const grad = defs.append("linearGradient").attr("id", "champGradient").attr("x1", "0%").attr("x2", "100%").attr("y1", "0%").attr("y2", "0%");
    grad.append("stop").attr("offset", "0%").attr("stop-color", "#f0d39a").attr("stop-opacity", 0.75);
    grad.append("stop").attr("offset", "60%").attr("stop-color", "#e8c477").attr("stop-opacity", 1);
    grad.append("stop").attr("offset", "100%").attr("stop-color", "#fff3d0").attr("stop-opacity", 1);
  }

  function drawGrid(scene, p) {
    const g = scene.append("g").attr("class", "grid");
    const ticks = axisTicks(p);
    for (const t of ticks) {
      const x = p.x(t);
      g.append("line").attr("class", "grid-line").attr("x1", x).attr("x2", x).attr("y1", 40).attr("y2", p.H - 24);
    }
    // horizontal guides
    for (let i = 1; i <= 4; i++) {
      const y = p.top + (i / 5) * (p.H - p.top - p.bottom);
      g.append("line").attr("class", "grid-line").attr("x1", p.left).attr("x2", p.left + p.treeW).attr("y1", y).attr("y2", y).attr("stroke-opacity", 0.12);
    }
    // Faint decade bands give the time field a quiet rhythm.
    for (let d = 0; d < p.maxGen; d += 20) {
      const x0 = p.x(d);
      const x1 = p.x(Math.min(p.maxGen, d + 20));
      g.append("rect").attr("x", x0).attr("y", 40).attr("width", Math.max(0, x1 - x0)).attr("height", p.H - 64)
        .attr("fill", "var(--bone)").attr("opacity", d % 40 === 0 ? 0.025 : 0.014);
    }
    if (p.W > 860) {
      const ghost = scene.append("g").attr("class", "ghost-stat");
      ghost.append("text").attr("x", p.W - p.right - 6).attr("y", 152).attr("text-anchor", "end").attr("class", "ghost-number").text(p.data.stats.nodes.toLocaleString());
      ghost.append("text").attr("x", p.W - p.right - 6).attr("y", 172).attr("text-anchor", "end").attr("class", "ghost-label").text("GENOMES IN THE FIELD");
    }
  }

  function drawPopulation(layer, p) {
    const g = layer.append("g").attr("class", "population");
    for (const [family, paths] of p.primaryByFamily) {
      if (state.hiddenFamilies.has(family)) continue;
      const color = familyColor(family);
      g.append("path")
        .attr("class", "population")
        .attr("d", paths.join(""))
        .attr("stroke", color)
        .attr("stroke-width", 0.7)
        .attr("stroke-opacity", state.mode === "full" ? 0.2 : 0.085);
    }
    if (p.secondaryPath && state.mode === "full") {
      g.append("path").attr("class", "secondary").attr("d", p.secondaryPath);
    }
    // Branches: curated = trunk + two best siblings at each step; full = best per generation.
    const branchMap = state.mode === "full" ? p.focusByFamily : p.curatedByFamily;
    const f = layer.append("g").attr("class", "focus");
    for (const [family, paths] of branchMap) {
      if (state.hiddenFamilies.has(family)) continue;
      const color = familyColor(family);
      f.append("path")
        .attr("class", "focus")
        .attr("d", paths.join(""))
        .attr("stroke", color)
        .attr("stroke-width", state.mode === "full" ? 1.0 : 1.15)
        .attr("stroke-opacity", state.mode === "full" ? 0.62 : 0.72);
    }
    // Champion path.
    const champG = layer.append("g").attr("class", "champion-group");
    if (p.champPath) {
      const under = champG.append("path").attr("class", "champion-under").attr("d", p.champPath);
      const core = champG.append("path").attr("class", "champion").attr("d", p.champPath).attr("stroke", "url(#champGradient)");
      state.championCore = core;
      state.championUnder = under;
    }
  }

  function drawNodes(layer, p) {
    const g = layer.append("g").attr("class", "nodes");
    const visible = p.nodes.filter((n) => !state.hiddenFamilies.has(n.family));
    const list = state.mode === "full" ? visible.filter((n) => p.focusIds.has(n.id)) : visible.filter((n) => p.curatedIds.has(n.id));
    const selection = state.selected ? lineageSet(p, state.selected.id) : null;

    const dust = g.append("g").attr("class", "dust");
    dust.selectAll("circle")
      .data(visible)
      .join("circle")
      .attr("cx", (d) => d._x)
      .attr("cy", (d) => d._y)
      .attr("r", state.mode === "full" ? 1.55 : 1.25)
      .attr("fill", (d) => familyColor(d.family))
      .attr("fill-opacity", state.mode === "full" ? 0.72 : 0.64);

    const focus = g.append("g").attr("class", "focus-nodes");
    const node = focus.selectAll("g")
      .data(list, (d) => d.id)
      .join("g")
      .attr("class", (d) => {
        let cls = "node";
        if (p.lineageIds.has(d.id)) cls += " lineage";
        if (d.id === p.champion?.id) cls += " champion";
        if (selection) cls += selection.has(d.id) ? " lineage-active" : " dim";
        return cls;
      })
      .attr("transform", (d) => `translate(${d._x},${d._y})`)
      .attr("tabindex", (d) => (p.focusIds.has(d.id) ? 0 : -1))
      .attr("role", "button")
      .attr("aria-label", (d) => `${d.model}, generation ${d.generation}, top-243 ${fmt(metric(d), 1)}`)
      .on("mouseenter", (event, d) => showTooltip(event, d, p))
      .on("mousemove", (event) => moveTooltip(event))
      .on("mouseleave", hideTooltip)
      .on("click", (event, d) => {
        event.stopPropagation();
        selectNode(d);
      })
      .on("keydown", (event, d) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectNode(d);
        }
      });

    // Halo only for champion.
    node.filter((d) => d.id === p.champion?.id).append("circle").attr("class", "halo").attr("r", 15);
    node.filter((d) => d.id === p.champion?.id).append("circle").attr("class", "core").attr("r", 7.4);
    node.filter((d) => d.id === p.champion?.id).append("circle").attr("r", 15).attr("fill", "transparent");

    // Rings for focus/lineage nodes.
    node.filter((d) => d.id !== p.champion?.id).append("circle")
      .attr("class", "ring")
      .attr("r", (d) => (p.lineageIds.has(d.id) ? 4.2 : 3.0))
      .attr("stroke", (d) => familyColor(d.family));

    return node;
  }

  function drawMilestones(layer, p) {
    const g = layer.append("g").attr("class", "milestones");
    for (const m of p.milestones) {
      const n = m.n;
      if (!n) continue;
      const above = m.place === "above";
      const dx = n._x > p.left + p.treeW * 0.55 ? -12 : 12;
      const dy = above ? -44 : 36;
      const anchor = dx < 0 ? "end" : "start";
      const x = n._x + dx;
      const y = n._y + dy;
      const mg = g.append("g").attr("class", "milestone").attr("transform", `translate(${x},${y})`);
      mg.append("line").attr("x1", -dx).attr("y1", -dy + (above ? 12 : -12)).attr("x2", 0).attr("y2", above ? 12 : -12);
      mg.append("text").attr("class", "m-kicker").attr("text-anchor", anchor).text(m.kicker);
      mg.append("text").attr("class", "m-title").attr("text-anchor", anchor).attr("y", 15).text(m.title === "the ascent" ? "GAM" : m.title);
    }
  }

  function drawC1(scene, p) {
    const g = scene.append("g").attr("class", "c1-group").attr("opacity", state.showC1 ? 1 : 0);
    state.c1Group = g;
    if (!p.control || !p.control.top243) return;
    const champX = p.champion?._x ?? p.left;
    const champY = p.champion?._y ?? p.H / 2;
    const c1x = p.c1x;
    const c1y = p.c1y;

    g.append("path")
      .attr("class", "c1-link")
      .attr("d", `M${champX},${champY} C${champX + 72},${champY} ${c1x - 72},${c1y} ${c1x},${c1y}`);

    g.append("circle").attr("class", "c1-halo").attr("cx", c1x).attr("cy", c1y).attr("r", 15);
    const node = g.append("g")
      .attr("class", "c1-node")
      .attr("transform", `translate(${c1x},${c1y})`)
      .attr("tabindex", 0)
      .attr("role", "button")
      .attr("aria-label", "C1 baseline")
      .on("click", (event) => { event.stopPropagation(); selectNode(p.control); })
      .on("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectNode(p.control); } });
    node.append("path").attr("d", "M0,-8 L8,0 L0,8 L-8,0Z").attr("class", "c1-mark");
    node.append("circle").attr("r", 16).attr("fill", "transparent");

    g.append("text").attr("class", "c1-label").attr("x", c1x).attr("y", c1y - 24).attr("text-anchor", "middle").text("C1");
    g.append("text").attr("class", "c1-kicker").attr("x", c1x).attr("y", c1y - 10).attr("text-anchor", "middle").text("BASELINE");
    g.append("text").attr("class", "c1-metric").attr("x", c1x).attr("y", c1y + 24).attr("text-anchor", "middle")
      .text(`${fmt(p.control.top243, 1)} · ${fmt(p.control.top500, 1)} · ${fmt(p.control.avg_precision, 3)}`);
  }

  function drawAxis(scene, p) {
    const g = scene.append("g").attr("class", "axis");
    const y = 38;
    g.append("line").attr("class", "axis-line").attr("x1", p.left).attr("x2", p.left + p.treeW).attr("y1", y).attr("y2", y);
    g.append("text").attr("class", "axis-caption").attr("x", p.left).attr("y", y - 14).text("GENERATION / TIME →");
    g.append("text").attr("class", "axis-note").attr("x", p.left + p.treeW).attr("y", y - 14).attr("text-anchor", "end").text("time axis compressed after gen 22");
    const ticks = axisTicks(p);
    for (const t of ticks) {
      const x = p.x(t);
      const major = t === 0 || t === p.maxGen || t % 20 === 0;
      g.append("line").attr("class", "axis-line").attr("x1", x).attr("x2", x).attr("y1", y).attr("y2", y + (major ? 7 : 4)).attr("stroke-opacity", major ? 0.22 : 0.1);
      g.append("text").attr("class", "axis-label" + (major ? " major" : "")).attr("x", x).attr("y", y - 6).attr("text-anchor", "middle").text(t);
    }
    // Champion generation marker.
    if (p.champion) {
      const cx = p.x(p.champion.generation);
      g.append("line").attr("class", "reveal-line").attr("x1", cx).attr("x2", cx).attr("y1", y + 2).attr("y2", p.H - 18);
      g.append("text").attr("class", "axis-label major").attr("x", cx).attr("y", y + 18).attr("text-anchor", "middle").text(String(p.champion.generation));
    }
  }

  function axisTicks(p) {
    const candidates = [0, 5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80];
    const out = candidates.filter((t) => t < p.maxGen);
    out.push(p.maxGen);
    return Array.from(new Set(out)).sort((a, b) => a - b);
  }

  function drawSelection(scene, p, node) {
    const byId = p.byId;
    const chain = [];
    let cur = byId.get(node.id) || (node.is_control ? null : null);
    while (cur) {
      chain.push(cur);
      cur = cur.parent_a && byId.get(cur.parent_a) ? byId.get(cur.parent_a) : cur.parent_b && byId.get(cur.parent_b) ? byId.get(cur.parent_b) : null;
    }
    chain.reverse();
    if (chain.length < 2) return;
    let d = "";
    for (let i = 1; i < chain.length; i++) {
      const a = chain[i - 1];
      const b = chain[i];
      const dx = b._x - a._x;
      d += `M${a._x},${a._y}C${a._x + dx * 0.45},${a._y} ${b._x - dx * 0.45},${b._y} ${b._x},${b._y}`;
    }
    scene.append("path").attr("class", "selection-line").attr("d", d);
  }

  function lineageSet(p, id) {
    const parent = new Map();
    const child = new Map();
    for (const e of p.primary) {
      if (!parent.has(e.c.id)) parent.set(e.c.id, []);
      parent.get(e.c.id).push(e.p.id);
      if (!child.has(e.p.id)) child.set(e.p.id, []);
      child.get(e.p.id).push(e.c.id);
    }
    const set = new Set([id]);
    const walk = (start, map) => {
      const stack = [start];
      while (stack.length) {
        const cur = stack.pop();
        for (const nxt of map.get(cur) || []) {
          if (!set.has(nxt)) {
            set.add(nxt);
            stack.push(nxt);
          }
        }
      }
    };
    walk(id, parent);
    walk(id, child);
    return set;
  }

  function applySelectionClasses(p) {
    const has = !!state.selected;
    d3.select(els.svg).classed("has-selection", has);
    $$(".node", els.svg).forEach((el) => el.classList.remove("dim"));
    if (!has) return;
    // Node classes are already set in drawNodes via selection; population dimming:
    const pop = d3.select(els.svg).selectAll(".population");
    pop.attr("stroke-opacity", 0.012);
    d3.select(els.svg).selectAll(".focus").attr("stroke-opacity", 0.05);
  }

  /* ------------------------------------------------------------------ */
  /* reveal / timeline                                                  */
  /* ------------------------------------------------------------------ */

  function updateRevealVisuals() {
    const p = state.prepared;
    if (!p) return;
    const x = p.x(state.reveal);
    if (state.clipRect) state.clipRect.attr("width", Math.max(0, x));
    if (state.c1Group) state.c1Group.attr("opacity", state.showC1 && state.reveal >= p.maxGen - 0.01 ? 1 : 0);
    if (state.championCore) {
      // A subtle fade of the champion line as it is revealed.
      state.championCore.attr("opacity", state.reveal >= (p.champion?.generation ?? 0) ? 1 : 0.25);
    }
    renderTimelinePlayhead(p);
    els.timeLabel.textContent = timeLabel(p);
  }

  function timeLabel(p) {
    return `${Math.round(state.reveal)} / ${p.maxGen}`;
  }

  function renderTimeline(p) {
    els.timeRange.max = p.maxGen;
    els.timeRange.value = state.reveal;
    els.timeRange.style.display = "none"; // custom scrubber below
    // Build custom ticks.
    els.timelineTicks.innerHTML = "";
    for (const t of axisTicks(p)) {
      const span = document.createElement("span");
      const frac = (p.x(t) - p.left) / Math.max(1, p.treeW);
      const left = ((p.left / p.W) + frac * (p.treeW / p.W)) * 100;
      span.className = "tick" + (t % 20 === 0 || t === 0 || t === p.maxGen ? " major" : "");
      span.style.left = `${left}%`;
      els.timelineTicks.appendChild(span);
      if (t % 20 === 0 || t === 0 || t === p.maxGen) {
        const lab = document.createElement("span");
        lab.className = "tick-label";
        lab.style.left = `${left}%`;
        lab.textContent = t;
        els.timelineTicks.appendChild(lab);
      }
    }
    renderTimelinePlayhead(p);
  }

  function renderTimelinePlayhead(p) {
    if (!p) return;
    const track = $(".timeline-track");
    if (!track) return;
    let ph = track.querySelector(".playhead");
    if (!ph) {
      ph = document.createElement("div");
      ph.className = "playhead";
      track.appendChild(ph);
    }
    const frac = (p.x(state.reveal) - p.left) / Math.max(1, p.treeW);
    ph.style.left = `${clamp((p.left / p.W) + frac * (p.treeW / p.W), 0, 1) * 100}%`;
  }

  function bindScrubber() {
    const track = $(".timeline-track");
    if (!track) return;
    let dragging = false;
    const setFromEvent = (event) => {
      const p = state.prepared;
      if (!p) return;
      const rect = track.getBoundingClientRect();
      const f = clamp((event.clientX - rect.left) / rect.width, 0, 1);
      const chartX = p.left + f * p.W - p.left; // normalized chart coordinate
      // Convert the normalized track position to x in chart space.
      const x = p.left + f * p.W - p.left;
      // The mapping uses the full canvas width, but the tree is inset; use the
      // inverse of the same normalized mapping used for ticks.
      const treeFrac = (f - p.left / p.W) / (p.treeW / p.W);
      const gen = p.genFromX(p.left + clamp(treeFrac, 0, 1) * p.treeW);
      setReveal(gen);
    };
    track.addEventListener("pointerdown", (e) => { dragging = true; try { track.setPointerCapture?.(e.pointerId); } catch (_) {} setFromEvent(e); });
    track.addEventListener("pointermove", (e) => { if (dragging) setFromEvent(e); });
    window.addEventListener("pointerup", () => { dragging = false; });
    track.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        setReveal(state.reveal + (e.key === "ArrowRight" ? 1 : -1));
      }
    });
  }

  function setReveal(gen) {
    const p = state.prepared;
    if (!p) return;
    state.reveal = clamp(gen, 0, p.maxGen);
    if (state.playing) stopPlay();
    updateRevealVisuals();
  }

  /* ------------------------------------------------------------------ */
  /* interactions                                                       */
  /* ------------------------------------------------------------------ */

  function selectNode(d) {
    if (!d) return;
    state.selected = d;
    state.dossierOpen = true;
    document.body.classList.remove("dossier-closed");
    render();
    els.dossier.classList.remove("hidden");
    if (state.prepared) renderDossier();
  }

  function showTooltip(event, d, p) {
    const m = metric(d);
    els.tooltip.innerHTML = `<div class="tt-model">${esc(d.model)}</div>
      <div class="tt-meta">GEN ${fmt(d.generation, 0)} · ${esc(d.operation || "init")}</div>
      <div class="tt-row"><span>top-243</span><b>${fmt(m, 1)}</b></div>
      <div class="tt-row"><span>top-500</span><b>${fmt(metric(d, "top500"), 1)}</b></div>
      <div class="tt-row"><span>AP</span><b>${fmt(metric(d, "avg_precision"), 3)}</b></div>
      <div class="tt-meta">${esc((d.features || "").slice(0, 34))}</div>`;
    els.tooltip.classList.add("on");
    moveTooltip(event);
  }

  function moveTooltip(event) {
    const pad = 14;
    const w = els.tooltip.offsetWidth || 200;
    const h = els.tooltip.offsetHeight || 110;
    let x = event.clientX + pad;
    let y = event.clientY + pad;
    if (x + w > window.innerWidth - 8) x = event.clientX - w - pad;
    if (y + h > window.innerHeight - 8) y = event.clientY - h - pad;
    els.tooltip.style.left = `${Math.max(8, x)}px`;
    els.tooltip.style.top = `${Math.max(8, y)}px`;
  }

  function hideTooltip() { els.tooltip.classList.remove("on"); }

  function renderDossier() {
    const p = state.prepared;
    if (!p) return;
    const data = p.data;
    const node = state.selected || p.champion || p.control;
    if (!node) { els.dossier.innerHTML = '<p class="empty">No specimen selected.</p>'; return; }
    const isChamp = node.id === p.champion?.id || node.is_champion;
    const isC1 = node.is_control || node.id === p.control?.id;
    const model = node.model || "C1";
    const v243 = node.top243 ?? node.screen_top243;
    const v500 = node.top500 ?? node.screen_top500;
    const ap = node.avg_precision ?? node.screen_ap;
    const c1 = p.control || {};
    const d243 = v243 != null && c1.top243 != null ? v243 - c1.top243 : null;
    const d500 = v500 != null && c1.top500 != null ? v500 - c1.top500 : null;
    const dap = ap != null && c1.avg_precision != null ? ap - c1.avg_precision : null;
    const gate = state.meta.kpis.gate;
    const children = p.primary.filter((e) => e.p.id === node.id).length;
    const parents = [node.parent_a, node.parent_b].filter((x) => x && p.byId.get(x));

    els.dossier.innerHTML = `
      <button class="close" id="closeDossier" aria-label="Close dossier">×</button>
      <p class="d-kicker">${isC1 ? "Baseline specimen" : isChamp ? "Specimen 018 / champion" : "Specimen"}</p>
      <h2 class="d-model">${esc(isC1 ? "C1" : model)}</h2>
      <p class="d-sub">${esc(node.id || "control")}</p>
      <p class="d-features">${esc(node.features || "signals · assigner · text_tfidf")}</p>
      <div class="d-metrics">
        <div class="d-metric ${isChamp ? "gold" : isC1 ? "control" : ""}"><div class="n">${fmt(v243, 1)}</div><div class="l">top-243</div></div>
        <div class="d-metric"><div class="n">${fmt(v500, 1)}</div><div class="l">top-500</div></div>
        <div class="d-metric"><div class="n">${fmt(ap, 3)}</div><div class="l">AP</div></div>
      </div>
      ${!isC1 ? `<div class="d-block">
        <h4>vs C1 baseline</h4>
        <div class="d-row"><span>top-243</span><b class="${d243 >= 0 ? "pos" : "neg"}">${d243 == null ? "—" : `${d243 >= 0 ? "+" : ""}${fmt(d243, 1)}`}</b></div>
        <div class="d-row"><span>top-500</span><b class="${d500 >= 0 ? "pos" : "neg"}">${d500 == null ? "—" : `${d500 >= 0 ? "+" : ""}${fmt(d500, 1)}`}</b></div>
        <div class="d-row"><span>AP</span><b class="${dap >= 0 ? "pos" : "neg"}">${dap == null ? "—" : `${dap >= 0 ? "+" : ""}${fmt(dap, 3)}`}</b></div>
      </div>` : ""}
      <div class="d-block">
        <h4>Trial</h4>
        <div class="d-row"><span>generation</span><b>${fmt(node.generation, 0)}</b></div>
        <div class="d-row"><span>operation</span><b>${esc(node.operation || "—")}</b></div>
        <div class="d-row"><span>children</span><b>${children}</b></div>
        ${state.view === "arena" ? `<div class="d-row"><span>status</span><b>${node.alive === 1 ? "alive" : "eliminated"}</b></div>` : ""}
      </div>
      ${parents.length ? `<div class="d-block"><h4>Parents</h4><p class="parents">${parents.map((id) => `<button data-parent="${esc(id)}">${esc(id.slice(0, 12))}…</button>`).join(" · ")}</p></div>` : ""}
      ${isChamp ? `<div class="d-block"><h4>Five-seed gains vs C1</h4>
        <div class="d-row"><span>top-243</span><b class="pos">+${fmt(gate.top243_gain, 1)}</b></div>
        <div class="d-row"><span>top-500</span><b class="pos">+${fmt(gate.top500_gain, 1)}</b></div>
        <div class="d-row"><span>AP</span><b class="pos">+${fmt(gate.ap_gain, 3)}</b></div>
      </div>` : ""}
      <div class="d-actions"><button class="text-action" id="dossierLineage">Isolate lineage</button><button class="text-action" id="dossierCopy">Copy ID</button></div>
      <p class="d-note">${isC1 ? "C1 is the audited baseline, placed at the end of the field as a comparison branch." : "Gold is the champion lineage. Small rings are alternative branches; the field behind them is the full population. C1 is the baseline branch."}</p>`;

    $("#closeDossier")?.addEventListener("click", () => {
      state.dossierOpen = false;
      els.dossier.classList.add("hidden");
      document.body.classList.add("dossier-closed");
    });
    $$(".parents button", els.dossier).forEach((b) =>
      b.addEventListener("click", () => {
        const parent = p.byId.get(b.dataset.parent);
        if (parent) selectNode(parent);
      })
    );
    $("#dossierLineage")?.addEventListener("click", () => {
      state.selected = node;
      state.mode = "curated";
      state.hideOthers = true;
      render();
    });
    $("#dossierCopy")?.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(node.id); toast("ID copied"); } catch { toast(node.id); }
    });
  }

  /* ------------------------------------------------------------------ */
  /* rail / figures / legend                                            */
  /* ------------------------------------------------------------------ */

  function renderFigures() {
    const p = state.prepared;
    const data = state.data[state.view];
    const champ = data.champion || {};
    const c1 = data.control || {};
    const gate = state.meta.kpis.gate;
    let rows;
    if (state.view === "arena") {
      rows = [
        { v: data.stats.nodes.toLocaleString(), l: "genomes", n: "80 generations" },
        { v: data.stats.alive.toLocaleString(), l: "survivors", n: `${data.stats.eliminated.toLocaleString()} eliminated` },
        { v: fmt(champ.top243, 1), l: "champion top-243", n: `C1 ${fmt(c1.top243, 1)}`, cls: "gold" },
        { v: fmt(champ.top500, 1), l: "champion top-500", n: `C1 ${fmt(c1.top500, 1)}`, cls: "gold" },
        { v: fmt(champ.avg_precision, 3), l: "average precision", n: `C1 ${fmt(c1.avg_precision, 3)}`, cls: "gold" },
        { v: `+${fmt(gate.top243_gain, 1)} / +${fmt(gate.top500_gain, 1)}`, l: "five-seed gain", n: "vs C1", cls: "gold" },
      ];
    } else {
      rows = [
        { v: data.stats.nodes.toLocaleString(), l: "genomes", n: `${data.stats.generations} generations` },
        { v: "11", l: "model families", n: "5,371 evaluations" },
        { v: fmt(champ.top243, 1), l: "champion top-243", n: `C1 ${fmt(c1.top243, 1)}`, cls: "gold" },
        { v: fmt(champ.top500, 1), l: "champion top-500", n: `C1 ${fmt(c1.top500, 1)}`, cls: "gold" },
        { v: fmt(champ.avg_precision, 3), l: "average precision", n: `C1 ${fmt(c1.avg_precision, 3)}`, cls: "gold" },
        { v: `+${fmt(gate.top243_gain, 1)} / +${fmt(gate.top500_gain, 1)}`, l: "five-seed gain", n: "vs C1", cls: "gold" },
      ];
    }
    els.figureList.innerHTML = rows.map((r) => `<div class="figure ${r.cls || ""}"><div class="fig-main"><span class="fig-value">${r.v}</span><span class="fig-label">${r.l}</span></div><span class="fig-note">${r.n}</span></div>`).join("");
  }

  function renderLegend() {
    const data = state.data[state.view];
    const counts = new Map();
    for (const n of data.nodes) {
      if (n.is_control) continue;
      const f = state.meta.family_colors[n.family] ? n.family : "unknown";
      counts.set(f, (counts.get(f) || 0) + 1);
    }
    const rows = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
    els.familyLegend.innerHTML = rows.map(([f, c]) => `<div class="family-row ${state.hiddenFamilies.has(f) ? "off" : ""}" data-family="${esc(f)}">
      <span class="family-line" style="color:${state.meta.family_colors[f] || "#888"}"></span>
      <span class="family-name">${esc(f)}</span><span class="family-count">${c}</span></div>`).join("");
    $$(".family-row", els.familyLegend).forEach((row) =>
      row.addEventListener("click", () => {
        const f = row.dataset.family;
        if (state.hiddenFamilies.has(f)) state.hiddenFamilies.delete(f);
        else state.hiddenFamilies.add(f);
        render();
      })
    );
  }

  function updateViewNav() {
    $$(".view-btn", els.viewNav).forEach((b) => b.classList.toggle("active", b.dataset.view === state.view));
    $$("#modeToggle button").forEach((b) => b.classList.toggle("active", b.dataset.mode === state.mode));
    els.btnIsolate.setAttribute("aria-pressed", state.selected ? "true" : "false");
    els.btnC1.setAttribute("aria-pressed", state.showC1 ? "true" : "false");
    els.btnC1.textContent = state.showC1 ? "Shown at the end" : "Hidden";
  }

  /* ------------------------------------------------------------------ */
  /* events                                                             */
  /* ------------------------------------------------------------------ */

  function bind() {
    $$(".view-btn", els.viewNav).forEach((b) =>
      b.addEventListener("click", () => setView(b.dataset.view))
    );
    $$("#modeToggle button").forEach((b) =>
      b.addEventListener("click", () => {
        state.mode = b.dataset.mode;
        render();
      })
    );
    els.btnIsolate.addEventListener("click", () => {
      if (state.selected) {
        state.selected = null;
        render();
        toast("Showing full population");
      } else {
        state.selected = state.prepared?.champion || null;
        render();
        toast("Champion lineage isolated");
      }
    });
    els.btnC1.addEventListener("click", () => {
      state.showC1 = !state.showC1;
      render();
    });
    els.btnPlay.addEventListener("click", togglePlay);
    els.btnReset.addEventListener("click", resetView);
    $("#btnDossier").addEventListener("click", () => {
      state.dossierOpen = !state.dossierOpen;
      els.dossier.classList.toggle("hidden", !state.dossierOpen);
      document.body.classList.toggle("dossier-closed", !state.dossierOpen);
      state.transform = null;
      render();
    });
    els.familyLegend.addEventListener("click", () => {});
    $("#legendAll").addEventListener("click", () => { state.hiddenFamilies.clear(); render(); });
    els.search.addEventListener("input", debounce(() => { state.search = els.search.value.trim().toLowerCase(); renderSearch(); }, 100));
    bindScrubber();

    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => { state.transform = null; render(); }, 160);
    });

    document.addEventListener("keydown", (e) => {
      const tag = (e.target?.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea") {
        if (e.key === "Escape") e.target.blur();
        return;
      }
      if (e.key === "/") { e.preventDefault(); els.search.focus(); }
      else if (e.key === "0") { e.preventDefault(); resetView(); }
      else if (e.key === " ") { e.preventDefault(); togglePlay(); }
      else if (e.key.toLowerCase() === "l") { els.btnIsolate.click(); }
      else if (e.key === "Escape") { state.selected = null; render(); }
    });
  }

  function setView(view) {
    if (!state.data[view]) return;
    state.view = view;
    state.selected = null;
    state.mode = "curated";
    state.reveal = state.data[view].stats.generations;
    state.transform = null;
    state.animateNext = true;
    state.dossierOpen = true;
    document.body.classList.remove("dossier-closed");
    els.dossier.classList.remove("hidden");
    render();
    animateChampion();
  }

  function resetView() {
    state.transform = null;
    state.selected = null;
    state.reveal = state.prepared?.maxGen ?? 80;
    if (state.svg && state.zoom) state.svg.call(state.zoom.transform, d3.zoomIdentity);
    render();
    toast("View reset");
  }

  function togglePlay() {
    if (state.playing) { stopPlay(); return; }
    const p = state.prepared;
    if (!p) return;
    if (state.reveal >= p.maxGen - 0.01) {
      state.reveal = 0;
      updateRevealVisuals();
    }
    state.playing = true;
    els.playText.textContent = "Pause";
    els.btnPlay.querySelector(".play-glyph").textContent = "❚❚";
    const start = performance.now();
    const from = state.reveal;
    const duration = 7600;
    const tick = (now) => {
      if (!state.playing) return;
      const t = clamp((now - start) / duration, 0, 1);
      const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      state.reveal = from + (p.maxGen - from) * eased;
      updateRevealVisuals();
      if (t < 1) state.playRAF = requestAnimationFrame(tick);
      else stopPlay();
    };
    state.playRAF = requestAnimationFrame(tick);
  }

  function stopPlay() {
    state.playing = false;
    if (state.playRAF) cancelAnimationFrame(state.playRAF);
    state.playRAF = null;
    if (els.playText) els.playText.textContent = "Run generations";
    if (els.btnPlay) els.btnPlay.querySelector(".play-glyph").textContent = "▶";
    if (state.prepared) updateRevealVisuals();
  }

  function animateChampion() {
    if (!state.prepared) return;
    requestAnimationFrame(() => {
      const core = d3.select(els.svg).select(".champion");
      if (core.empty()) return;
      const el = core.node();
      const len = el.getTotalLength ? el.getTotalLength() : 0;
      if (!len) return;
      core.attr("stroke-dasharray", `${len} ${len}`).attr("stroke-dashoffset", len);
      core.transition().duration(2400).ease(d3.easeCubicOut).attr("stroke-dashoffset", 0).on("end", () => {
        core.attr("stroke-dasharray", null).attr("stroke-dashoffset", null);
      });
    });
  }

  function renderSearch() {
    const q = state.search;
    let count = 0;
    const p = state.prepared;
    if (!p) return;
    d3.select(els.svg).selectAll(".node").each(function (d) {
      const hit = q && `${d.model} ${d.features} ${d.operation} ${d.id}`.toLowerCase().includes(q);
      this.classList.toggle("search-hit", !!hit);
      if (hit) count++;
    });
    els.searchCount.textContent = q ? `${count}` : "";
  }

  function toast(msg) {
    els.toast.textContent = msg;
    els.toast.classList.add("on");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => els.toast.classList.remove("on"), 1600);
  }

  function debounce(fn, ms) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  document.addEventListener("DOMContentLoaded", () => {
    boot().catch((err) => {
      console.error(err);
      const svg = document.getElementById("braid");
      if (svg) svg.outerHTML = `<pre style="padding:30px;color:#d98b8b;font:12px/1.6 monospace">Could not load the braid: ${esc(err.stack || err.message || err)}\nRun python evolution/build_data.py and serve this folder over HTTP.</pre>`;
    });
  });
})();
