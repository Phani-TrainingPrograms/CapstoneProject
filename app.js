/* Promotion Attribution - single-page UI. No build step; Plotly is served locally. */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const view = $("#view");
const state = { meta: null, promos: null, validation: null, proposals: null, selectedProposal: null, lastGate: null };

// ---------------------------------------------------------------- helpers
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" }, ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (_) { /* ignore */ }
    toast(`Request failed: ${msg}`);
    throw new Error(msg);
  }
  return res.json();
}
function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast"; t.textContent = msg;
  document.body.appendChild(t); setTimeout(() => t.remove(), 5000);
}
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const pct = (x, d = 1, sign = true) => x == null || isNaN(x) ? "–" : `${sign && x > 0 ? "+" : ""}${(x * 100).toFixed(d)}%`;
const num = (x, d = 0) => x == null || isNaN(x) ? "–" : Number(x).toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d });
const signed = (x, d = 0) => `${x > 0 ? "+" : ""}${num(x, d)}`;
function money(x) {
  if (x == null || isNaN(x)) return "–";
  const a = Math.abs(x), s = x < 0 ? "−" : "";
  if (a >= 1e6) return `${s}$${(a / 1e6).toFixed(2)}M`;
  if (a >= 1e3) return `${s}$${(a / 1e3).toFixed(1)}k`;
  return `${s}$${a.toFixed(0)}`;
}
const pp = (x) => `${x > 0 ? "+" : ""}${Number(x).toFixed(2)}pp`;
function verdictBadge(r) {
  if (r.status !== "ok") return `<span class="badge neutral">Refused</span>`;
  if (r.ci_low > 0) return `<span class="badge good">Significant uplift</span>`;
  if (r.ci_high < 0) return `<span class="badge bad">Significant decline</span>`;
  return `<span class="badge neutral">No measurable effect</span>`;
}
const okBadge = (ok, yes = "Pass", no = "Fail") => `<span class="badge ${ok ? "good" : "bad"}">${ok ? "✓ " + yes : "✕ " + no}</span>`;
const tile = (label, value, note = "", cls = "") =>
  `<div class="tile ${cls}"><div class="label">${label}</div><div class="value">${value}</div><div class="note">${note}</div></div>`;
const spinner = (txt = "Loading…") => `<div class="loading"><span class="spinner"></span> ${txt}</div>`;

function layout(extra = {}) {
  const axis = { gridcolor: css("--grid"), linecolor: css("--axis"), zerolinecolor: css("--axis"),
                 tickfont: { color: css("--muted"), size: 11 }, automargin: true, title: { font: { size: 12, color: css("--ink-2") } } };
  const base = {
    margin: { l: 10, r: 16, t: 8, b: 36 }, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: css("--font"), size: 12, color: css("--ink-2") }, showlegend: false,
    hoverlabel: { bgcolor: css("--surface"), bordercolor: css("--axis"), font: { color: css("--ink"), size: 12 } },
  };
  const out = { ...base, ...extra };
  out.xaxis = { ...axis, ...(extra.xaxis || {}) };
  out.yaxis = { ...axis, ...(extra.yaxis || {}) };
  return out;
}
const PCONF = { displayModeBar: false, responsive: true };
const plot = (el, traces, lay) => Plotly.newPlot(el, traces, layout(lay), PCONF);

