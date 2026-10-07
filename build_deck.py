"""
Builds Promotion_Attribution_Demo.pptx from deck_data.json (numbers pulled from the
running service) and the app screenshots in assets/.

    python presentation/build_deck.py
"""
from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_TICK_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from lxml import etree
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / "deck_data.json").read_text())
A = HERE / "assets"
OUT = HERE / "Promotion_Attribution_Demo.pptx"

# ---------------------------------------------------------------- palette (matches the app)
NAVY = RGBColor(0x13, 0x23, 0x3F)
NAVY_2 = RGBColor(0x1E, 0x33, 0x58)
BLUE = RGBColor(0x2A, 0x78, 0xD6)
BLUE_SOFT = RGBColor(0xE3, 0xEE, 0xFB)
ORANGE = RGBColor(0xEB, 0x68, 0x34)
ORANGE_SOFT = RGBColor(0xFD, 0xEB, 0xE3)
INK = RGBColor(0x1F, 0x29, 0x37)
MUTED = RGBColor(0x5F, 0x67, 0x73)
GREY = RGBColor(0xB8, 0xBD, 0xC6)
CARD = RGBColor(0xF3, 0xF5, 0xF9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x0E, 0x7A, 0x36)
GREEN_SOFT = RGBColor(0xE4, 0xF3, 0xE8)
RED = RGBColor(0xC6, 0x2E, 0x2E)
RED_SOFT = RGBColor(0xFB, 0xE7, 0xE7)
ICE = RGBColor(0xC9, 0xD8, 0xF2)
FONT = "Calibri"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
TITLE_ONLY = prs.slide_layouts[5]
N_SLIDES = 13
_count = 0


# ---------------------------------------------------------------- helpers
def new_slide(title: str, dark: bool = False, notes: str = ""):
    global _count
    _count += 1
    s = prs.slides.add_slide(TITLE_ONLY)
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = NAVY if dark else WHITE
    t = s.shapes.title
    t.left, t.top, t.width, t.height = Inches(0.6), Inches(0.42), Inches(12.1), Inches(0.95)
    tf = t.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.text = title
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.runs[0]
    r.font.name, r.font.size, r.font.bold = FONT, Pt(32), True
    r.font.color.rgb = WHITE if dark else NAVY
    if _count > 1:
        text(s, 0.6, 7.0, 8, 0.3, "Promotion Performance Attribution · method v1.2.0", 10, color=GREY if dark else MUTED)
        text(s, 11.7, 7.0, 1.03, 0.3, f"{_count} / {N_SLIDES}", 10, color=GREY if dark else MUTED, align=PP_ALIGN.RIGHT)
    if notes:
        s.notes_slide.notes_text_frame.text = notes.strip()
    return s


