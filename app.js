(() => {
  'use strict';

  const MIN = 3;             // keyword/collaborator verschijnt als pill vanaf dit aantal
  const ACCENT = '#ffcd00';
  const TRACE = '#24a793';
  const RAIL_W = 380;
  const MOBILE = window.matchMedia('(max-width: 700px)');

  const PART = new Set(['van', 'von', 'de', 'der', 'den', 'del', 'della', 'dello', 'di', 'da', 'du',
    'dos', 'das', 'la', 'le', 'lo', 'ten', 'ter', 'te', "'t", 'op', 'bin', 'al', 'y', 'ibn']);

  const TYPE = {
    'Contribution to journal': 'Journal',
    'Chapter in Book/Report/Conference proceeding': 'Conference',
    'Contribution to conference': 'Conference',
    'Working paper': 'Preprint',
    'Book/Report': 'Report',
    'Thesis': 'Thesis',
  };

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  class App {
    constructor(pubs) {
      this.state = { q: '', kw: null, author: null, paperSel: null, mode: 'topics' };
      this.setup(pubs);
    }

    setup(pubs) {
      const all = pubs.map((p, i) => Object.assign({}, p, {
        _id: i,
        // De site levert pure_url; het ontwerp rekende op p.url.
        url: p.pure_url,
        link: p.doi
          ? (/^http/.test(p.doi) ? p.doi : 'https://doi.org/' + p.doi)
          : (p.pure_url || p.arxiv || '#'),
        _cat: TYPE[p.type] || 'Work',
      }));
      all.forEach(p => {
        p._search = [p.title, p.venue, p.authors.join(' '), p.year, (p.keywords || []).join(' ')]
          .join(' ').toLowerCase();
      });
      this.all = all;

      const kc = {}, kl = {};
      all.forEach(p => (p.keywords || []).forEach(k => {
        const low = k.toLowerCase();
        kc[low] = (kc[low] || 0) + 1;
        if (!kl[low] || k[0] === k[0].toUpperCase()) kl[low] = k;
      }));
      this.kwCounts = kc;
      this.kwLabels = kl;
      this.topKw = Object.entries(kc)
        .filter(([, n]) => n >= MIN)
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .map(e => e[0]);

      const ac = {};
      all.forEach(p => p.authors.forEach(a => {
        if (!/beerepoot/i.test(a)) ac[a] = (ac[a] || 0) + 1;
      }));
      this.authorCounts = ac;
    }

    surname(name) {
      const toks = String(name).trim().split(/\s+/).filter(Boolean);
      if (toks.length <= 1) return name;
      const isInit = t => /^[A-Za-z](\.[A-Za-z])*\.?$/.test(t)
        && t.replace(/\./g, '') === t.replace(/\./g, '').toUpperCase()
        && t.replace(/\./g, '').length <= 3;
      let start = -1;
      for (let i = 1; i < toks.length; i++) {
        if (PART.has(toks[i].toLowerCase())) { start = i; break; }
      }
      let parts;
      if (start > 0) parts = toks.slice(start);
      else {
        let i = 1;
        while (i < toks.length && isInit(toks[i])) i++;
        parts = toks.slice(i);
        if (!parts.length) parts = toks.slice(-1);
      }
      parts = parts.map(t => PART.has(t.toLowerCase()) ? t.toLowerCase() : t);
      parts[0] = parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
      return parts.join(' ');
    }

    typeLabel(p) { return p._cat === 'Work' ? (p.type || 'Work') : p._cat; }

    setState(patch) { Object.assign(this.state, patch); this.render(); }

    setKw = k => this.setState({ kw: this.state.kw === k ? null : k, author: null });
    setAuthor = a => this.setState({ author: this.state.author === a ? null : a, kw: null });
    setPaper = id => this.setState({ paperSel: this.state.paperSel === id ? null : id });
    setMode = m => this.setState({ mode: m });
    onSearch = e => this.setState({ q: e.target.value.trim().toLowerCase() });
    onReset = () => {
      const inp = document.getElementById('search');
      if (inp) inp.value = '';
      this.setState({ kw: null, author: null, q: '', paperSel: null });
    };

    active(p) {
      const { q, kw, author } = this.state;
      if (kw && !(p.keywords || []).some(k => k.toLowerCase() === kw)) return false;
      if (author && !p.authors.includes(author)) return false;
      if (q && !q.split(/\s+/).every(t => p._search.includes(t))) return false;
      return true;
    }

    filtered() { return this.all.filter(p => this.active(p)); }

    // ---------------- CANVAS MAP ----------------
    initMap(canvas) {
      const self = this;
      const ctx = canvas.getContext('2d');
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const PUBS = this.all, iris = 'Iris Beerepoot';
      const yrs = PUBS.map(p => p.year);
      let y0 = Math.min(...yrs), y1 = Math.max(...yrs);
      if (y0 === y1) y1 = y0 + 1;
      let W, H, ml = 150, mr = 150, mt = 34, mb = 46, curVW = 0, curVH = 0;
      let nodeList = null;
      const nYears = y1 - y0 + 1, cardW = 152, yearGap = 196;

      const neededH = vh => {
        if (!nodeList) return vh;
        const colH = {};
        nodeList.forEach(n => { colH[n.year] = (colH[n.year] || 0) + n.h + 9; });
        const tallest = Math.max(0, ...Object.values(colH));
        return Math.max(vh, tallest + mt + mb + 16);
      };
      const resize = () => {
        const par = canvas.parentElement;
        curVW = (par ? par.clientWidth : canvas.clientWidth) || 800;
        curVH = (par ? par.clientHeight : canvas.clientHeight) || 520;
        H = neededH(curVH);
        W = Math.max(curVW, nYears * yearGap + ml + mr);
        canvas.style.width = W + 'px';
        canvas.style.height = H + 'px';
        canvas.width = W * dpr;
        canvas.height = H * dpr;
      };
      resize();
      canvas.style.cursor = 'default';

      const xFor = yr => ml + (yr - y0) / (y1 - y0) * (W - ml - mr);
      const centerY = () => (mt + H - mb) / 2;

      const wrap = n => {
        ctx.font = "500 11.5px 'Space Grotesk',sans-serif";
        const maxW = cardW - 22, words = String(n.p.title).split(/\s+/), lines = [];
        let cur = '';
        for (let i = 0; i < words.length; i++) {
          const t = cur ? cur + ' ' + words[i] : words[i];
          if (ctx.measureText(t).width <= maxW || !cur) cur = t;
          else { lines.push(cur); cur = words[i]; if (lines.length === 2) break; }
        }
        if (cur && lines.length < 2) lines.push(cur);
        if (lines.length > 2) lines.length = 2;
        const shown = lines.join(' ').split(/\s+/).length;
        if (shown < words.length) {
          let li = lines.length - 1;
          while (lines[li] && ctx.measureText(lines[li] + '…').width > maxW) {
            lines[li] = lines[li].replace(/\s*\S+$/, '');
          }
          lines[li] = (lines[li] || '') + '…';
        }
        n._lines = lines.length ? lines : [String(n.p.title)];
        n.w = cardW;
        n.h = 13 + n._lines.length * 15;
      };

      const nodes = PUBS.map((p, i) => ({
        id: i, p, year: p.year, x0: xFor(p.year), x: xFor(p.year),
        y: centerY() + (Math.random() - 0.5) * 300, vy: 0, appear: 0,
      }));
      nodes.forEach(wrap);
      nodeList = nodes;
      resize();

      const nodeById = {};
      nodes.forEach(n => nodeById[n.id] = n);

      const chron = (p, q) => p.year - q.year || p.id - q.id;

      // De structuur van de kaart: papers die een onderwerp delen, op volgorde van
      // jaar aan elkaar geregen. Een kliek (elk paar dat een keyword deelt) zou
      // 387 lijnen geven; deze ketens 57. Papers delen vaak meer dan een keyword,
      // dus paren worden samengevoegd -- elke lijn onthoudt welke keywords hem
      // opleveren, zodat een geselecteerd topic zijn eigen lijnen kan oplichten.
      const byKw = {};
      nodes.forEach(n => (n.p.keywords || []).forEach(k => {
        const low = k.toLowerCase();
        (byKw[low] = byKw[low] || []).push(n);
      }));
      const pairKey = (i, j) => i < j ? i + '-' + j : j + '-' + i;
      const topicMap = new Map();
      Object.keys(byKw).forEach(k => {
        const seq = byKw[k].slice().sort(chron);
        if (seq.length < 2) return;
        for (let i = 0; i < seq.length - 1; i++) {
          const a = seq[i], b = seq[i + 1], key = pairKey(a.id, b.id);
          let e = topicMap.get(key);
          if (!e) { e = { a, b, kws: new Set() }; topicMap.set(key, e); }
          e.kws.add(k);
        }
      });
      const topicEdges = [...topicMap.values()];
      const topicEdgesOf = n => topicEdges.filter(e => e.a === n || e.b === n);

      // Co-auteurketens liggen er niet standaard in; ze verschijnen als je een
      // collaborator kiest.
      const byAuthor = {};
      nodes.forEach(n => n.p.authors.forEach(a => {
        if (a !== iris) (byAuthor[a] = byAuthor[a] || []).push(n);
      }));
      const recurring = Object.keys(byAuthor).filter(a => byAuthor[a].length >= 2);
      const authorEdges = [];
      recurring.forEach(a => {
        const seq = byAuthor[a].slice().sort(chron);
        for (let i = 0; i < seq.length - 1; i++) authorEdges.push({ a: seq[i], b: seq[i + 1], author: a });
      });

      let alpha = 1, running = false, raf = 0, progress = 0;
      let hovered = null, dragNode = null, dragMoved = false, dragStart = null;
      const reheat = a => {
        alpha = Math.max(alpha, a || 0.5);
        if (!running) { running = true; loop(); }
      };

      const colMap = {};
      nodes.forEach(n => (colMap[n.year] = colMap[n.year] || []).push(n));
      const columns = Object.values(colMap);

      // Harde non-overlap: binnen elke jaarkolom een minimale verticale tussenruimte.
      const resolveColumns = () => {
        const top = mt, bot = H - mb;
        columns.forEach(list => {
          if (list.length < 2) {
            const n = list[0];
            if (n) n.y = Math.max(top + n.h / 2, Math.min(bot - n.h / 2, n.y));
            return;
          }
          list.sort((a, b) => a.y - b.y);
          for (let i = 1; i < list.length; i++) {
            const a = list[i - 1], b = list[i];
            const minGap = (a.h + b.h) / 2 + 7, d = b.y - a.y;
            if (d < minGap) {
              const push = (minGap - d) / 2;
              if (a !== dragNode) a.y -= push;
              if (b !== dragNode) b.y += push;
            }
          }
          const first = list[0], last = list[list.length - 1];
          if (first.y - first.h / 2 < top) {
            const dy = top - (first.y - first.h / 2);
            list.forEach(n => { if (n !== dragNode) n.y += dy; });
          }
          if (last.y + last.h / 2 > bot) {
            const dy = (last.y + last.h / 2) - bot;
            const avail = bot - top, needed = list.reduce((s, n) => s + n.h, 0) + (list.length - 1) * 7;
            if (needed <= avail) list.forEach(n => { if (n !== dragNode) n.y -= dy; });
            else {
              let yy = top;
              list.forEach(n => {
                n.y = yy + n.h / 2;
                yy += n.h + (avail - list.reduce((s, m) => s + m.h, 0)) / (list.length - 1);
              });
            }
          }
        });
      };

      const step = () => {
        if (alpha < 0.02) return;
        const cy = centerY();
        for (let i = 0; i < nodes.length; i++) {
          const a = nodes[i];
          for (let j = i + 1; j < nodes.length; j++) {
            const b = nodes[j];
            const dx = a.x - b.x;
            let dy = a.y - b.y;
            if (Math.abs(dy) < 0.01) dy = (Math.random() - 0.5);
            const overlapX = Math.abs(dx) < cardW * 0.92;
            const d2 = dx * dx + dy * dy;
            const f = (overlapX ? 3400 : 900) / d2;
            const fy = (dy / Math.sqrt(d2)) * f;
            a.vy += fy * alpha;
            b.vy -= fy * alpha;
          }
        }
        // Papers over hetzelfde onderwerp trekken naar elkaar toe.
        topicEdges.forEach(e => {
          const d = e.b.y - e.a.y;
          e.a.vy += d * 0.016 * alpha;
          e.b.vy -= d * 0.016 * alpha;
        });
        nodes.forEach(n => {
          n.vy += (cy - n.y) * 0.0016 * alpha;
          n.vy *= 0.86;
          n.vy = Math.max(-30, Math.min(30, n.vy));
          const half = n.h / 2;
          n.x += (n.x0 - n.x) * 0.2;
          if (n !== dragNode) n.y += n.vy;
          n.y = Math.max(mt + half, Math.min(H - mb - half, n.y));
        });
        resolveColumns();
        alpha *= 0.987;
      };

      const bez = (a, b) => {
        const mx = (a.x + b.x) / 2;
        ctx.moveTo(a.x, a.y);
        ctx.bezierCurveTo(mx, a.y, mx, b.y, b.x, b.y);
      };
      const rr = (x, y, w, h, r) => {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.arcTo(x + w, y, x + w, y + h, r);
        ctx.arcTo(x + w, y + h, x, y + h, r);
        ctx.arcTo(x, y + h, x, y, r);
        ctx.arcTo(x, y, x + w, y, r);
        ctx.closePath();
      };

      const draw = () => {
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, W, H);
        const st = self.state, author = st.author, kw = st.kw, q = st.q;
        // De sweep loopt een fractie voorbij het laatste jaar. Stopt hij precies op
        // y1, dan blijft dat jaar op appear 0.79 hangen en staat het permanent
        // gedimd t.o.v. de rest.
        const thr = y0 + progress * (y1 - y0 + 0.7);
        nodes.forEach(n => { n.appear = Math.max(0, Math.min(1, (thr - n.year + 0.55) / 0.7)); });

        for (let y = y0; y <= y1; y++) {
          const x = xFor(y), litY = y <= thr + 0.5;
          ctx.strokeStyle = 'rgba(255,255,255,0.06)';
          ctx.lineWidth = 1;
          ctx.globalAlpha = litY ? 1 : 0.5;
          ctx.beginPath();
          ctx.moveTo(x, mt - 8);
          ctx.lineTo(x, H - mb + 4);
          ctx.stroke();
          ctx.fillStyle = litY ? '#7f838d' : '#4a4d55';
          ctx.font = "500 11px 'Space Grotesk',sans-serif";
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          ctx.fillText(y, x, H - mb + 11);
        }
        ctx.globalAlpha = 1;

        if (progress < 1) {
          const sx = xFor(thr);
          ctx.strokeStyle = 'rgba(255,205,0,0.55)';
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(sx, mt - 8);
          ctx.lineTo(sx, H - mb + 4);
          ctx.stroke();
        }

        const selNode = st.paperSel != null ? nodeById[st.paperSel] : null;
        // Een gekozen collaborator legt zijn keten over de kaart; anders licht de
        // hover de onderwerplijnen van dat paper op.
        const trace = author ? authorEdges.filter(e => e.author === author) : null;
        const focusEdges = trace
          || (hovered ? topicEdgesOf(hovered) : null)
          || (kw ? topicEdges.filter(e => e.kws.has(kw)) : null);
        const traceNodes = focusEdges ? new Set(focusEdges.flatMap(e => [e.a, e.b])) : null;
        if (hovered && traceNodes) traceNodes.add(hovered);
        let litNodes = null;
        if (author) litNodes = traceNodes;
        else if (kw || q) litNodes = new Set(nodes.filter(n => self.active(n.p)));
        else if (hovered) litNodes = traceNodes;

        topicEdges.forEach(e => {
          const ap = Math.min(e.a.appear, e.b.appear);
          if (ap <= 0.02) return;
          let a2, col, lw;
          if (trace) { col = '#8a90b8'; a2 = 0.04; lw = 1; }   // wijkt voor de keten
          else if (focusEdges) {
            const on = focusEdges.includes(e);
            if (on) { col = ACCENT; a2 = 0.9; lw = 2; }
            else { col = '#8a90b8'; a2 = 0.04; lw = 1; }
          } else if (litNodes) {
            const both = litNodes.has(e.a) && litNodes.has(e.b);
            col = '#8a90b8'; a2 = both ? 0.22 : 0.04; lw = 1;
          } else { col = '#8a90b8'; a2 = 0.13; lw = 1; }
          ctx.beginPath();
          bez(e.a, e.b);
          ctx.strokeStyle = col;
          ctx.globalAlpha = a2 * ap;
          ctx.lineWidth = lw;
          ctx.stroke();
        });

        if (trace) trace.forEach(e => {
          const ap = Math.min(e.a.appear, e.b.appear);
          if (ap <= 0.02) return;
          ctx.beginPath();
          bez(e.a, e.b);
          ctx.strokeStyle = TRACE;
          ctx.globalAlpha = 0.9 * ap;
          ctx.lineWidth = 2;
          ctx.stroke();
        });

        if (focusEdges) focusEdges.forEach(e => {
          const ap = Math.min(e.a.appear, e.b.appear);
          if (ap <= 0.4) return;
          self.drawArrow(ctx, e, author ? TRACE : ACCENT);
        });
        ctx.globalAlpha = 1;

        nodes.forEach(n => {
          if (n.appear <= 0.02) return;
          const sel = selNode === n;
          const lit = !litNodes || litNodes.has(n) || sel;
          const recede = litNodes && !lit;
          const traced = author && traceNodes && traceNodes.has(n);
          const emph = sel || (litNodes && lit) || n === hovered;
          const w = n.w, hh = n.h, x = n.x - w / 2, y = n.y - hh / 2;
          ctx.globalAlpha = (recede ? 0.14 : 1) * n.appear;
          const accent = traced ? TRACE : ACCENT;
          if (emph) { ctx.shadowColor = accent; ctx.shadowBlur = sel ? 20 : 12; }
          rr(x, y, w, hh, 9);
          ctx.fillStyle = emph ? '#181b24' : '#111319';
          ctx.fill();
          ctx.shadowBlur = 0;
          ctx.lineWidth = sel ? 1.8 : (emph ? 1.4 : 1);
          ctx.strokeStyle = emph ? accent : 'rgba(255,255,255,0.12)';
          ctx.stroke();
          ctx.fillStyle = recede ? '#6b6e77' : (emph ? '#ffffff' : '#c3c5cd');
          ctx.font = "500 11.5px 'Space Grotesk',sans-serif";
          ctx.textAlign = 'left';
          ctx.textBaseline = 'middle';
          const tx = x + 13, ty0 = n.y - (n._lines.length - 1) * 7.5;
          n._lines.forEach((ln, i) => ctx.fillText(ln, tx, ty0 + i * 15));
          ctx.globalAlpha = 1;
        });

        if (hovered) {
          self.drawTip(ctx, W,
            `${hovered.p.title}  ·  ${self.typeLabel(hovered.p)}, ${hovered.p.year}`,
            hovered.x, hovered.y - hovered.h / 2 - 12);
        }
        if (author) {
          ctx.fillStyle = TRACE;
          ctx.font = "600 12px 'Space Grotesk',sans-serif";
          ctx.textAlign = 'left';
          ctx.textBaseline = 'bottom';
          ctx.fillText('▶ tracing ' + self.surname(author), 16, H - mb - 10);
        }
      };

      const loop = () => {
        step();
        if (progress < 1) progress = Math.min(1, progress + 0.012);
        draw();
        if (progress < 1 || alpha >= 0.02) raf = requestAnimationFrame(loop);
        else running = false;
      };

      const pick = (px, py) => {
        for (let i = nodes.length - 1; i >= 0; i--) {
          const n = nodes[i];
          if (n.appear < 0.5) continue;
          if (Math.abs(px - n.x) < n.w / 2 + 2 && Math.abs(py - n.y) < n.h / 2 + 2) return n;
        }
        return null;
      };
      const rel = e => {
        const r = canvas.getBoundingClientRect();
        return { x: e.clientX - r.left, y: e.clientY - r.top };
      };

      canvas.addEventListener('mousemove', e => {
        if (dragNode) {
          const p = rel(e);
          if (!dragMoved && dragStart && Math.hypot(p.x - dragStart.x, p.y - dragStart.y) < 5) return;
          dragMoved = true;
          dragNode.y = p.y;
          dragNode.vy = 0;
          reheat(0.15);
          return;
        }
        const p = rel(e);
        const hh = pick(p.x, p.y);
        if (hh !== hovered) {
          hovered = hh;
          canvas.style.cursor = hh ? 'pointer' : 'default';
          if (!running) draw();
        }
      });
      canvas.addEventListener('mousedown', e => {
        const p = rel(e);
        const hh = pick(p.x, p.y);
        if (hh) { dragNode = hh; dragMoved = false; dragStart = p; }
      });
      window.addEventListener('mouseup', () => {
        if (dragNode && !dragMoved) self.setPaper(dragNode.id);
        dragNode = null;
      });
      canvas.addEventListener('mouseleave', () => {
        if (hovered && !dragNode) { hovered = null; draw(); }
      });
      canvas.addEventListener('click', e => {
        const p = rel(e);
        if (!pick(p.x, p.y) && self.state.paperSel != null) self.setState({ paperSel: null });
      });

      const remeasure = () => {
        const par = canvas.parentElement, vw = par ? par.clientWidth : 0, vh = par ? par.clientHeight : 0;
        if (vw === curVW && vh === curVH) return; // negeer padding-only changes (rail opent)
        resize();
        nodes.forEach(n => { n.x0 = xFor(n.year); });
        reheat(0.4);
      };
      window.addEventListener('resize', remeasure);
      if (window.ResizeObserver && canvas.parentElement) {
        const ro = new ResizeObserver(remeasure);
        ro.observe(canvas.parentElement);
      }
      requestAnimationFrame(remeasure);
      setTimeout(remeasure, 250);

      progress = 0; alpha = 1; running = true;
      loop();

      return {
        refresh() { if (!running) draw(); },
        reveal(id) {
          const n = nodeById[id], sc = canvas.parentElement;
          if (!n || !sc) return;
          const usable = Math.max(240, sc.clientWidth - RAIL_W);
          sc.scrollTo({ left: Math.max(0, n.x - usable / 2), behavior: 'smooth' });
        },
        resize() {
          const par = canvas.parentElement;
          const vw = par ? par.clientWidth : canvas.clientWidth;
          const vh = par ? par.clientHeight : canvas.clientHeight;
          if (vw === curVW && vh === curVH) { if (!running) draw(); return; }
          resize();
          nodes.forEach(n => { n.x0 = xFor(n.year); });
          reheat(0.3);
        },
      };
    }

    drawArrow(ctx, e, color) {
      const t = 0.6, a = e.a, b = e.b, mx = (a.x + b.x) / 2;
      const pt = tt => ({
        x: (1 - tt) ** 3 * a.x + 3 * (1 - tt) ** 2 * tt * mx + 3 * (1 - tt) * tt * tt * mx + tt ** 3 * b.x,
        y: (1 - tt) ** 3 * a.y + 3 * (1 - tt) ** 2 * tt * a.y + 3 * (1 - tt) * tt * tt * b.y + tt ** 3 * b.y,
      });
      const p0 = pt(t), p1 = pt(t + 0.02), ang = Math.atan2(p1.y - p0.y, p1.x - p0.x), s = 5.5;
      ctx.save();
      ctx.translate(p0.x, p0.y);
      ctx.rotate(ang);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.moveTo(s, 0);
      ctx.lineTo(-s * 0.7, s * 0.6);
      ctx.lineTo(-s * 0.7, -s * 0.6);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }

    drawTip(ctx, W, text, x, y) {
      const t = text.length > 60 ? text.slice(0, 58) + '…' : text;
      ctx.font = "500 12px 'Space Grotesk',sans-serif";
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const w = ctx.measureText(t).width;
      const rx = Math.max(w / 2 + 10, Math.min(W - w / 2 - 10, x));
      const bx = rx - w / 2 - 9, by = y - 11, bw = w + 18, bh = 22, r = 7;
      ctx.beginPath();
      ctx.moveTo(bx + r, by);
      ctx.arcTo(bx + bw, by, bx + bw, by + bh, r);
      ctx.arcTo(bx + bw, by + bh, bx, by + bh, r);
      ctx.arcTo(bx, by + bh, bx, by, r);
      ctx.arcTo(bx, by, bx + bw, by, r);
      ctx.closePath();
      ctx.fillStyle = 'rgba(18,20,26,0.97)';
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.14)';
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.fillStyle = '#e9eaee';
      ctx.fillText(t, rx, y);
    }

    // ---------------- CONTROLS ----------------
    pill(label, count, on, onClick) {
      const b = el('button', 'pill' + (on ? ' on' : ''));
      b.appendChild(document.createTextNode(label));
      if (count != null) b.appendChild(el('span', 'pill-n', count));
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.addEventListener('click', onClick);
      return b;
    }

    renderPills() {
      const host = document.getElementById('pills');
      host.textContent = '';
      let items;
      if (this.state.mode === 'collab') {
        items = Object.entries(this.authorCounts)
          .filter(([, n]) => n >= MIN)
          .sort((a, b) => b[1] - a[1] || this.surname(a[0]).localeCompare(this.surname(b[0])))
          .map(([a, n]) => this.pill(this.surname(a), n, this.state.author === a, () => this.setAuthor(a)));
      } else {
        items = this.topKw.map(k =>
          this.pill(this.kwLabels[k], this.kwCounts[k], this.state.kw === k, () => this.setKw(k)));
      }
      items.forEach(b => host.appendChild(b));
    }

    renderModeToggle() {
      const host = document.getElementById('mode');
      host.textContent = '';
      [['topics', 'Topics'], ['collab', 'Collaborators']].forEach(([m, label]) => {
        const b = el('button', 'mode-btn' + (this.state.mode === m ? ' on' : ''), label);
        b.setAttribute('aria-pressed', this.state.mode === m ? 'true' : 'false');
        b.addEventListener('click', () => this.setMode(m));
        host.appendChild(b);
      });
    }

    kwChip(k) {
      const low = k.toLowerCase(), on = this.state.kw === low;
      const b = el('button', 'chip' + (on ? ' on' : ''), k);
      b.addEventListener('click', () => this.setKw(low));
      return b;
    }

    // ---------------- DETAIL RAIL ----------------
    renderRail() {
      const host = document.getElementById('rail');
      host.textContent = '';
      const { paperSel } = this.state;
      if (paperSel == null) { host.hidden = true; return; }
      host.hidden = false;

      const p = this.all[paperSel];

      const head = el('div', 'rail-head');
      const headText = el('div', 'rail-head-text');
      headText.appendChild(el('div', 'rail-kicker', this.typeLabel(p) + ' · ' + p.year));
      headText.appendChild(el('div', 'rail-title', p.title));
      head.appendChild(headText);
      const close = el('button', 'rail-close', '×');
      close.setAttribute('aria-label', 'Close');
      close.addEventListener('click', () => this.setState({ paperSel: null }));
      head.appendChild(close);
      host.appendChild(head);

      host.appendChild(el('div', 'rail-label', 'Authors — click to trace'));
      const authors = el('div', 'rail-authors');
      p.authors.forEach((a, i) => {
        const isIris = /beerepoot/i.test(a);
        const on = this.state.author === a;
        const b = el('button', 'author' + (isIris ? ' me' : '') + (on ? ' on' : ''), a);
        if (isIris) b.disabled = true;
        else {
          b.title = 'Filter by ' + this.surname(a);
          b.addEventListener('click', () => this.setAuthor(a));
        }
        authors.appendChild(b);
        if (i < p.authors.length - 1) authors.appendChild(document.createTextNode(', '));
      });
      host.appendChild(authors);

      if (p.venue) {
        host.appendChild(el('div', 'rail-label', 'Published in'));
        host.appendChild(el('div', 'rail-venue', p.venue));
      }

      if ((p.keywords || []).length) {
        host.appendChild(el('div', 'rail-label', 'Topics'));
        const chips = el('div', 'rail-chips');
        p.keywords.forEach(k => chips.appendChild(this.kwChip(k)));
        host.appendChild(chips);
      }

      const links = [];
      if (p.link && p.link !== '#') links.push(['Read', p.link]);
      if (p.pdf) links.push(['PDF', p.pdf]);
      if (p.url && p.url !== p.link) links.push(['Pure', p.url]);
      if (links.length) {
        const row = el('div', 'rail-links');
        links.forEach(([lbl, href], i) => {
          const a = el('a', i === 0 ? 'btn primary' : 'btn', lbl);
          a.href = href;
          a.target = '_blank';
          a.rel = 'noopener';
          row.appendChild(a);
        });
        host.appendChild(row);
      }
    }

    // ---------------- TEXT LIST ----------------
    // Op mobiel is dit de site; op desktop staat het er voor screenreaders en indexering,
    // omdat een canvas voor beide onleesbaar is.
    renderList() {
      const host = document.getElementById('pub-list');
      const pubs = this.filtered();

      const count = document.getElementById('count');
      count.textContent = pubs.length === this.all.length
        ? `${this.all.length} publications`
        : `${pubs.length} of ${this.all.length} publications`;

      host.textContent = '';
      if (!pubs.length) {
        host.appendChild(el('p', 'empty', 'No matches.'));
        return;
      }

      const byYear = {};
      pubs.forEach(p => (byYear[p.year] ??= []).push(p));

      Object.keys(byYear).sort((a, b) => b - a).forEach(year => {
        host.appendChild(el('h3', 'year', year));
        const ul = el('ul', 'pubs');
        byYear[year].forEach(p => {
          const li = el('li');

          const title = el('div', 'title');
          const a = el('a', null, p.title);
          a.href = p.link;
          title.appendChild(a);
          li.appendChild(title);

          const meta = el('div', 'meta');
          meta.appendChild(document.createTextNode(p.authors.join(', ') + '. '));
          if (p.venue) meta.appendChild(el('em', null, p.venue + '. '));
          meta.appendChild(el('span', 'type', this.typeLabel(p)));
          li.appendChild(meta);

          if ((p.keywords || []).length) {
            const chips = el('div', 'list-chips');
            p.keywords.forEach(k => chips.appendChild(this.kwChip(k)));
            li.appendChild(chips);
          }

          ul.appendChild(li);
        });
        host.appendChild(ul);
      });
    }

    render() {
      this.renderModeToggle();
      this.renderPills();
      this.renderRail();
      this.renderList();

      // Was componentDidUpdate in het ontwerp.
      if (this.tryBind) this.tryBind();
      if (this._viz) this._viz.refresh();
      const sc = document.getElementById('graph-scroll');
      if (sc) sc.style.paddingRight = this.state.paperSel != null ? RAIL_W + 'px' : '0px';
      if (this._viz && this.state.paperSel != null && this._lastSel !== this.state.paperSel) {
        this._viz.reveal(this.state.paperSel);
      }
      this._lastSel = this.state.paperSel;
    }

    mount() {
      document.getElementById('search').addEventListener('input', this.onSearch);
      document.getElementById('reset').addEventListener('click', this.onReset);

      this.tryBind = () => {
        if (MOBILE.matches) return false;   // geen canvas op mobiel
        const c = document.getElementById('viz-map');
        if (!c || !c.parentElement || !c.parentElement.clientWidth) return false;
        if (this._viz && this._vizCanvas === c) { this._viz.resize(); return true; }
        this._vizCanvas = c;
        this._viz = this.initMap(c);
        return true;
      };

      this.render();

      const timer = setInterval(() => this.tryBind(), 200);
      setTimeout(() => clearInterval(timer), 4000);
      window.addEventListener('load', this.tryBind);
      requestAnimationFrame(this.tryBind);

      // Bij het passeren van de breakpoint moet de kaart alsnog opgebouwd worden.
      MOBILE.addEventListener('change', () => this.tryBind());
    }
  }

  fetch('publications.json')
    .then(r => r.json())
    .then(pubs => new App(pubs).mount())
    .catch(() => {
      document.getElementById('pub-list').textContent = 'Publication list unavailable.';
    });
})();