function md(src) {
  if (!src) return "";
  const lines = src.replace(/\r/g, "").split("\n");
  const inline = (s) => esc(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
  let html = "", i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (l.startsWith("```")) {
      let code = []; i++;
      while (i < lines.length && !lines[i].startsWith("```")) code.push(lines[i++]);
      html += `<pre><code>${esc(code.join("\n"))}</code></pre>`; i++; continue;
    }
    const h = l.match(/^(#{1,4})\s+(.*)/);
    if (h) { html += `<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`; i++; continue; }
    if (l.startsWith("|")) {
      const rows = [];
      while (i < lines.length && lines[i].startsWith("|")) rows.push(lines[i++]);
      const cells = (r) => r.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const body = rows.slice(2).map((r) => `<tr>${cells(r).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("");
      html += `<div class="table-wrap"><table><thead><tr>${cells(rows[0]).map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table></div>`;
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(l)) {
      const ordered = /^\s*\d+\./.test(l); const items = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        let item = lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, "");
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*]|\d+\.)\s+/.test(lines[i])) item += " " + lines[i++].trim();
        items.push(`<li>${inline(item)}</li>`);
      }
      html += ordered ? `<ol>${items.join("")}</ol>` : `<ul>${items.join("")}</ul>`; continue;
    }
    if (l.startsWith(">")) {
      const q = [];
      while (i < lines.length && lines[i].startsWith(">")) q.push(lines[i++].replace(/^>\s?/, ""));
      html += `<blockquote>${inline(q.join(" "))}</blockquote>`; continue;
    }
    if (!l.trim()) { i++; continue; }
    const para = [];
    while (i < lines.length && lines[i].trim() && !/^(#|```|\||>|\s*([-*]|\d+\.)\s)/.test(lines[i])) para.push(lines[i++]);
    html += `<p>${inline(para.join(" "))}</p>`;
  }
  return html;
}

async function getPromos() { return state.promos ||= await api("/api/promotions"); }
async function getValidation() { return state.validation ||= await api("/api/validation"); }

// ---------------------------------------------------------------- shell
async function loadMeta() {
  state.meta = await api("/api/meta");
  const m = state.meta;
  $("#foot").innerHTML = `
    <div>Method <span class="mono">v${esc(m.method_version)}</span></div>
    <div>Config <span class="mono">${esc(m.config_hash)}</span></div>
    <div>Data <span class="mono">${esc(m.data_hash)}</span></div>
    <div class="muted" style="margin-top:4px">${m.n_stores} stores · ${m.n_skus} SKUs · ${m.weeks[0]} → ${m.weeks[1]}</div>
    <button class="theme-toggle" id="themeBtn" title="Toggle light/dark">◐ Theme</button>`;
  $("#themeBtn").onclick = () => {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("pa-theme", root.dataset.theme); } catch (_) { /* ignore */ }
    route();
  };
}
try { const t = localStorage.getItem("pa-theme"); if (t) document.documentElement.dataset.theme = t; } catch (_) { /* ignore */ }

const ROUTES = { portfolio: renderPortfolio, promo: renderPromo, ask: renderAsk, method: renderMethod, validation: renderValidation,
                 repro: renderRepro, gate: renderGate, data: renderData };
async function route() {
  const [, name = "portfolio", arg] = (location.hash || "#/portfolio").split("/");
  document.querySelectorAll(".nav a").forEach((a) => a.classList.toggle("active", a.dataset.route === name));
  view.innerHTML = spinner();
  window.scrollTo(0, 0);
  try { await (ROUTES[name] || renderPortfolio)(arg); }
  catch (e) { console.error(e); view.innerHTML = `<div class="callout bad">Something went wrong: ${esc(e.message)}</div>`; }
}
window.addEventListener("hashchange", route);

// ---------------------------------------------------------------- 1. portfolio
async function renderPortfolio() {
  const P = await getPromos();
  const ok = P.filter((p) => p.status === "ok");
  const up = ok.filter((p) => p.ci_low > 0), down = ok.filter((p) => p.ci_high < 0);
  const flat = ok.length - up.length - down.length;
  const incRev = ok.reduce((a, p) => a + p.incremental_revenue, 0);
  const roiPos = ok.filter((p) => p.roi > 0).length;
  view.innerHTML = `
    <div class="page-head"><div>
      <h1>Promotion portfolio</h1>
      <p>Every promotion measured the same way: a fixed baseline, matched control stores, and a 95% confidence interval.
      Click any row to see the counterfactual behind the number.</p></div>
      <span class="badge info big">Method v${esc(state.meta.method_version)}</span></div>
    <div class="grid g6">
      ${tile("Promotions measured", ok.length, `${P.length - ok.length} refused`)}
      ${tile("Significant uplift", up.length, "95% CI above zero")}
      ${tile("No measurable effect", flat, "CI includes zero")}
      ${tile("Significant decline", down.length, "CI below zero")}
      ${tile("Incremental revenue", money(incRev), "sum of point estimates")}
      ${tile("ROI-positive", `${roiPos}/${ok.length}`, "margin vs funding cost")}
    </div>
    <div class="card mt">
      <div class="card-head"><div><h2>Uplift with 95% confidence interval</h2>
        <p class="sub">The headline number is the dot; the whisker is how sure we are. Hollow markers show what a spreadsheet pre/post comparison would have reported.</p></div></div>
      <div class="legend-inline">
        <span><i class="sw line" style="background:var(--series-1)"></i>Method estimate · 95% CI</span>
        <span><i class="sw line" style="background:var(--muted)"></i>Not significant</span>
        <span><i class="sw" style="border:2px solid var(--muted);background:none;width:10px;height:10px;border-radius:50%"></i>Spreadsheet pre/post</span>
      </div>
      <div id="forest" class="chart tall"></div>
    </div>
    <div class="card mt">
      <h2>All promotions</h2><p class="sub">Uplift = actual ÷ counterfactual − 1 over the promotion weeks, treated stores, promoted SKUs.</p>
      <div class="table-wrap"><table>
        <thead><tr><th>Promotion</th><th>Mechanic</th><th>Weeks</th><th class="num">Uplift</th><th class="num">95% CI</th><th>Verdict</th>
          <th class="num">Incr. units</th><th class="num">Incr. revenue</th><th class="num">ROI</th><th class="num" title="What a pre/post spreadsheet would say">Spreadsheet</th></tr></thead>
        <tbody>${P.map((p) => `
          <tr class="click" onclick="location.hash='#/promo/${p.promo_id}'">
            <td><strong>${p.promo_id}</strong> <span class="ink2">${esc(p.promo_name)}</span></td>
            <td>${esc(p.mechanic)}${p.discount_pct ? ` <span class="muted">${Math.round(p.discount_pct * 100)}%</span>` : ""}</td>
            <td class="muted">${p.start_week} · ${p.duration_weeks}w</td>
            ${p.status === "ok" ? `
            <td class="num"><strong>${pct(p.uplift_pct)}</strong></td>
            <td class="num ink2">${pct(p.ci_low)} to ${pct(p.ci_high)}</td>
            <td>${verdictBadge(p)}</td>
            <td class="num">${signed(p.incremental_units)}</td>
            <td class="num">${money(p.incremental_revenue)}</td>
            <td class="num ${p.roi > 0 ? "pos" : "neg"}">${pct(p.roi, 0)}</td>
            <td class="num muted">${pct(p.naive_estimates.pre_post_no_control)}</td>` : `<td colspan="7" class="muted">Refused</td>`}
          </tr>`).join("")}</tbody></table></div>
    </div>`;
  const rows = [...ok].reverse();
  const y = rows.map((p) => `${p.promo_id} · ${p.promo_name}`);
  const sig = rows.map((p) => p.ci_low > 0 || p.ci_high < 0);
  plot("forest", [
    { type: "scatter", mode: "markers", x: rows.map((p) => p.naive_estimates.pre_post_no_control * 100), y,
      marker: { size: 9, symbol: "circle-open", color: css("--muted"), line: { width: 1.5 } }, name: "Spreadsheet pre/post",
      hovertemplate: "%{y}<br>Spreadsheet pre/post: %{x:+.1f}%<extra></extra>" },
    { type: "scatter", mode: "markers", x: rows.map((p) => p.uplift_pct * 100), y,
      error_x: { type: "data", symmetric: false, array: rows.map((p) => (p.ci_high - p.uplift_pct) * 100),
                 arrayminus: rows.map((p) => (p.uplift_pct - p.ci_low) * 100), color: css("--series-1"), thickness: 2, width: 0 },
      marker: { size: 11, color: sig.map((s) => s ? css("--series-1") : css("--muted")), line: { color: css("--surface"), width: 2 } },
      customdata: rows.map((p) => [pct(p.ci_low), pct(p.ci_high), p.verdict]),
      hovertemplate: "%{y}<br><b>Uplift %{x:+.1f}%</b><br>95% CI %{customdata[0]} to %{customdata[1]}<br>%{customdata[2]}<extra></extra>" },
  ], { xaxis: { ticksuffix: "%", zeroline: true, zerolinewidth: 1.5, title: { text: "Uplift vs counterfactual" } },
       yaxis: { gridcolor: "rgba(0,0,0,0)" }, margin: { l: 10, r: 16, t: 8, b: 44 } });
  document.getElementById("forest").on("plotly_click", (e) => { location.hash = `#/promo/${e.points[0].y.split(" · ")[0]}`; });
}

// ---------------------------------------------------------------- 2. promo deep-dive
function groupRuns(weeks, pred) {
  const runs = []; let s = null;
  weeks.forEach((w, i) => {
    if (pred(i)) { if (s === null) s = i; }
    else if (s !== null) { runs.push([s, i - 1]); s = null; }
  });
  if (s !== null) runs.push([s, weeks.length - 1]);
  return runs;
}

async function renderPromo(id) {
  const P = await getPromos();
  id = id || P[0].promo_id;
  const r = await api(`/api/promotions/${id}`);
  const opts = P.map((p) => `<option value="${p.promo_id}" ${p.promo_id === id ? "selected" : ""}>${p.promo_id} · ${esc(p.promo_name)}</option>`).join("");
  const head = `
    <div class="page-head"><div>
      <h1>${esc(r.promo_name)}</h1>
      <p><span class="pill">${r.promo_id}</span> &nbsp;${esc(r.mechanic)}${r.discount_pct ? ` · ${Math.round(r.discount_pct * 100)}% off` : ""} · ${esc(r.category)}
      · ${r.start_week} → ${r.end_week} (${r.duration_weeks} weeks) · ${r.treated_stores?.length ?? "–"} treated stores · owner ${esc(r.owner)}</p></div>
      <div class="row"><select id="promoSel">${opts}</select>${verdictBadge(r).replace("badge", "badge big")}</div></div>`;
  if (r.status !== "ok") {
    view.innerHTML = head + `<div class="callout bad">The method refused to attribute this promotion: ${esc(r.reason)}</div>`;
    $("#promoSel").onchange = (e) => (location.hash = `#/promo/${e.target.value}`);
    return;
  }
  const s = r.series;
  view.innerHTML = head + `
    <div class="grid g6">
      ${tile("Uplift", pct(r.uplift_pct), `95% CI ${pct(r.ci_low)} to ${pct(r.ci_high)}`, "hero")}
      ${tile("Incremental units", signed(r.incremental_units), `CI ${signed(r.incremental_units_low)} to ${signed(r.incremental_units_high)}`)}
      ${tile("Incremental revenue", money(r.incremental_revenue), `at avg promo price $${num(r.avg_promo_price, 2)}`)}
      ${tile("Promotion ROI", pct(r.roi, 0), `margin ${money(r.incremental_margin)} vs cost ${money(r.funding_cost)}`)}
      ${tile("p-value", r.p_value < 0.001 ? "< 0.001" : num(r.p_value, 3), r.significant ? "significant at 95%" : "not significant")}
      ${tile("Pre-period fit", pct(r.pre_period_mape, 1, false), "mean abs. error, baseline weeks")}
    </div>
    <div class="card mt">
      <div class="card-head"><div><h2>Actual vs counterfactual</h2>
        <p class="sub">The counterfactual is what the treated stores would have sold without the promotion, built from matched control stores scaled to the treated stores' baseline. The gap during the promo is the uplift.</p></div></div>
      <div class="legend-inline">
        <span><i class="sw line" style="background:var(--series-1)"></i>Actual (treated stores)</span>
        <span><i class="sw dash" style="border-color:var(--series-2)"></i>Counterfactual</span>
        <span><i class="sw" style="background:var(--series-2-band)"></i>95% CI of counterfactual</span>
        <span><i class="sw" style="background:var(--baseline-band);outline:1px solid var(--grid)"></i>Baseline weeks</span>
        <span><i class="sw" style="background:var(--excluded-band)"></i>Excluded from baseline</span>
        <span><i class="sw" style="background:var(--promo-band);outline:1px solid var(--grid)"></i>Promotion</span>
      </div>
      <div id="cfChart" class="chart tall"></div>
      <p class="sub" style="margin:8px 0 0">Over the promotion: actual <strong>${num(r.actual_units)}</strong> units vs counterfactual <strong>${num(r.counterfactual_units)}</strong> → ${signed(r.incremental_units)} incremental units.</p>
    </div>
    <div class="grid g2 mt">
      <div class="card"><h2>How sure are we?</h2><p class="sub">${num(r.bootstrap_draws.length)} of 1,000 bootstrap re-estimates (stores resampled). The shaded region is the 95% interval.</p>
        <div id="bootChart" class="chart short"></div></div>
      <div class="card"><h2>One promotion, three answers</h2><p class="sub">Why the method is code: the shortcuts people use in spreadsheets give very different numbers for the same promotion.</p>
        <div id="threeChart" class="chart short"></div></div>
    </div>
    <div class="grid g2 mt">
      <div class="card"><h2>Baseline definition applied</h2>
        <p class="sub">Selected by rule, not by analyst. See <a href="#/method">the method</a>, section 2.</p>
        <dl class="kv">
          <dt>Baseline weeks</dt><dd>${r.baseline_weeks.length} weeks, ${r.baseline_weeks[0]} → ${r.baseline_weeks[r.baseline_weeks.length - 1]}</dd>
          <dt>Excluded</dt><dd>${r.excluded_weeks.length ? r.excluded_weeks.map((e) => `<div><span class="pill">${e.week}</span> <span class="ink2">${esc(e.reason)}</span></div>`).join("") : "none"}</dd>
          <dt>Match window</dt><dd>${r.match_window[0]} → ${r.match_window[1]}</dd>
          <dt>Control strategy</dt><dd>${esc(r.control_strategy)} · ${r.control_stores.length} distinct control stores from ${r.control_candidates} untreated candidates</dd>
        </dl></div>
      <div class="card"><h2>Provenance</h2><p class="sub">Every number on this page can be regenerated exactly from these identifiers.</p>
        <dl class="kv">
          <dt>Method version</dt><dd><span class="pill">v${esc(r.method_version)}</span></dd>
          <dt>Config hash</dt><dd><span class="pill">${esc(r.config_hash)}</span></dd>
          <dt>Data hash</dt><dd><span class="pill">${esc(r.data_hash)}</span></dd>
          <dt>Confidence level</dt><dd>${Math.round(r.confidence_level * 100)}%</dd>
          <dt>Promoted SKUs</dt><dd>${r.sku_ids.map((k) => `<span class="pill">${k}</span>`).join(" ")}</dd>
        </dl></div>
    </div>
    <div class="card mt"><h2>Treated stores and their matched controls</h2>
      <p class="sub">Each treated store is compared with the untreated stores of the same format and region whose pre-period sales tracked it most closely (lower score = closer).</p>
      <div class="table-wrap"><table><thead><tr><th>Treated store</th><th>Format · region</th><th>Matched controls (score)</th><th>Match level</th>
        <th class="num">Actual</th><th class="num">Counterfactual</th><th class="num">Store uplift</th></tr></thead><tbody>
        ${r.pairs.map((p) => `<tr><td><strong>${p.treated.store_id}</strong> <span class="ink2">${esc(p.treated.store_name)}</span></td>
          <td class="ink2">${p.treated.format} · ${p.treated.region}</td>
          <td>${p.controls.map((c) => `<span class="pill" title="${esc(c.store_name)}">${c.store_id} ${c.match_score.toFixed(3)}</span>`).join(" ")}${p.n_controls > p.controls.length ? ` <span class="muted">+${p.n_controls - p.controls.length} more</span>` : ""}</td>
          <td>${p.fallback ? `<span class="badge bad">relaxed: ${esc(p.match_level)}</span>` : `<span class="badge neutral">${esc(p.match_level)}</span>`}</td>
          <td class="num">${num(p.actual_promo_units)}</td><td class="num">${num(p.counterfactual_promo_units)}</td>
          <td class="num"><strong>${pct(p.uplift_pct)}</strong></td></tr>`).join("")}
      </tbody></table></div></div>`;
  $("#promoSel").onchange = (e) => (location.hash = `#/promo/${e.target.value}`);

  // counterfactual chart
  const shapes = [];
  const band = (i0, i1, color) => shapes.push({ type: "rect", xref: "x", yref: "paper", x0: s.weeks[i0], x1: s.weeks[i1], y0: 0, y1: 1,
    fillcolor: color, line: { width: 0 }, layer: "below", xshift: 0 });
  // widen rects by half a week so single weeks are visible
  const half = (w, d) => { const t = new Date(w); t.setDate(t.getDate() + d); return t.toISOString().slice(0, 10); };
  groupRuns(s.weeks, (i) => s.role[i] === "baseline").forEach(([a, b]) => band(a, b, css("--baseline-band")));
  groupRuns(s.weeks, (i) => s.role[i] === "excluded").forEach(([a, b]) => band(a, b, css("--excluded-band")));
  groupRuns(s.weeks, (i) => s.role[i] === "promo").forEach(([a, b]) => band(a, b, css("--promo-band")));
  shapes.forEach((sh) => { sh.x0 = half(sh.x0, -3.5); sh.x1 = half(sh.x1, 3.5); });
  const annotations = [];
  const promoRun = groupRuns(s.weeks, (i) => s.role[i] === "promo")[0];
  if (promoRun) annotations.push({ x: s.weeks[Math.floor((promoRun[0] + promoRun[1]) / 2)], y: 1, yref: "paper", yanchor: "bottom", text: `<b>Promotion  ${pct(r.uplift_pct)}</b>`, showarrow: false, font: { color: css("--ink"), size: 12 } });
  const bRun = groupRuns(s.weeks, (i) => s.role[i] === "baseline");
  if (bRun.length) annotations.push({ x: s.weeks[bRun[bRun.length - 1][1]], xanchor: "right", y: 1, yref: "paper", yanchor: "bottom", text: "Baseline", showarrow: false, font: { color: css("--muted"), size: 11 } });
  s.weeks.forEach((w, i) => { if (s.holiday[i]) annotations.push({ x: w, y: 0, yref: "paper", yanchor: "bottom", text: "★", showarrow: false, font: { color: css("--muted"), size: 11 }, hovertext: "Holiday week" }); });
  const roleLabel = { baseline: "baseline week", excluded: "excluded from baseline", promo: "promotion week", "match-only": "match window", other: "" };
  plot("cfChart", [
    { x: s.weeks, y: s.band_high, mode: "lines", line: { width: 0 }, hoverinfo: "skip", connectgaps: false },
    { x: s.weeks, y: s.band_low, mode: "lines", line: { width: 0 }, fill: "tonexty", fillcolor: css("--series-2-band"), hoverinfo: "skip", connectgaps: false },
    { x: s.weeks, y: s.counterfactual, mode: "lines", name: "Counterfactual", line: { color: css("--series-2"), width: 2, dash: "dash" },
      hovertemplate: "Counterfactual %{y:,.0f}<extra></extra>" },
    { x: s.weeks, y: s.actual, mode: "lines+markers", name: "Actual", line: { color: css("--series-1"), width: 2 }, marker: { size: 4 },
      customdata: s.role.map((x) => roleLabel[x]), hovertemplate: "Actual %{y:,.0f}<br><span style='color:gray'>%{customdata}</span><extra></extra>" },
  ], { shapes, annotations, hovermode: "x unified", margin: { l: 10, r: 16, t: 24, b: 36 },
       yaxis: { title: { text: "Units / week (promoted SKUs, treated stores)" }, tickformat: ",.0f", rangemode: "tozero" }, xaxis: { type: "date" } });

  // bootstrap histogram
  const d = r.bootstrap_draws.map((x) => x * 100);
  plot("bootChart", [{ type: "histogram", x: d, marker: { color: css("--series-1"), line: { color: css("--surface"), width: 1 } }, nbinsx: 30,
    hovertemplate: "%{x}<br>%{y} draws<extra></extra>" }], {
    bargap: 0.04,
    shapes: [
      { type: "rect", xref: "x", yref: "paper", x0: r.ci_low * 100, x1: r.ci_high * 100, y0: 0, y1: 1, fillcolor: css("--baseline-band"), line: { width: 0 }, layer: "below" },
      { type: "line", xref: "x", yref: "paper", x0: 0, x1: 0, y0: 0, y1: 1, line: { color: css("--ink-2"), width: 1.5, dash: "dot" } },
    ],
    annotations: [{ x: 0, y: 1, yref: "paper", text: "zero", showarrow: false, yanchor: "bottom", font: { size: 11, color: css("--muted") } }],
    xaxis: { ticksuffix: "%", title: { text: "Bootstrap uplift estimate" } }, yaxis: { title: { text: "Draws" } }, margin: { l: 10, r: 16, t: 16, b: 40 } });

  // three answers
  const three = [
    ["Promoted vs unpromoted stores", r.naive_estimates.promoted_vs_unpromoted_stores],
    ["Pre/post, no control", r.naive_estimates.pre_post_no_control],
    ["This method (v" + r.method_version + ")", r.uplift_pct],
  ];
  plot("threeChart", [{ type: "bar", orientation: "h", y: three.map((t) => t[0]), x: three.map((t) => t[1] * 100),
    marker: { color: [css("--axis"), css("--axis"), css("--series-1")] }, text: three.map((t) => pct(t[1])), textposition: "outside",
    cliponaxis: false, textfont: { color: css("--ink") }, hovertemplate: "%{y}: %{x:+.1f}%<extra></extra>", width: 0.55 }],
    { xaxis: { ticksuffix: "%", zeroline: true }, yaxis: { gridcolor: "rgba(0,0,0,0)" }, margin: { l: 10, r: 50, t: 8, b: 36 } });
}

// ---------------------------------------------------------------- Ask
state.ask = { thread: [], context: null, busy: false };
const ASK_STARTERS = ["How did P09 perform?", "What about its ROI?", "Top 5 promotions by ROI in 2025",
  "Which mechanics work best on average?", "How is the confidence interval computed?", "How did the chocolate promotion do?",
  "Which promotions lost money?", "Did the method recover the planted effects?"];

function evVal(k, v) {
  if (v === null || v === undefined) return "–";
  if (typeof v === "number") {
    if (/pct|roi|^ci_|mape|coverage|share|rate|confidence_level|discount|spreadsheet|promoted_vs/.test(k)) return pct(v, 2);
    if (/revenue|margin|cost/.test(k)) return money(v);
    if (/price/.test(k)) return `$${v.toFixed(2)}`;
    return Number.isInteger(v) ? num(v) : num(v, 4);
  }
  if (Array.isArray(v)) return v.length > 6 ? `${v.slice(0, 6).map((x) => typeof x === "object" ? JSON.stringify(x) : x).join(", ")} … (${v.length})` : v.map((x) => typeof x === "object" ? JSON.stringify(x) : x).join(", ");
  if (typeof v === "object") return Object.entries(v).map(([a, b]) => `${a}: ${b}`).join(" · ");
  return String(v);
}

function renderTurn(t, i) {
  if (t.role === "user") return `<div class="msg-user">${esc(t.text)}</div>`;
  if (t.pending) return `<div class="msg-bot"><span class="typing"><span class="spinner"></span> Looking up the evidence…</span></div>`;
  const a = t.data, v = a.verification;
  const body = md(a.answer).replace(/\[(E\d+)\]/g, (_, id) => `<a class="cite" data-turn="${i}" data-ev="${id}" title="Show evidence ${id}">${id}</a>`);
  const evs = a.evidence.map((e) => {
    const text = e.data && typeof e.data.text === "string" ? `<div class="ev-text">${esc(e.data.text)}</div>` : "";
    const kv = Object.entries(e.data || {}).filter(([k]) => k !== "text")
      .map(([k, val]) => `<div><span>${esc(k)}</span><span>${esc(evVal(k, val))}</span></div>`).join("");
    return `<div class="ev-item" id="ev-${i}-${e.id}"><div class="ev-head"><span class="ev-id">${e.id}</span><strong>${esc(e.title)}</strong>
      <span class="ev-src">${esc(e.source)}</span></div>${kv ? `<div class="ev-kv">${kv}</div>` : ""}${text}</div>`;
  }).join("");
  const check = v.checked === 0 ? `<span class="badge neutral">no numbers to check</span>`
    : v.all_verified ? `<span class="badge good">✓ ${v.verified}/${v.checked} numbers verified against evidence</span>`
    : `<span class="badge bad">⚠ ${v.checked - v.verified} of ${v.checked} numbers not found in evidence</span>`;
  return `<div class="msg-bot"><div class="md">${body}</div>
    <div class="msg-foot">${check}<span class="pill">intent: ${esc(a.intent)}</span><span class="pill">method v${esc(a.method_version)}</span></div>
    ${a.evidence.length ? `<details id="evd-${i}"><summary>Evidence (${a.evidence.length})</summary>${evs}</details>` : ""}
    <details><summary>Trace</summary><ol class="trace">${a.trace.map((x) => `<li>${esc(x)}</li>`).join("")}</ol></details></div>`;
}

function drawThread() {
  const th = $("#thread");
  if (!th) return;
  const S = state.ask;
  th.innerHTML = S.thread.map(renderTurn).join("");
  const last = [...S.thread].reverse().find((t) => t.role === "bot" && t.data);
  $("#askChips").innerHTML = (last && !S.busy ? last.data.suggestions : (S.thread.length ? [] : ASK_STARTERS))
    .map((q) => `<button class="chip">${esc(q)}</button>`).join("");
  document.querySelectorAll("#askChips .chip").forEach((b) => b.onclick = () => askQuestion(b.textContent));
  th.querySelectorAll(".cite").forEach((c) => c.onclick = () => {
    const d = document.getElementById(`evd-${c.dataset.turn}`); if (d) d.open = true;
    const el = document.getElementById(`ev-${c.dataset.turn}-${c.dataset.ev}`);
    if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1600); }
  });
}