def text(s, x, y, w, h, content, size=16, bold=False, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         italic=False, name=None, spacing=None):
    """content: str, or list of paragraphs; a paragraph is str or list of (text, {opts}) runs."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paras = content if isinstance(content, list) else [content]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if spacing:
            p.space_after = Pt(spacing)
        runs = para if isinstance(para, list) else [(para, {})]
        for rt, o in runs:
            r = p.add_run()
            r.text = rt
            f = r.font
            f.name = FONT
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", italic)
            f.color.rgb = o.get("color", color)
    return tb


def box(s, x, y, w, h, fill=CARD, radius=0.06, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, name=None):
    sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = radius
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(1.25)
    sh.shadow.inherit = False
    if name:
        sh.name = name
    return sh


def circle_num(s, x, y, n, d=0.55, fill=BLUE, color=WHITE, size=18):
    c = box(s, x, y, d, d, fill=fill, shape=MSO_SHAPE.OVAL)
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = str(n)
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(size), True, color
    return c


def chip(s, x, y, w, label, ok: bool):
    b = box(s, x, y, w, 0.34, fill=GREEN_SOFT if ok else RED_SOFT, radius=0.5)
    tf = b.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = ("✓ " if ok else "✕ ") + label
    r.font.name, r.font.size, r.font.bold = FONT, Pt(12), True
    r.font.color.rgb = GREEN if ok else RED
    return b


def picture(s, path, x, y, w=None, h=None, frame=True, name=None):
    from PIL import Image
    iw, ih = Image.open(path).size
    if w and not h:
        h = w * ih / iw
    elif h and not w:
        w = h * iw / ih
    if frame:
        pad = 0.08
        box(s, x - pad, y - pad, (w or 0) + 2 * pad, (h or 0) + 2 * pad, fill=WHITE, line=RGBColor(0xDD, 0xE1, 0xE8), radius=0.03)
    pic = s.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    if name:
        pic.name = name
    return pic


def style_chart(ch, size=12):
    ch.font.name = FONT
    ch.font.size = Pt(size)
    ch.font.color.rgb = MUTED


def pct(x, d=1):
    return f"{'+' if x > 0 else '−' if x < 0 else ''}{abs(x) * 100:.{d}f}%"


P = {p["promo_id"]: p for p in D["promos"]}
VAL = D["validation"]
CAL = D["calibration"]

# ================================================================ 1. title
s = new_slide("Promotion Performance Attribution", dark=True, notes="""
Opening. Introduce yourself and the capstone: Retail, Marketing & Sales Analytics, project 20.
One-line pitch: we turned promotion post-mortems from an argument into a measurement, with a method you can audit, test and trust.
Agenda: the problem, how it works, results, then the proof (validation, reproducibility, the merge gate), with a live demo throughout.
""")
s.shapes.title.top = Inches(2.15)
s.shapes.title.width = Inches(6.6)
s.shapes.title.height = Inches(1.6)
s.shapes.title.text_frame.paragraphs[0].runs[0].font.size = Pt(44)
text(s, 0.6, 3.85, 6.2, 1.0, "Measured, not argued: a promotion uplift method you can audit, test and trust", 20, color=ICE)
text(s, 0.6, 5.35, 6.2, 0.9, [
    [("Capstone demo · Retail Marketing & Sales Analytics", {"bold": True, "color": WHITE})],
    [("Live app: http://127.0.0.1:8000", {"color": GREY})],
], 14, spacing=4)
picture(s, A / "promo_crop.png", 7.35, 1.55, w=5.4, name="Counterfactual chart screenshot")
text(s, 7.35, 4.6, 5.4, 0.6, "Actual sales (blue) vs the counterfactual (orange): what would have happened without the promotion",
     12, color=GREY, italic=True)

# ================================================================ 2. problem
p07 = P["P07"]
s = new_slide("Same promotion, opposite conclusions", notes=f"""
Hook. "Did that promotion work?" Take Yogurt 15% Off.
The sales team compares promo weeks with the weeks just before: sales went DOWN {abs(p07['naive_estimates']['pre_post_no_control'])*100:.1f}%, so it failed.
The category team compares stores that ran it with stores that didn't: +{p07['naive_estimates']['promoted_vs_unpromoted_stores']*100:.0f}%, a huge success.
Same promotion, same data, opposite conclusions; it depends whose spreadsheet you trust.
The real answer is +15%. We know that for certain because we planted it, and the method recovers {pct(p07['uplift_pct'])}.
""")
text(s, 0.6, 1.3, 12, 0.5, "Yogurt 15% Off (P07): one data set, three ways of measuring it", 18, color=MUTED)
cards = [
    ("Sales team", "Pre/post: promo weeks vs the weeks before", p07["naive_estimates"]["pre_post_no_control"], "“It failed”", RED_SOFT, RED),
    ("Category team", "Stores that ran it vs stores that didn't", p07["naive_estimates"]["promoted_vs_unpromoted_stores"], "“Huge success”", ORANGE_SOFT, ORANGE),
    ("This method", "Matched twin stores + fixed baseline", p07["uplift_pct"], "Planted truth: +15.0%", BLUE_SOFT, BLUE),
]
for i, (who, how, v, verdict, fill, col) in enumerate(cards):
    x = 0.6 + i * 4.1
    box(s, x, 2.0, 3.8, 3.75, fill=fill, name=f"{who} card")
    text(s, x + 0.35, 2.3, 3.1, 0.4, who, 20, bold=True, color=INK)
    text(s, x + 0.35, 2.75, 3.1, 0.7, how, 14, color=MUTED)
    text(s, x + 0.35, 3.45, 3.1, 1.2, pct(v), 56, bold=True, color=col)
    text(s, x + 0.35, 4.85, 3.1, 0.5, verdict, 18, bold=True, color=INK)
text(s, 0.6, 6.1, 12, 0.45, "The calculation lived in personal spreadsheets, so the answer depended on who reported it.",
     16, italic=True, color=INK)

# ================================================================ 3. what we built
s = new_slide("The method is the deliverable, not just the number", notes="""
Instead of a spreadsheet, the calculation is now a service: software with the rules written down in code.
Three things make it trustworthy.
1. The method is fixed and written down: what counts as normal sales, which stores we compare against, and how uplift is computed are decided once, documented and version-numbered.
2. Every number comes with its counterfactual and its margin of error.
3. We proved it works on data with hidden answers, and any change to the method must pass that test before it ships.
TECH: Python + FastAPI service, versioned attribution package with a YAML config, pytest suite, CI workflow gating merges.
""")
pillars = [
    ("Method as code", "Baseline rules, control selection and the uplift formula live in version-controlled code and a config file, documented in METHOD.md.",
     "method_config.yaml · v1.2.0"),
    ("Counterfactual + confidence interval", "Every uplift is shown against what would have happened without the promotion, with a 95% interval, not just a headline.",
     "Bootstrap · 1,000 draws"),
    ("Proven and gated", "Validated on synthetic data with planted effects. A method change cannot merge unless it still recovers them.",
     "89 tests · CI merge gate"),
]
for i, (h, b, tag) in enumerate(pillars):
    x = 0.6 + i * 4.1
    box(s, x, 1.65, 3.8, 4.55, fill=CARD, name=f"Pillar {i + 1}")
    circle_num(s, x + 0.35, 1.95, i + 1, d=0.7, size=22)
    text(s, x + 0.35, 2.9, 3.15, 0.85, h, 21, bold=True, color=NAVY)
    text(s, x + 0.35, 3.85, 3.15, 1.6, b, 15, color=INK)
    t = box(s, x + 0.35, 5.5, 3.1, 0.42, fill=BLUE_SOFT, radius=0.5)
    tf = t.text_frame
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    r = tf.paragraphs[0].add_run()
    r.text = tag
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(13), True, BLUE
text(s, 0.6, 6.4, 12.1, 0.4, "Delivered: FastAPI service · 8-page web app · Ask (grounded Q&A) · test suite · CI workflow · synthetic data generator",
     14, color=MUTED)

# ================================================================ 4. how it works
s = new_slide("How the attribution works, in five steps", notes="""
Walk left to right.
1 Sales data: weekly sales by store and product.
2 Baseline by rule: the 13 normal weeks before launch, skipping holidays, the week before launch, and weeks with another promotion on the same products. If there's too little history, it refuses to report.
3 Twin stores: for each promoted store, the 3 untreated stores of the same format and region whose sales tracked it most closely before launch.
4 Counterfactual and uplift: twin-store sales scaled to the promoted store's baseline; uplift = actual / counterfactual - 1. Seasonality, holidays and trend cancel because twins share them.
5 Confidence interval: re-run 1,000 times with stores reshuffled; report the middle 95%.
Validation and the gate wrap the whole pipeline.
TECH: difference-in-differences in ratio form; two-stage bootstrap (Poisson re-weighting of controls + resampling of treated stores), seeded.
""")
steps = [
    ("Sales data", "Weekly units by store × product × week", "416k rows"),
    ("Baseline by rule", "13 normal weeks before launch; skip holidays and other promos", "Rules B1–B5"),
    ("Twin stores", "3 untreated stores per promoted store: same format + region, closest sales pattern", "Matched pairs"),
    ("Counterfactual & uplift", "Twins scaled to the store's baseline; uplift = actual ÷ counterfactual − 1", "Ratio DiD"),
    ("Confidence interval", "Re-estimate 1,000 times with stores reshuffled; keep the middle 95%", "Bootstrap"),
]
w, gap = 2.22, 0.25
for i, (h, b, tag) in enumerate(steps):
    x = 0.6 + i * (w + gap)
    box(s, x, 1.75, w, 3.35, fill=CARD, name=f"Step {i + 1}")
    circle_num(s, x + 0.25, 2.0, i + 1, d=0.55, fill=ORANGE if i == 3 else BLUE)
    text(s, x + 0.25, 2.75, w - 0.45, 0.75, h, 17, bold=True, color=NAVY)
    text(s, x + 0.25, 3.5, w - 0.45, 1.3, b, 13, color=INK)
    text(s, x + 0.25, 4.7, w - 0.45, 0.3, tag, 12, bold=True, color=BLUE)
    if i < len(steps) - 1:
        a = box(s, x + w + 0.02, 3.25, gap - 0.04, 0.3, fill=GREY, shape=MSO_SHAPE.RIGHT_ARROW)
wrap = box(s, 0.6, 5.4, 12.1, 1.15, fill=NAVY, name="Validation wrapper")
text(s, 0.95, 5.55, 11.5, 0.9, [
    [("Wrapped around every step: ", {"bold": True, "color": WHITE}),
     ("synthetic ground-truth validation · reproducibility fingerprints · a merge gate that blocks any method change that stops recovering the planted effects",
      {"color": ICE})]], 16, anchor=MSO_ANCHOR.MIDDLE)

# ================================================================ 5. portfolio
ok = [p for p in D["promos"] if p["status"] == "ok"]
n_up = sum(p["ci_low"] > 0 for p in ok)
n_down = sum(p["ci_high"] < 0 for p in ok)
n_flat = len(ok) - n_up - n_down
n_roi = sum(p["roi"] > 0 for p in ok)
s = new_slide(f"{n_up} of {len(ok)} promotions lifted sales, but only {n_roi} paid back", notes=f"""
DEMO: Portfolio page.
Twelve promotions, all measured the same way: {n_up} genuinely increased sales, {n_flat} had no measurable effect, and {n_down} hurt sales.
The chart compares the method (blue) with what a pre/post spreadsheet would have said (grey). Summer Soda: spreadsheet {pct(P['P03']['naive_estimates']['pre_post_no_control'])}, method {pct(P['P03']['uplift_pct'])}. Teams were taking credit for twice the real result.
ROI: only {n_roi} promotions paid back their funding. Both buy-one-get-one promotions drove big volume but lost money.
""")
cd = CategoryChartData()
rows = list(reversed(ok))
def short(name: str, limit: int = 20) -> str:
    name = name.replace("Buy-One-Get-One", "BOGO").replace(" (Repeat)", " repeat")
    out = ""
    for w_ in name.split():
        if len(out) + len(w_) + 1 > limit:
            break
        out = f"{out} {w_}".strip()
    return out


cd.categories = [f"{p['promo_id']} {short(p['promo_name'])}" for p in rows]
cd.add_series("Spreadsheet pre/post", [round(p["naive_estimates"]["pre_post_no_control"] * 100, 1) for p in rows])
cd.add_series("This method", [round(p["uplift_pct"] * 100, 1) for p in rows])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.5), Inches(1.4), Inches(8.3), Inches(5.45), cd)
gf.name = "Uplift: method vs spreadsheet"
ch = gf.chart
style_chart(ch, 11)
ch.has_legend = True
ch.legend.position = XL_LEGEND_POSITION.TOP
ch.legend.include_in_layout = False
ch.legend.font.size = Pt(12)
plot = ch.plots[0]
plot.gap_width = 45
plot.overlap = -10
for ser, col in zip(plot.series, (GREY, BLUE)):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = col
    ser.invert_if_negative = False
plot.has_data_labels = True
dl = plot.data_labels
dl.number_format = '+0.0"%";−0.0"%"'
dl.number_format_is_linked = False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
dl.font.size = Pt(10)
dl.font.color.rgb = MUTED
va = ch.value_axis
va.has_major_gridlines = True
va.major_gridlines.format.line.color.rgb = RGBColor(0xE6, 0xE8, 0xEC)
va.format.line.fill.background()
va.tick_labels.number_format = '0"%"'
va.tick_labels.number_format_is_linked = False
va.tick_labels.font.size = Pt(10)
ca = ch.category_axis
ca.tick_label_position = XL_TICK_LABEL_POSITION.LOW
ca.format.line.color.rgb = GREY
ca.tick_labels.font.size = Pt(10)
stats = [(str(n_up), "significant uplift", BLUE), (str(n_flat), "no measurable effect", MUTED),
         (str(n_down), "significant decline", RED), (f"{n_roi}/{len(ok)}", "paid back their funding (ROI > 0)", GREEN)]
for i, (v, lab, col) in enumerate(stats):
    y = 1.5 + i * 1.33
    box(s, 9.2, y, 3.55, 1.15, fill=CARD)
    text(s, 9.45, y + 0.12, 1.3, 0.9, v, 36, bold=True, color=col, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 10.8, y + 0.12, 1.85, 0.9, lab, 14, color=INK, anchor=MSO_ANCHOR.MIDDLE)

# ================================================================ 6. counterfactual
p9 = P["P09"]
s = new_slide("The counterfactual shows what would have happened anyway", notes=f"""
DEMO: Promotion deep-dive, P09 Holiday Chocolate Gifting.
Blue is what the promoted stores actually sold. The orange dashed line is the counterfactual: what they would have sold without the promotion, built from twin stores.
The Christmas spike: a naive analysis credits it to the promotion. The twin stores spiked at Christmas too, so the counterfactual rises with it. Only the gap counts: {pct(p9['uplift_pct'])}.
Light blue = baseline weeks; grey = weeks thrown out by rule (a holiday, the week before launch).
Margin of error: {pct(p9['ci_low'])} to {pct(p9['ci_high'])}. The planted effect was +18%.
Then show "one promotion, three answers" and the matched-pairs table: every store and its twins are auditable.
""")
picture(s, A / "promo_crop.png", 0.68, 1.55, w=8.25, name="P09 counterfactual screenshot")
callouts = [
    (pct(p9["uplift_pct"]), f"uplift, 95% CI {pct(p9['ci_low'])} to {pct(p9['ci_high'])}", BLUE),
    ("+18.0%", "planted truth: recovered within 0.6pp", GREEN),
    ("Christmas", "spike is in the counterfactual too, so it isn't credited to the promo", ORANGE),
    (f"{D['p09_detail']['n_controls']} twins", f"control stores matched to {D['p09_detail']['n_treated']} promoted stores (same format + region)", NAVY),
]
for i, (v, lab, col) in enumerate(callouts):
    y = 1.5 + i * 1.33
    box(s, 9.3, y, 3.45, 1.15, fill=CARD)
    text(s, 9.5, y + 0.1, 3.1, 0.5, v, 26, bold=True, color=col)
    text(s, 9.5, y + 0.6, 3.1, 0.5, lab, 12, color=INK)

# ================================================================ 7. mechanics
G = D["groups"]
s = new_slide("BOGO drives the most volume, and loses the most money", notes="""
Business insight from the Ask page: "Which mechanics work best on average?"
BOGO has the biggest uplift but the worst ROI: giving away half the product costs more than the extra sales earn.
Bundles and simple price cuts (TPR) pay back.
Caveat: these are averages over a handful of promotions. Each promotion's uplift is measured causally, but the comparison between mechanics is descriptive.
""")


def mech_chart(x, title, key, color, fmt):
    cd = CategoryChartData()
    order = sorted(G, key=lambda g: g[key], reverse=True)
    cd.categories = [g["group"] for g in order]
    cd.add_series(title, [round(g[key] * 100, 4) for g in order])
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(1.85), Inches(5.9), Inches(4.0), cd)
    gf.name = title
    ch = gf.chart
    style_chart(ch, 12)
    ch.has_legend = False
    ch.has_title = True
    ch.chart_title.text_frame.text = title
    tr = ch.chart_title.text_frame.paragraphs[0].runs[0]
    tr.font.size, tr.font.bold, tr.font.color.rgb, tr.font.name = Pt(16), True, INK, FONT
    pl = ch.plots[0]
    pl.gap_width = 70
    ser = pl.series[0]
    ser.invert_if_negative = False
    for idx, g in enumerate(order):
        pt = ser.points[idx]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = color if g[key] >= 0 else RED
    for dpt in ser._element.findall(qn("c:dPt")):       # PowerPoint inverts negative points unless told not to
        if dpt.find(qn("c:invertIfNegative")) is None:
            el = etree.Element(qn("c:invertIfNegative"))
            el.set("val", "0")
            dpt.find(qn("c:idx")).addnext(el)
    pl.has_data_labels = True
    pl.data_labels.number_format = fmt
    pl.data_labels.number_format_is_linked = False
    pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    pl.data_labels.font.size = Pt(12)
    pl.data_labels.font.bold = True
    pl.data_labels.font.color.rgb = INK
    va = ch.value_axis
    va.major_gridlines.format.line.color.rgb = RGBColor(0xE6, 0xE8, 0xEC)
    va.format.line.fill.background()
    va.tick_labels.number_format = '0"%"'
    va.tick_labels.number_format_is_linked = False
    ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
    ch.category_axis.format.line.color.rgb = GREY


mech_chart(0.6, "Average uplift by mechanic", "mean_uplift_pct", BLUE, '+0.0"%";−0.0"%"')
mech_chart(6.8, "Average ROI by mechanic", "mean_roi", GREEN, '+0"%";−0"%"')
bogo = next(g for g in G if g["group"] == "BOGO")
text(s, 0.6, 6.15, 12.1, 0.6, [[("Read-out: ", {"bold": True}),
     (f"BOGO lifts volume {pct(bogo['mean_uplift_pct'])} on average but returns {pct(bogo['mean_roi'], 0)} ROI. "
      "Averages over few promotions are descriptive; each promotion's uplift is measured causally.", {})]], 15)

# ================================================================ 8. Ask
s = new_slide("Ask: plain-English answers where every number is checked", notes="""
DEMO: Ask page. Click "How did P09 perform?" then "What about its ROI?".
Not everyone wants to read charts; here a manager can just ask.
Every number has an E1 tag: the evidence it came from. Click it to see the exact record.
The green badge: before any answer is shown, every number in it is checked against the evidence. It can't make numbers up.
It understood "its ROI" meant the chocolate promotion from the previous question.
No AI model: same question, same answer. A 17-question evaluation set in the test suite guards it.
""")
points = [
    ("Cites its evidence", "Every claim carries an [E#] tag that opens the exact attribution record behind it."),
    ("Checks every number", "Each figure must match the evidence before the answer is shown: “15/15 verified”."),
    ("Follows the conversation", "“What about its ROI?” resolves to the promotion just discussed."),
    ("Deterministic", "No AI model, so the same question always gets the same answer; guarded by a 17-question eval set."),
]
for i, (h, b) in enumerate(points):
    y = 1.6 + i * 1.28
    circle_num(s, 0.6, y + 0.05, i + 1, d=0.5, size=16)
    text(s, 1.3, y, 3.8, 0.4, h, 18, bold=True, color=NAVY)
    text(s, 1.3, y + 0.42, 3.8, 0.8, b, 13, color=INK)
picture(s, A / "ask_crop.png", 5.55, 1.6, w=7.15, name="Ask screenshot")

# ================================================================ 9. validation
rows = VAL["rows"]
sm = VAL["summary"]
s = new_slide("We hid the answers, and the method found every one", notes=f"""
DEMO: Ground-truth validation page.
With real sales you never know the true effect, so you can't grade a method. So we built a realistic simulated retailer (100 stores, 40 products, two years of weekly sales) and planted a known effect in each promotion, like hiding an answer key.
The method ran without seeing the answers. Planted (dark) vs found (blue): {sm['n_passed']} of {sm['n_promos']} within ±2 points; the largest miss was {sm['max_abs_error_pp']:.2f} points.
It correctly found the zero-effect promotion and the negative one.
One test could be lucky, so we generated {CAL['seeds']} different simulated retailers: {CAL['share_within_tolerance']*100:.1f}% of {CAL['estimates']} estimates landed within ±2 points. That's why the tolerance can be stated with confidence.
""")
cd = CategoryChartData()
cd.categories = [r["promo_id"] for r in rows]
cd.add_series("Planted (truth)", [round(r["true_uplift_pct"] * 100, 1) for r in rows])
cd.add_series("Recovered by the method", [round(r["estimated_uplift_pct"] * 100, 1) for r in rows])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.4), Inches(8.4), Inches(5.4), cd)
gf.name = "Planted vs recovered"
ch = gf.chart
style_chart(ch, 11)
ch.has_legend = True
ch.legend.position = XL_LEGEND_POSITION.TOP
ch.legend.include_in_layout = False
ch.legend.font.size = Pt(12)
pl = ch.plots[0]
pl.gap_width = 60
pl.overlap = -5
for ser, col in zip(pl.series, (NAVY, BLUE)):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = col
    ser.invert_if_negative = False
va = ch.value_axis
va.major_gridlines.format.line.color.rgb = RGBColor(0xE6, 0xE8, 0xEC)
va.format.line.fill.background()
va.tick_labels.number_format = '0"%"'
va.tick_labels.number_format_is_linked = False
ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
ch.category_axis.format.line.color.rgb = GREY
vstats = [(f"{sm['n_passed']}/{sm['n_promos']}", "planted effects recovered within ±2.0pp", GREEN),
          (f"{sm['max_abs_error_pp']:.2f}pp", f"largest error (mean {sm['mean_abs_error_pp']:.2f}pp)", BLUE),
          (f"{CAL['share_within_tolerance'] * 100:.1f}%", f"of {CAL['estimates']} estimates within ±2pp across {CAL['seeds']} new worlds", NAVY),
          (f"{CAL['mean_ci_coverage'] * 100:.0f}%", "of 95% intervals contained the truth (target 95%)", ORANGE)]
for i, (v, lab, col) in enumerate(vstats):
    y = 1.5 + i * 1.33
    box(s, 9.2, y, 3.55, 1.15, fill=CARD)
    text(s, 9.42, y + 0.1, 3.2, 0.5, v, 28, bold=True, color=col)
    text(s, 9.42, y + 0.62, 3.2, 0.5, lab, 12, color=INK)

# ================================================================ 10. reproducibility
R = D["repro"]
s = new_slide("Same data, same version, same answer: every time", notes=f"""
DEMO: Reproducibility page, Run 5x.
"It depends who reports it" is gone: we re-run the whole analysis from scratch 5 times. Each run produces a fingerprint, a unique code for every number in the results. All identical.
Pinned: method version, config hash, data hash, and the random seed (each promotion gets its own stream, so results don't depend on run order).
TECH: SHA-256 over all reported values; tests also prove the data generator reproduces the CSVs byte for byte.
""")
box(s, 0.6, 1.55, 7.6, 4.9, fill=NAVY, name="Fingerprint panel")
text(s, 0.95, 1.8, 7.0, 0.4, f"{len(R['runs'])} independent runs · result fingerprint (SHA-256)", 15, bold=True, color=WHITE)
for i, run in enumerate(R["runs"]):
    y = 2.45 + i * 0.66
    text(s, 0.95, y, 0.8, 0.45, f"#{run['run']}", 15, bold=True, color=GREY, anchor=MSO_ANCHOR.MIDDLE)
    tb = text(s, 1.65, y, 5.6, 0.45, run["fingerprint"][:40] + "…", 14, color=ICE, anchor=MSO_ANCHOR.MIDDLE)
    tb.text_frame.paragraphs[0].runs[0].font.name = "Courier New"
    circle_num(s, 7.4, y + 0.02, "✓", d=0.42, fill=GREEN, size=14)
text(s, 0.95, 5.85, 7.0, 0.45, "All runs identical, down to the last digit", 16, bold=True, color=WHITE)
pins = [("Method version", f"v{D['meta']['method_version']}"), ("Config hash", D["meta"]["config_hash"]),
        ("Data hash", D["meta"]["data_hash"]), ("Random seed", "fixed in config, one stream per promotion")]
text(s, 8.65, 1.6, 4.1, 0.4, "What is pinned", 20, bold=True, color=NAVY)
for i, (k, v) in enumerate(pins):
    y = 2.2 + i * 1.0
    box(s, 8.65, y, 4.1, 0.85, fill=CARD)
    text(s, 8.9, y + 0.1, 3.7, 0.3, k, 12, color=MUTED)
    text(s, 8.9, y + 0.4, 3.7, 0.4, v, 15, bold=True, color=INK)
text(s, 8.65, 6.25, 4.1, 0.5, "Automated tests: repeat runs, fresh load, run order, byte-identical data", 12, color=MUTED, italic=True)

# ================================================================ 11. gate
s = new_slide("A method change cannot ship unmeasured", notes="""
DEMO: Method-change gate page.
Methods evolve and someone always has a small improvement; the danger is a change that silently shifts every number.
Run "More bootstrap iterations": PASS, safe to ship.
Run "Match controls on format only": sounds sensible (more candidate stores) but it's BLOCKED: Summer Soda misses by 2.6 points. Stores in different regions grow at different rates, so the twins stop being twins.
"Use every untreated store": BLOCKED, only 2 of 12 recovered. Bigger isn't better if the comparison is unfair.
Build your own change, set tolerance to 50: G5 blocks a proposal that tries to loosen its own bar.
In GitHub, the same gate runs on every pull request; a BLOCK fails the build.
""")
G5 = D["gates"]
tbl_rows = len(G5) + 1
gt = s.shapes.add_table(tbl_rows, 4, Inches(0.6), Inches(1.55), Inches(7.9), Inches(0.6 * tbl_rows))
gt.name = "Gate results"
tbl = gt.table
widths = (3.2, 0.95, 2.25, 1.5)
for i, wv in enumerate(widths):
    tbl.columns[i].width = Inches(wv)
hdr = ("Proposed change", "Version", "Recovered", "Verdict")
for j, h in enumerate(hdr):
    c = tbl.cell(0, j)
    c.fill.solid()
    c.fill.fore_color.rgb = NAVY
    c.text = h
    r = c.text_frame.paragraphs[0].runs[0]
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(13), True, WHITE
for i, g in enumerate(G5, start=1):
    vals = (g["title"], f"v{g['version']}", f"{g['n_passed']}/12 · max {g['max_err']:.2f}pp", g["verdict"])
    for j, v in enumerate(vals):
        c = tbl.cell(i, j)
        c.fill.solid()
        c.fill.fore_color.rgb = WHITE if i % 2 else CARD
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        c.text = v
        r = c.text_frame.paragraphs[0].runs[0]
        r.font.name, r.font.size, r.font.color.rgb = FONT, Pt(13), INK
        if j == 3:
            r.font.bold = True
            r.font.color.rgb = GREEN if v == "PASS" else RED
            r.text = ("✓ " if v == "PASS" else "✕ ") + v
for i in range(tbl_rows):
    tbl.rows[i].height = Inches(0.6)
text(s, 0.6, 5.35, 7.9, 0.9, [[("The subtle one: ", {"bold": True}),
     ("“match on format only” sounds reasonable, but stores in other regions grow at different rates. "
      "It misses Summer Soda by 2.6pp, so the gate blocks it.", {})]], 14)
checks = [("G1", "Planted effects recovered within ±2pp"), ("G2", "Identical result across two runs"),
          ("G3", "Version bumped for any method change"), ("G4", "Reference data matches pinned checksums"),
          ("G5", "Proposal can't loosen its own tolerance")]
text(s, 8.95, 1.55, 3.8, 0.4, "Every change must pass", 18, bold=True, color=NAVY)
for i, (k, v) in enumerate(checks):
    y = 2.1 + i * 0.83
    box(s, 8.95, y, 3.8, 0.7, fill=CARD)
    circle_num(s, 9.08, y + 0.12, k, d=0.46, fill=BLUE, size=11)
    text(s, 9.7, y + 0.05, 2.95, 0.6, v, 13, color=INK, anchor=MSO_ANCHOR.MIDDLE)
text(s, 8.95, 6.35, 3.8, 0.4, "Runs on every pull request in CI", 12, italic=True, color=MUTED)

# ================================================================ 12. scorecard
cov = D["coverage"]["files"]["baseline.py"]
s = new_slide("All four success metrics are met", notes=f"""
Close the loop on the brief. Four success metrics, with the evidence for each:
1 Recovery within a stated tolerance: {sm['n_passed']}/{sm['n_promos']} within ±2pp; {CAL['share_within_tolerance']*100:.1f}% across {CAL['seeds']} simulated retailers.
2 Baseline-definition test coverage: {cov:.0f}% line coverage, every rule B1-B5 has its own test; CI enforces a 95% floor.
3 Reproducibility: identical fingerprints, every run.
4 Gate on a method change: good changes pass; plausible-but-wrong changes are blocked.
""")
score = [
    ("Recovery of the planted effect within a stated tolerance", f"{sm['n_passed']}/{sm['n_promos']} within ±2.0pp",
     f"Max error {sm['max_abs_error_pp']:.2f}pp; {CAL['share_within_tolerance'] * 100:.1f}% within tolerance across {CAL['seeds']} new worlds"),
    ("Baseline-definition test coverage", f"{cov:.0f}% line coverage",
     "Every rule B1–B5 has its own test; CI enforces a 95% floor on the baseline module"),
    ("Reproducibility of a result across runs", "Identical fingerprints",
     "Repeat runs, fresh data load and run order all give the same SHA-256 result hash"),
    ("Gate demonstration on a method change", "2 PASS · 3 BLOCK",
     "“Match on format only” blocked at 2.6pp; G5 stops a proposal loosening its own tolerance"),
]
for i, (m, v, e) in enumerate(score):
    col, row = i % 2, i // 2
    x, y = 0.6 + col * 6.15, 1.6 + row * 2.6
    box(s, x, y, 5.95, 2.35, fill=CARD, name=f"Metric {i + 1}")
    circle_num(s, x + 0.3, y + 0.3, "✓", d=0.55, fill=GREEN, size=18)
    text(s, x + 1.05, y + 0.3, 4.6, 0.6, m, 15, bold=True, color=MUTED)
    text(s, x + 1.05, y + 0.92, 4.6, 0.6, v, 26, bold=True, color=NAVY)
    text(s, x + 1.05, y + 1.55, 4.6, 0.7, e, 13, color=INK)

# ================================================================ 13. next steps
s = new_slide("From one argued number to one measured method", dark=True, notes="""
Close. Promotion reviews stop being an argument about whose spreadsheet is right: there's one method, written down, tested and versioned, and every number comes with its counterfactual and its margin of error.
Next steps:
1 Pilot on real sales alongside current reports, keeping the synthetic test as the permanent safety net.
2 Build holdout stores into promotion planning, so every format and region has twins.
3 Extend scope: halo, cannibalisation, post-promotion dip.
4 Bring the null false-positive rate (13% across 30 worlds) down to the 5% target; the gate is how we'd prove it.
5 Optional: AI phrasing for Ask, with the number check as a guardrail.
Then open for questions.
""")
nxt = [
    ("Pilot on real sales", "Run alongside today's reports; keep the synthetic test as the safety net"),
    ("Plan holdout stores", "Keep 3+ untreated stores per format × region in every promotion"),
    ("Widen the scope", "Halo, cannibalisation and the post-promotion dip"),
    ("Tighten the null rate", "13% false positives across 30 worlds → 5% target, proven through the gate"),
]
for i, (h, b) in enumerate(nxt):
    col, row = i % 2, i // 2
    x, y = 0.6 + col * 6.15, 1.75 + row * 2.0
    box(s, x, y, 5.95, 1.75, fill=NAVY_2, name=f"Next step {i + 1}")
    circle_num(s, x + 0.3, y + 0.3, i + 1, d=0.55, fill=ORANGE, size=18)
    text(s, x + 1.05, y + 0.28, 4.6, 0.5, h, 20, bold=True, color=WHITE)
    text(s, x + 1.05, y + 0.85, 4.6, 0.8, b, 14, color=ICE)
text(s, 0.6, 6.05, 12.1, 0.5, "Questions?   ·   Live app: http://127.0.0.1:8000   ·   Code, METHOD.md and tests in promo_attribution/",
     16, color=GREY)

assert _count == N_SLIDES, _count
prs.save(OUT)
print(f"Saved {OUT} ({_count} slides)")