async function askQuestion(q) {
  const S = state.ask;
  q = (q || "").trim();
  if (!q || S.busy) return;
  S.busy = true;
  S.thread.push({ role: "user", text: q }, { role: "bot", pending: true });
  drawThread();
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  try {
    const a = await api("/api/ask", { method: "POST", body: { question: q, context: S.context } });
    S.thread[S.thread.length - 1] = { role: "bot", data: a };
    S.context = a.context;
  } catch (e) {
    S.thread.pop();
  } finally {
    S.busy = false;
    drawThread();
    const bots = document.querySelectorAll(".msg-bot");
    if (bots.length) bots[bots.length - 1].scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

async function renderAsk(arg) {
  view.innerHTML = `<div class="ask-wrap">
    <div class="page-head"><div><h1>Ask</h1>
      <p>Ask about a promotion, a ranking, or the method. Answers cite evidence <span class="cite">E#</span> from the attribution results,
      and every number is checked against that evidence before it is shown. No AI model is involved, so the same question always gets the same answer.</p></div>
      <button id="askClear" title="Start a new conversation">↺ New conversation</button></div>
    <div class="chips" id="askChips"></div>
    <div class="thread" id="thread"></div></div>
    <div class="ask-bar"><form id="askForm"><input id="askInput" autocomplete="off" placeholder="Ask about a promotion, a ranking, or the method…" maxlength="500">
      <button class="primary" type="submit" title="Send">↑ Ask</button></form></div>`;
  $("#askForm").onsubmit = (e) => { e.preventDefault(); const i = $("#askInput"); askQuestion(i.value); i.value = ""; };
  $("#askClear").onclick = () => { state.ask = { thread: [], context: null, busy: false }; drawThread(); $("#askInput").focus(); };
  drawThread();
  $("#askInput").focus();
  if (arg) {
    history.replaceState(null, "", "#/ask");
    for (const q of decodeURIComponent(arg).split("|")) await askQuestion(q);
  }
}

// ---------------------------------------------------------------- 3. method
async function renderMethod() {
  const m = await api("/api/method");
  const cov = m.coverage, t = m.tests, c = m.calibration;
  view.innerHTML = `
    <div class="page-head"><div><h1>The method</h1>
      <p>The baseline definition, control selection and uplift calculation are written in code, documented here and version-controlled.
      This page renders <code>METHOD.md</code>, <code>method_config.yaml</code> and <code>CHANGELOG.md</code> straight from the repository.</p></div>
      <span class="badge info big">v${esc(m.config.method_version)} · ${esc(m.config_hash)}</span></div>
    <div class="grid g4">
      ${tile("Baseline-definition coverage", cov ? `${cov.files["baseline.py"] ?? "–"}%` : "–", cov ? "line coverage of attribution/baseline.py" : "run the test suite to measure")}
      ${tile("Method code coverage", cov ? `${cov.total}%` : "–", "all of attribution/")}
      ${tile("Tests", t ? `${t.n_tests - t.n_failed}/${t.n_tests}` : "–", t ? (t.passed ? "all passing" : `${t.n_failed} failing`) : "not run yet")}
      ${tile("Stated tolerance", `±${m.config.validation.tolerance_pp}pp`, c ? `${(c.share_within_tolerance * 100).toFixed(1)}% of ${c.estimates} estimates within it` : "")}
    </div>
    <div class="row mt"><button class="primary" id="runTests">▶ Run test suite now</button><span class="muted" id="testMsg">Runs the same pytest + coverage command as CI (about 15–30 s).</span></div>
    <div class="grid g3 mt" style="grid-template-columns: minmax(0,1.6fr) minmax(0,1fr)">
      <div class="card md">${md(m.method_md)}</div>
      <div class="grid" style="align-content:start">
        <div class="card"><h2>method_config.yaml</h2><p class="sub">The method's settings. Changing any of them is a method change and must pass the gate.</p><pre class="yaml">${esc(m.config_yaml)}</pre></div>
        ${cov ? `<div class="card"><h2>Coverage by module</h2><table><tbody>${Object.entries(cov.files).map(([f, v]) => `<tr><td><code>${esc(f)}</code></td><td class="num">${v}%</td></tr>`).join("")}</tbody></table></div>` : ""}
        <div class="card md">${md(m.changelog_md)}</div>
      </div>
    </div>`;
  $("#runTests").onclick = async (e) => {
    e.target.disabled = true; $("#testMsg").innerHTML = `<span class="spinner"></span> Running pytest…`;
    try { const r = await api("/api/ci/run", { method: "POST" }); $("#testMsg").textContent = `${r.n_tests - r.n_failed}/${r.n_tests} passed in ${r.seconds}s`; setTimeout(route, 600); }
    finally { e.target.disabled = false; }
  };
}

// ---------------------------------------------------------------- 4. validation
async function renderValidation() {
  const [v, m] = await Promise.all([getValidation(), api("/api/method")]);
  const s = v.summary, c = m.calibration, tol = s.tolerance_pp;
  const nullRow = v.rows.find((r) => r.true_uplift_pct === 0);
  view.innerHTML = `
    <div class="page-head"><div><h1>Synthetic ground-truth validation</h1>
      <p>The data was generated with known, planted promotion effects, which are hidden from the method. The method is run blind, and passes only if it recovers every planted effect within <strong>±${tol} percentage points</strong>.</p></div>
      ${okBadge(s.passed, "Validation passed", "Validation failed").replace("badge", "badge big")}</div>
    <div class="grid g4">
      ${tile("Planted effects recovered", `${s.n_passed}/${s.n_promos}`, `within ±${tol}pp`, "hero")}
      ${tile("Largest error", `${s.max_abs_error_pp.toFixed(2)}pp`, `mean ${s.mean_abs_error_pp.toFixed(2)}pp · tolerance ${tol}pp`)}
      ${tile("CI coverage", `${Math.round(s.ci_coverage * 100)}%`, `intervals containing the truth (min ${Math.round(s.min_ci_coverage * 100)}%)`)}
      ${tile("Null promo", nullRow ? (nullRow.significant ? "✕ false positive" : "✓ not significant") : "–", nullRow ? `${nullRow.promo_id}: planted 0%, estimated ${pct(nullRow.estimated_uplift_pct, 2)}` : "")}
    </div>
    <div class="card mt"><h2>Planted vs recovered</h2>
      <p class="sub">Each row is one promotion. The diamond is the planted truth; the shaded bar is the ±${tol}pp tolerance around it; the dot and whisker are the method's estimate and 95% CI.</p>
      <div class="legend-inline">
        <span><i class="sw" style="background:var(--ink);width:9px;height:9px;transform:rotate(45deg)"></i>Planted effect (truth)</span>
        <span><i class="sw" style="background:var(--excluded-band)"></i>Tolerance ±${tol}pp</span>
        <span><i class="sw line" style="background:var(--series-1)"></i>Estimate · 95% CI</span>
      </div>
      <div id="recChart" class="chart tall"></div></div>
    <div class="card mt"><h2>Recovery detail</h2><div class="table-wrap"><table>
      <thead><tr><th>Promotion</th><th>Scenario</th><th class="num">Planted</th><th class="num">Estimated</th><th class="num">95% CI</th>
        <th class="num">Error</th><th>CI covers truth</th><th>Spreadsheet error</th><th>Result</th></tr></thead><tbody>
      ${v.rows.map((r) => `<tr><td><strong>${r.promo_id}</strong> <span class="ink2">${esc(r.promo_name)}</span></td>
        <td class="ink2">${esc(r.scenario || "")}</td><td class="num">${pct(r.true_uplift_pct)}</td>
        <td class="num"><strong>${pct(r.estimated_uplift_pct, 2)}</strong></td><td class="num ink2">${pct(r.ci_low)} to ${pct(r.ci_high)}</td>
        <td class="num">${pp(r.error_pp)}</td><td>${r.ci_covers_truth ? "✓" : "✕"}</td>
        <td class="num muted">${pp((r.naive_pre_post - r.true_uplift_pct) * 100)}</td>
        <td>${okBadge(r.passed)}</td></tr>`).join("")}</tbody></table></div></div>
    ${c ? `<div class="card mt"><h2>Is the tolerance honest? Calibration across ${c.seeds} independently generated worlds</h2>
      <p class="sub">One data set could be lucky. <code>scripts/calibrate_tolerance.py</code> regenerates the synthetic world under ${c.seeds} different seeds and runs method v${esc(c.method_version)} blind on each (${c.estimates} estimates).</p>
      <div class="grid g6">
        ${tile("Median error", `${c.abs_error_pp.p50}pp`)}
        ${tile("95th percentile", `${c.abs_error_pp.p95}pp`)}
        ${tile("99th percentile", `${c.abs_error_pp.p99}pp`)}
        ${tile("Within ±" + c.tolerance_pp + "pp", `${(c.share_within_tolerance * 100).toFixed(1)}%`)}
        ${tile("Mean CI coverage", `${Math.round(c.mean_ci_coverage * 100)}%`, "target 95%")}
        ${tile("Null false-positive rate", `${Math.round(c.null_false_positive_rate * 100)}%`, "target 5%")}
      </div></div>` : ""}`;
  const rows = [...v.rows].filter((r) => r.status === "ok").reverse();
  const y = rows.map((r) => `${r.promo_id} · ${r.promo_name}`);
  const shapes = rows.map((r, i) => ({ type: "rect", xref: "x", yref: "y", x0: r.true_uplift_pct * 100 - tol, x1: r.true_uplift_pct * 100 + tol,
    y0: i - 0.32, y1: i + 0.32, fillcolor: css("--excluded-band"), line: { width: 0 }, layer: "below" }));
  plot("recChart", [
    { type: "scatter", mode: "markers", x: rows.map((r) => r.true_uplift_pct * 100), y, marker: { symbol: "diamond", size: 11, color: css("--ink") },
      hovertemplate: "%{y}<br>Planted %{x:+.1f}%<extra></extra>" },
    { type: "scatter", mode: "markers", x: rows.map((r) => r.estimated_uplift_pct * 100), y,
      error_x: { type: "data", symmetric: false, array: rows.map((r) => (r.ci_high - r.estimated_uplift_pct) * 100),
                 arrayminus: rows.map((r) => (r.estimated_uplift_pct - r.ci_low) * 100), color: css("--series-1"), thickness: 2, width: 0 },
      marker: { size: 9, color: css("--series-1"), line: { color: css("--surface"), width: 1.5 } },
      customdata: rows.map((r) => [pp(r.error_pp)]), hovertemplate: "%{y}<br>Estimated %{x:+.2f}% (error %{customdata[0]})<extra></extra>" },
  ], { shapes, xaxis: { ticksuffix: "%", zeroline: true, title: { text: "Uplift" } }, yaxis: { gridcolor: "rgba(0,0,0,0)" } });
}

// ---------------------------------------------------------------- 5. reproducibility
async function renderRepro() {
  const m = state.meta;
  view.innerHTML = `
    <div class="page-head"><div><h1>Reproducibility</h1>
      <p>The same data and the same method version must give the same answer, to the last digit, no matter who runs it or when.
      Each run reloads the data from disk, re-runs all ${m.n_promotions} attributions (including 1,000 bootstrap draws each) and hashes every reported number.</p></div></div>
    <div class="grid g2">
      <div class="card"><h2>Run it yourself</h2><p class="sub">The fingerprint is a SHA-256 of every uplift, interval, p-value, control pairing and baseline week.</p>
        <div class="row"><label class="field">Number of runs<select id="nRuns"><option>3</option><option selected>5</option><option>10</option></select></label>
          <span class="spacer"></span><button class="primary" id="goRepro">▶ Run attribution again</button></div>
        <div id="reproOut" class="mt"></div></div>
      <div class="card"><h2>What is pinned</h2><p class="sub">These four identifiers fully determine every result.</p>
        <dl class="kv">
          <dt>Method version</dt><dd><span class="pill">v${esc(m.method_version)}</span> <span class="muted">— code in attribution/</span></dd>
          <dt>Config hash</dt><dd><span class="pill">${esc(m.config_hash)}</span> <span class="muted">— method_config.yaml</span></dd>
          <dt>Data hash</dt><dd><span class="pill">${esc(m.data_hash)}</span> <span class="muted">— input CSVs</span></dd>
          <dt>Random seed</dt><dd><span class="muted">part of the config; each promotion gets its own stream, so results don't depend on run order</span></dd>
        </dl>
        <h3>Covered by automated tests</h3>
        <ul class="ink2" style="margin:0;padding-left:18px">
          <li>two runs in one process give identical fingerprints</li>
          <li>a fresh load of the data from disk gives the same fingerprint</li>
          <li>one promo run on its own equals the same promo run in a batch</li>
          <li>changing the seed <em>does</em> change the fingerprint (so the seed is part of the method)</li>
          <li>the data generator reproduces the pinned CSVs byte for byte</li>
        </ul></div>
    </div>`;
  $("#goRepro").onclick = async (e) => {
    e.target.disabled = true;
    $("#reproOut").innerHTML = spinner("Running…");
    try {
      const r = await api("/api/reproducibility", { method: "POST", body: { runs: +$("#nRuns").value } });
      $("#reproOut").innerHTML = `
        <div class="verdict ${r.identical ? "pass" : "block"}"><div class="big">${r.identical ? "✓ Identical" : "✕ Different"}</div>
          <div>${r.runs.length} independent runs, ${r.identical ? "one fingerprint" : "results differ between runs"}.</div></div>
        <table class="mt"><thead><tr><th>Run</th><th>Result fingerprint (SHA-256)</th><th class="num">Time</th></tr></thead><tbody>
        ${r.runs.map((x) => `<tr><td>#${x.run}</td><td class="fp">${x.fingerprint}</td><td class="num">${x.seconds}s</td></tr>`).join("")}</tbody></table>`;
    } finally { e.target.disabled = false; }
  };
}

// ---------------------------------------------------------------- 6. gate
async function renderGate(arg) {
  let autoRun = false;
  if (arg && arg !== state.selectedProposal) { state.selectedProposal = decodeURIComponent(arg); state.lastGate = null; autoRun = arg !== "__custom"; }
  const [props, log, val, meta] = await Promise.all([api("/api/proposals"), api("/api/gate/log"), getValidation(), api("/api/method")]);
  state.proposals = props;
  const cfg = meta.config;
  const sel = state.selectedProposal || props[0]?.file;
  view.innerHTML = `
    <div class="page-head"><div><h1>Method-change gate</h1>
      <p>A change to the method cannot ship unmeasured. Every proposed change runs against the synthetic data with its planted effects and must still recover them, stay reproducible and bump the version. CI runs the same check on every pull request (<code>.github/workflows/method-gate.yml</code>).</p></div></div>
    <div class="grid" style="grid-template-columns: minmax(0,1fr) minmax(0,2fr)">
      <div class="grid" style="align-content:start">
        <div class="card"><h2>Proposed changes</h2><p class="sub">From <code>configs/proposals/</code>. Pick one, then run the gate.</p>
          <div class="grid" style="gap:8px">${props.map((p) => `
            <div class="proposal ${p.file === sel ? "sel" : ""}" data-file="${esc(p.file)}">
              <div class="pt">${esc(p.title)}</div>
              <div class="pm">v${esc(cfg.method_version)} → v${esc(p.method_version)} · ${p.diff.filter((d) => d.key !== "method_version").length} setting(s) · ${esc(p.author)}</div></div>`).join("")}
            <div class="proposal ${sel === "__custom" ? "sel" : ""}" data-file="__custom"><div class="pt">✎ Build your own change</div><div class="pm">Edit the method settings and gate them</div></div>
          </div></div>
        <div class="card"><h2>Gate history</h2><p class="sub">Every gate run is logged to <code>reports/gate_log.jsonl</code>.</p>
          ${log.length ? `<table><tbody>${log.slice(0, 12).map((l) => `<tr><td>${okBadge(l.verdict === "PASS", "PASS", "BLOCK")}</td><td>${esc(l.label)}<div class="muted" style="font-size:11.5px">${esc(l.timestamp.replace("T", " ").slice(0, 16))} · v${esc(l.proposed_version)}</div></td></tr>`).join("")}</tbody></table>` : `<p class="muted">No gate runs yet.</p>`}
        </div>
      </div>
      <div class="grid" style="align-content:start">
        <div class="card" id="propDetail"></div>
        <div id="gateOut"></div>
      </div>
    </div>`;
  document.querySelectorAll(".proposal").forEach((el) => el.onclick = () => { location.hash = `#/gate/${encodeURIComponent(el.dataset.file)}`; });
  const det = $("#propDetail");
  if (sel === "__custom") {
    det.innerHTML = `<h2>Build your own method change</h2><p class="sub">Starts from the current method (v${esc(cfg.method_version)}). Try weakening the control selection, or try loosening the tolerance and see what happens.</p>
      <div class="form-grid">
        <label class="field">Control strategy<select id="f_strategy">${["matched", "all_untreated", "random", "none"].map((s) => `<option ${s === cfg.controls.strategy ? "selected" : ""}>${s}</option>`).join("")}</select></label>
        <label class="field">Exact match on<select id="f_exact">${[["format,region", "format + region"], ["format", "format"], ["region", "region"], ["", "nothing"]].map(([v, l]) => `<option value="${v}" ${v === cfg.controls.exact_match_on.join(",") ? "selected" : ""}>${l}</option>`).join("")}</select></label>
        <label class="field">Controls per treated store<input type="number" id="f_k" min="1" max="20" value="${cfg.controls.controls_per_treated}"></label>
        <label class="field">Match window (weeks)<input type="number" id="f_mw" min="4" max="40" value="${cfg.controls.match_window_weeks}"></label>
        <label class="field">Baseline weeks<input type="number" id="f_pre" min="2" max="26" value="${cfg.baseline.pre_period_weeks}"></label>
        <label class="field">Gap before launch (weeks)<input type="number" id="f_gap" min="0" max="6" value="${cfg.baseline.gap_weeks}"></label>
        <label class="field">Bootstrap iterations<input type="number" id="f_boot" min="100" max="5000" step="100" value="${cfg.inference.bootstrap_iterations}"></label>
        <label class="field">Random seed<input type="number" id="f_seed" value="${cfg.inference.seed}"></label>
        <label class="field">Tolerance (pp) — owned by main<input type="number" id="f_tol" step="0.5" value="${cfg.validation.tolerance_pp}"></label>
        <label class="field">New method version<input type="text" id="f_ver" value="${bump(cfg.method_version)}"></label>
      </div>
      <div class="row mt">
        <label class="check"><input type="checkbox" id="f_hol" ${cfg.baseline.exclude_holiday_weeks ? "checked" : ""}> Exclude holiday weeks from baseline</label>
        <label class="check"><input type="checkbox" id="f_promo" ${cfg.baseline.exclude_promo_weeks ? "checked" : ""}> Exclude other-promo weeks</label>
      </div>
      <div class="row mt"><span class="spacer"></span><button class="primary" id="runGate">▶ Run gate</button></div>`;
  } else {
    const p = props.find((x) => x.file === sel);
    det.innerHTML = `<div class="card-head"><div><h2>${esc(p.title)}</h2><p class="sub">${esc(p.author)} · <code>${esc(p.file)}</code></p></div>
        <button class="primary" id="runGate">▶ Run gate</button></div>
      <div class="callout">${esc(p.rationale)}</div>
      <h3>Changes vs current method</h3>
      <table><thead><tr><th>Setting</th><th>Current</th><th>Proposed</th></tr></thead><tbody>
        ${p.diff.map((d) => `<tr><td><code>${esc(d.key)}</code></td><td class="ink2">${esc(JSON.stringify(d.current))}</td><td><strong>${esc(JSON.stringify(d.proposed))}</strong></td></tr>`).join("")}</tbody></table>`;
  }
  $("#runGate").onclick = async (e) => {
    e.target.disabled = true;
    $("#gateOut").innerHTML = `<div class="card">${spinner("Running gate: recovery on planted effects, reproducibility, versioning…")}</div>`;
    try {
      let body;
      if (sel === "__custom") {
        const exact = $("#f_exact").value;
        body = { title: "Custom change from UI", method_version: $("#f_ver").value, overrides: {
          controls: { strategy: $("#f_strategy").value, exact_match_on: exact ? exact.split(",") : [], controls_per_treated: +$("#f_k").value, match_window_weeks: +$("#f_mw").value },
          baseline: { pre_period_weeks: +$("#f_pre").value, gap_weeks: +$("#f_gap").value, exclude_holiday_weeks: $("#f_hol").checked, exclude_promo_weeks: $("#f_promo").checked },
          inference: { bootstrap_iterations: +$("#f_boot").value, seed: +$("#f_seed").value },
          validation: { tolerance_pp: +$("#f_tol").value } } };
      } else body = { proposal: sel };
      state.lastGate = await api("/api/gate", { method: "POST", body });
      showGate(state.lastGate, val);
    } catch (err) { $("#gateOut").innerHTML = ""; }
    finally { e.target.disabled = false; }
  };
  if (state.lastGate) showGate(state.lastGate, val);
  else if (autoRun) $("#runGate").click();
}
function bump(v) { const p = v.split(".").map(Number); p[1] += 1; p[2] = 0; return p.join("."); }

function showGate(g, current) {
  const pass = g.verdict === "PASS";
  const tol = current.summary.tolerance_pp;
  $("#gateOut").innerHTML = `
    <div class="card">
      <div class="verdict ${pass ? "pass" : "block"}"><div class="big">${pass ? "✓ PASS" : "✕ BLOCKED"}</div>
        <div><strong>${esc(g.label)}</strong><div class="ink2">${pass ? "Safe to merge: the method still recovers the planted effects." : "This change cannot merge. See the failed checks below."}
          · v${esc(g.current_version)} → v${esc(g.proposed_version)} · ${g.seconds}s</div></div></div>
      <ul class="check-list mt">${g.checks.map((c) => `<li><span class="ico ${c.passed ? "ok" : "no"}">${c.passed ? "✓" : "✕"}</span>
        <div><div class="t">${c.id} · ${esc(c.name)}</div><div class="d">${esc(c.detail)}</div></div></li>`).join("")}</ul>
    </div>
    <div class="card mt"><h2>Recovery error per promotion: current vs proposed</h2>
      <p class="sub">Estimate minus planted effect, in percentage points. Bars outside the shaded ±${tol}pp band fail the gate.</p>
      <div class="legend-inline"><span><i class="sw" style="background:var(--series-1)"></i>Current v${esc(g.current_version)}</span>
        <span><i class="sw" style="background:var(--series-2)"></i>Proposed v${esc(g.proposed_version)}</span>
        <span><i class="sw" style="background:var(--good-soft);outline:1px solid var(--good)"></i>Tolerance</span></div>
      <div id="gateChart" class="chart"></div></div>`;
  const ids = current.rows.map((r) => r.promo_id);
  const prop = Object.fromEntries(g.recovery.rows.map((r) => [r.promo_id, r]));
  const yAbs = Math.max(tol * 1.6, ...g.recovery.rows.map((r) => Math.abs(r.error_pp || 0)), ...current.rows.map((r) => Math.abs(r.error_pp))) * 1.1;
  plot("gateChart", [
    { type: "bar", x: ids, y: current.rows.map((r) => r.error_pp), name: "Current", marker: { color: css("--series-1") }, hovertemplate: "%{x} current: %{y:+.2f}pp<extra></extra>" },
    { type: "bar", x: ids, y: ids.map((i) => prop[i]?.error_pp ?? null), name: "Proposed", marker: { color: css("--series-2") },
      hovertemplate: "%{x} proposed: %{y:+.2f}pp<extra></extra>" },
  ], { barmode: "group", bargap: 0.3, bargroupgap: 0.08,
       shapes: [{ type: "rect", xref: "paper", x0: 0, x1: 1, y0: -tol, y1: tol, fillcolor: css("--good-soft"), line: { width: 1, color: css("--good"), dash: "dot" }, layer: "below" }],
       yaxis: { ticksuffix: "pp", range: [-yAbs, yAbs], zeroline: true, title: { text: "Estimation error" } } });
}

// ---------------------------------------------------------------- 7. data
async function renderData() {
  const d = await api("/api/data");
  const m = d.manifest;
  view.innerHTML = `
    <div class="page-head"><div><h1>Synthetic data</h1>
      <p>${m.n_stores} stores × ${m.n_skus} SKUs × ${m.n_weeks} weeks (${m.first_week} → ${m.last_week}), generated by <code>data_gen/generate_data.py</code> with seed <code>${m.seed}</code>.
      Effects were planted in treated store × SKU × week cells, and the method never sees them.</p></div></div>
    <div class="grid g2">
      <div class="card"><h2>Files</h2><p class="sub">Click a file to preview it. Checksums are pinned in <code>data_manifest.json</code>; the gate fails if the data changes.</p>
        <table><thead><tr><th>File</th><th class="num">Rows</th><th class="num">Size</th><th>SHA-256</th><th></th></tr></thead><tbody>
        ${d.files.map((f) => `<tr class="click" data-file="${esc(f.file)}"><td><code>${esc(f.file)}</code></td><td class="num">${num(f.rows)}</td>
          <td class="num">${num(f.size_kb)} KB</td><td><span class="pill">${esc(f.sha256)}</span></td>
          <td>${f.hidden_from_method ? `<span class="badge bad">hidden from method</span>` : `<span class="badge neutral">method input</span>`}</td></tr>`).join("")}</tbody></table></div>
      <div class="card"><h2>How the world was built</h2><p class="sub">The traps that make a naive method fail on purpose:</p>
        <ul class="ink2" style="margin:0;padding-left:18px;line-height:1.7">
          <li><strong>Seasonality differs by store format</strong> (Hyper ${m.parameters.format_season_amplitude.Hyper * 100}% swing, Express counter-seasonal) and <strong>trend differs by region</strong> (North +${m.parameters.region_trend_per_year.North * 100}%/yr, South ${m.parameters.region_trend_per_year.South * 100}%/yr).</li>
          <li><strong>Treated stores are not random</strong>: they lean towards large stores in a favoured region, so "all untreated stores" is a biased comparison.</li>
          <li><strong>Holiday lifts</strong> up to +${Math.round((Math.max(...Object.values(m.parameters.holiday_lift)) - 1) * 100)}% (Christmas), plus a chocolate gifting spike.</li>
          <li><strong>Repeat promotions</strong> on the same SKUs (P07 → P10, P04 → P08), so baselines must skip earlier promo weeks.</li>
          <li><strong>A null promo (0%) and a negative promo (−6%)</strong> that the method must not report as wins.</li>
          <li>A holdout rule keeps ≥ ${m.parameters.min_holdout_per_format_region} untreated stores in every format × region cell.</li>
        </ul>
        <h3>Store mix (stores per region × format)</h3>
        <table><thead><tr><th></th>${d.store_mix.formats.map((f) => `<th class="num">${f}</th>`).join("")}</tr></thead><tbody>
          ${d.store_mix.regions.map((r, i) => `<tr><td>${r}</td>${d.store_mix.counts[i].map((c) => `<td class="num">${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
    </div>
    <div class="card mt" id="preview"><p class="muted">Select a file above to preview its first rows.</p></div>
    <div class="card mt"><h2>Planted ground truth</h2><p class="sub"><code>ground_truth_effects.csv</code>, read only by the validation harness. A test confirms the method's code never references it.</p>
      <table><thead><tr><th>Promo</th><th class="num">Planted uplift</th><th class="num">Expected incremental units</th><th>Scenario</th></tr></thead><tbody>
      ${d.ground_truth.map((g) => `<tr><td><strong>${g.promo_id}</strong></td><td class="num">${pct(g.true_uplift_pct)}</td><td class="num">${signed(g.expected_incremental_units)}</td><td class="ink2">${esc(g.scenario)}</td></tr>`).join("")}</tbody></table></div>`;
  document.querySelectorAll("tr[data-file]").forEach((tr) => tr.onclick = async () => {
    const f = tr.dataset.file;
    $("#preview").innerHTML = spinner();
    const p = await api(`/api/data/${encodeURIComponent(f)}?limit=15`);
    $("#preview").innerHTML = `<h2><code>${esc(f)}</code></h2><p class="sub">First ${p.rows.length} rows</p><div class="table-wrap"><table>
      <thead><tr>${p.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${p.rows.map((r) => `<tr>${r.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  });
}

// ---------------------------------------------------------------- boot
loadMeta().then(route);
