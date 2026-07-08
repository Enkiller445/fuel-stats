# -*- coding: utf-8 -*-
"""
Визуальные компоненты дашборда: палитра, KPI-плитки со спарклайнами, интерактивные
inline-SVG графики (crosshair + тултип) и HTML-обёртка. Без внешних библиотек.

Палитра — валидированная (data-viz): категориальная для видов топлива, статусная
для наличия; тема светлая/тёмная — осознанные шаги, не авто-инверсия.
"""

import html
import json
from datetime import datetime

# CSS-переменные цветов серий (тема переключается в :root/@media)
FUEL_VAR = {"АИ-92": "--f92", "АИ-95": "--f95", "АИ-98": "--f98",
            "АИ-100": "--f100", "ДТ": "--fdt"}
GRADE_VAR = {"92": "--f92", "95": "--f95", "98": "--f98", "100": "--f100", "ДТ": "--fdt"}
# статусы наличия
ST_GOOD, ST_WARN, ST_SERIOUS, ST_CRIT, ST_MUTED = (
    "--st-good", "--st-warn", "--st-serious", "--st-crit", "--muted")


# ------------------------------------------------------------------ format ---
def fmt(v, unit=""):
    if v is None:
        return "—"
    if isinstance(v, float):
        s = f"{int(v):,}".replace(",", " ") if v == int(v) else \
            f"{v:,.2f}".replace(",", " ").replace(".", ",")
    else:
        s = f"{v:,}".replace(",", " ")
    return s + unit


def pct(part, whole, digits=0):
    if not whole:
        return None
    return round(100 * part / whole, digits)


def short_dt(ts):
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").strftime("%d.%m %H:%M")
    except Exception:
        return ts


def _clean(vals):
    return [v for v in vals if v is not None]


# --------------------------------------------------------------- sparkline ---
def sparkline(points, var, w=104, h=30):
    pts = points
    real = _clean(pts)
    if len(real) < 2:
        return f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none"></svg>'
    lo, hi = min(real), max(real)
    rng = (hi - lo) or 1
    n = len(pts)
    pad = 3
    def X(i):
        return pad + (w - 2 * pad) * (i / (n - 1))
    def Y(v):
        return h - pad - (h - 2 * pad) * (v - lo) / rng
    poly = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(pts) if v is not None)
    last_i = max(i for i, v in enumerate(pts) if v is not None)
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
            f'<polyline points="{poly}" fill="none" style="stroke:var({ST_MUTED})" '
            f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" opacity="0.7"/>'
            f'<circle cx="{X(last_i):.1f}" cy="{Y(pts[last_i]):.1f}" r="2.6" '
            f'style="fill:var({var})"/></svg>')


# --------------------------------------------------------------- KPI tile ---
def kpi(label, value, prev, unit="", good_down=True, sub="", spark=None, var="--f95"):
    delta = '<span class="d flat">нет прошлого</span>'
    if value is not None and prev is not None:
        d = round(value - prev, 2)
        if abs(d) < 1e-9:
            delta = '<span class="d flat">= без изм.</span>'
        else:
            up = d > 0
            good = (not up) if good_down else up
            arrow = "↑" if up else "↓"
            delta = f'<span class="d {"good" if good else "bad"}">{arrow} {fmt(abs(d), unit)}</span>'
    spark_html = sparkline(spark, var) if spark and len(_clean(spark)) >= 2 else ""
    sub_html = f'<div class="sub">{html.escape(sub)}</div>' if sub else ""
    return (f'<div class="tile"><div class="t-label">{html.escape(label)}</div>'
            f'<div class="t-row"><div class="t-value">{fmt(value, unit)}</div>{spark_html}</div>'
            f'<div class="t-delta">{delta}</div>{sub_html}</div>')


# ------------------------------------------------------------------- meter ---
def meter(share, var, height=8):
    p = 0 if share is None else max(0, min(100, share))
    return (f'<div class="meter" style="height:{height}px">'
            f'<div class="meter-fill" style="width:{p:.0f}%;background:var({var})"></div></div>')


def arrow(cur, prev, good_down=False, unit=""):
    """Стрелка тренда: цвет = направление × хорошо ли это."""
    if cur is None or prev is None:
        return ""
    d = round(cur - prev, 2)
    if abs(d) < 1e-9:
        return '<span class="d flat">=</span>'
    up = d > 0
    good = (not up) if good_down else up
    return f'<span class="d {"good" if good else "bad"}">{"↑" if up else "↓"} {fmt(abs(d), unit)}</span>'


# ------------------------------------------------------------------ legend ---
def legend(items):
    # items: [(name, cssvar, kind)] kind='line'|'rect'
    sp = ""
    for name, var, *rest in items:
        kind = rest[0] if rest else "line"
        key = (f'<span class="k-line" style="background:var({var})"></span>' if kind == "line"
               else f'<span class="k-rect" style="background:var({var})"></span>')
        sp += f'<span class="lg">{key}{html.escape(name)}</span>'
    return f'<div class="legend">{sp}</div>'


# -------------------------------------------------------------- line chart ---
def line_chart(chart_id, labels, series, unit="", area=False, y_int=False,
               height=270, end_labels=True):
    """
    series: [{'name','var','points':[y|None,...]}]
    Возвращает интерактивный график: сетка, заливка (area), линии, конечные точки/подписи,
    прозрачный слой для наведения; crosshair+тултип рисует общий JS (см. wrap()).
    """
    W, H = 860, height
    padL, padR, padT, padB = 52, 58, 14, 34
    plotW, plotH = W - padL - padR, H - padT - padB

    ys_all = [y for s in series for y in s["points"] if y is not None]
    if not ys_all:
        return '<div class="empty">Пока нет данных</div>'
    ymin, ymax = min(ys_all), max(ys_all)
    if ymin == ymax:
        ymin -= 1
        ymax += 1
    padv = (ymax - ymin) * 0.14
    ymin, ymax = ymin - padv, ymax + padv
    if y_int:
        ymin = max(0, ymin)

    n = len(labels)
    def X(i):
        return padL + (plotW * (i / (n - 1)) if n > 1 else plotW / 2)
    def Y(v):
        return padT + plotH * (1 - (v - ymin) / (ymax - ymin))

    P = [f'<svg viewBox="0 0 {W} {H}" class="chart" data-chart-id="{chart_id}" '
         f'preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">']

    # сетка + подписи Y
    for k in range(5):
        val = ymin + (ymax - ymin) * k / 4
        y = Y(val)
        P.append(f'<line class="grid" x1="{padL}" y1="{y:.1f}" x2="{W-padR}" y2="{y:.1f}"/>')
        lab = f"{val:.0f}" if y_int else f"{val:,.1f}".replace(",", " ").replace(".", ",")
        P.append(f'<text class="ylab" x="{padL-8}" y="{y+4:.1f}">{lab}</text>')

    # подписи X
    idxs = sorted(set([0, n - 1] + [round(n * f) for f in (0.25, 0.5, 0.75)]
                      if n > 4 else range(n)))
    for i in [i for i in idxs if 0 <= i < n]:
        anc = "start" if i == 0 else ("end" if i == n - 1 else "middle")
        P.append(f'<text class="xlab" x="{X(i):.1f}" y="{H-12}" '
                 f'style="text-anchor:{anc}">{html.escape(labels[i])}</text>')

    # area (только для одиночной серии) + линии
    for s in series:
        pts = s["points"]
        v = s["var"]
        if area and len(series) == 1:
            seg = [(i, y) for i, y in enumerate(pts) if y is not None]
            if len(seg) > 1:
                top = " ".join(f"{X(i):.1f},{Y(y):.1f}" for i, y in seg)
                base = f"{X(seg[-1][0]):.1f},{Y(ymin):.1f} {X(seg[0][0]):.1f},{Y(ymin):.1f}"
                P.append(f'<polygon points="{top} {base}" style="fill:var({v})" opacity="0.10"/>')
        poly = [f"{X(i):.1f},{Y(y):.1f}" for i, y in enumerate(pts) if y is not None]
        if len(poly) > 1:
            P.append(f'<polyline points="{" ".join(poly)}" fill="none" '
                     f'style="stroke:var({v})" stroke-width="2" '
                     f'stroke-linejoin="round" stroke-linecap="round"/>')
        # конечная точка + прямая подпись
        real = [i for i, y in enumerate(pts) if y is not None]
        if real:
            li = real[-1]
            P.append(f'<circle class="enddot" cx="{X(li):.1f}" cy="{Y(pts[li]):.1f}" r="3.5" '
                     f'style="fill:var({v})"/>')
            if end_labels:
                P.append(f'<text class="endlab" x="{X(li)+7:.1f}" y="{Y(pts[li])+3.5:.1f}" '
                         f'style="fill:var({v})">{html.escape(s["name"])}</text>')

    # crosshair-слой + прозрачный hit-rect
    P.append(f'<g class="xhair" data-cid="{chart_id}"></g>')
    P.append(f'<rect class="hit" x="{padL}" y="{padT}" width="{plotW}" height="{plotH}" '
             f'fill="transparent"/>')
    P.append("</svg>")

    # данные для JS (значения + пиксельные координаты)
    data = {
        "xs": [round(X(i), 1) for i in range(n)],
        "labels": labels,
        "unit": unit,
        "series": [{
            "name": s["name"], "var": s["var"],
            "vals": s["points"],
            "ys": [None if y is None else round(Y(y), 1) for y in s["points"]],
        } for s in series],
        "geo": {"top": padT, "bottom": padT + plotH, "W": W, "H": H},
    }
    # JSON внутри <script> — экранируем только '<' (энтити в script не декодируются)
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return (f'<div class="chartbox">' + "".join(P) +
            f'<div class="tip" id="tip-{chart_id}" hidden></div>'
            f'<script type="application/json" class="cdata" '
            f'data-for="{chart_id}">{payload}</script></div>')


# --------------------------------------------------------------------- wrap ---
def wrap(title, body):
    return _HEAD + html.escape(title) + _MID + body + _TAIL


_STYLE = """
:root{
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --baseline:#c3c2b7; --border:rgba(11,11,11,.10);
  --good:#006300; --bad:#c0392b;
  --f92:#2a78d6; --f95:#1baf7a; --f98:#eda100; --f100:#008300; --fdt:#4a3aa7;
  --st-good:#0ca30c; --st-warn:#e0920a; --st-serious:#ec835a; --st-crit:#d03b3b;
}
@media (prefers-color-scheme:dark){:root{
  --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10);
  --good:#0ca30c; --bad:#e66767;
  --f92:#3987e5; --f95:#199e70; --f98:#c98500; --f100:#008300; --fdt:#9085e9;
  --st-good:#0ca30c; --st-warn:#fab219; --st-serious:#ec835a; --st-crit:#d03b3b;
}}
*{box-sizing:border-box}
body{margin:0 auto;max-width:1160px;background:var(--page);color:var(--ink);
  font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:26px 22px 40px}
h1{margin:0 0 4px;font-size:25px;font-weight:680;letter-spacing:-.02em}
.meta{color:var(--muted);font-size:13px;margin-bottom:14px}
.sec{margin:26px 0 12px;font-size:13px;font-weight:600;letter-spacing:.04em;
  text-transform:uppercase;color:var(--muted)}
.banner{background:#fff4d6;color:#7c5b12;border:1px solid #f0d98a;border-radius:12px;
  padding:11px 14px;margin-bottom:16px;font-size:13px;line-height:1.5}
@media (prefers-color-scheme:dark){.banner{background:#332a10;color:#f0d98a;border-color:#5a4a1a}}
.hero{display:grid;grid-template-columns:1.4fr 1fr;gap:16px;margin-bottom:8px}
@media(max-width:720px){.hero{grid-template-columns:1fr}}
.card{background:var(--surface);border:1px solid var(--border);border-radius:16px;
  padding:16px 18px;margin-bottom:14px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.card h2{margin:0 0 6px;font-size:15px;font-weight:640}
.hint{color:var(--muted);font-weight:400;font-size:12px}
.tiles{display:grid;gap:12px;margin-bottom:14px}
.tiles.c5{grid-template-columns:repeat(5,1fr)} .tiles.c4{grid-template-columns:repeat(4,1fr)}
@media(max-width:820px){.tiles.c5,.tiles.c4{grid-template-columns:repeat(2,1fr)}}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:13px 15px}
.t-label{color:var(--ink2);font-size:12.5px;margin-bottom:7px}
.t-row{display:flex;align-items:flex-end;justify-content:space-between;gap:8px}
.t-value{font-size:25px;font-weight:670;letter-spacing:-.02em;line-height:1}
.spark{width:104px;height:30px;flex:0 0 auto}
.t-delta{margin-top:6px}
.d{font-size:12.5px;font-weight:640} .d.good{color:var(--good)} .d.bad{color:var(--bad)}
.d.flat{color:var(--muted);font-weight:500}
.sub{color:var(--muted);font-size:11.5px;margin-top:6px}
.hero-num{font-size:52px;font-weight:700;letter-spacing:-.03em;line-height:1}
.situation{display:flex;align-items:center;gap:14px;flex-wrap:wrap;background:var(--surface);
  border:1px solid var(--border);border-radius:14px;padding:12px 16px;margin-bottom:16px;font-size:13.5px}
.situation .lead{font-weight:660;font-size:15px}
.situation .pill{display:inline-flex;align-items:center;gap:6px;color:var(--ink2)}
.situation .pill .dot{width:9px;height:9px;border-radius:50%}
.fuelgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:16px}
@media(max-width:900px){.fuelgrid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:520px){.fuelgrid{grid-template-columns:1fr}}
.fuelcard{background:var(--surface);border:1px solid var(--border);border-radius:16px;
  padding:14px 15px 13px;position:relative;overflow:hidden}
.fuelcard::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--accent)}
.fc-head{display:flex;align-items:center;gap:8px;margin-bottom:9px}
.fc-dot{width:10px;height:10px;border-radius:50%;flex:0 0 auto}
.fc-name{font-weight:660;font-size:14px}
.fc-price{display:flex;align-items:flex-end;justify-content:space-between;gap:6px}
.fc-val{font-size:24px;font-weight:680;letter-spacing:-.02em;line-height:1}
.fc-sub{color:var(--muted);font-size:11px;margin-top:4px}
.fc-avail{margin-top:11px;padding-top:10px;border-top:1px solid var(--border)}
.fc-arow{display:flex;align-items:baseline;justify-content:space-between;font-size:12.5px}
.fc-arow .lbl{color:var(--ink2)} .fc-arow .num{font-weight:640;font-variant-numeric:tabular-nums}
.meter{width:100%;background:var(--grid);border-radius:99px;overflow:hidden;margin:5px 0 2px}
.meter-fill{height:100%;border-radius:99px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px} @media(max-width:820px){.grid2{grid-template-columns:1fr}}
.chartbox{position:relative}
.chart{width:100%;height:auto;display:block;touch-action:none}
.chart .grid{stroke:var(--grid);stroke-width:1}
.chart .ylab,.chart .xlab{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.chart .ylab{text-anchor:end}.chart .xlab{text-anchor:middle}
.chart .endlab{font-size:11px;font-weight:600}
.chart .xh-line{stroke:var(--baseline);stroke-width:1}
.chart .xh-dot{stroke:var(--surface);stroke-width:2}
.legend{display:flex;gap:15px;flex-wrap:wrap;margin-bottom:6px}
.lg{color:var(--ink2);font-size:12.5px;display:flex;align-items:center;gap:6px}
.k-line{width:14px;height:3px;border-radius:2px;display:inline-block}
.k-rect{width:11px;height:11px;border-radius:3px;display:inline-block}
.tip{position:absolute;pointer-events:none;background:var(--surface);color:var(--ink);
  border:1px solid var(--border);border-radius:10px;padding:8px 10px;font-size:12px;
  box-shadow:0 4px 14px rgba(0,0,0,.14);min-width:130px;z-index:5}
.tip .tt-x{color:var(--muted);font-size:11px;margin-bottom:5px}
.tip .tt-row{display:flex;align-items:center;gap:7px;justify-content:space-between;margin-top:2px}
.tip .tt-l{display:flex;align-items:center;gap:6px;color:var(--ink2)}
.tip .tt-k{width:12px;height:3px;border-radius:2px} .tip .tt-v{font-weight:660;font-variant-numeric:tabular-nums}
.tablewrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
table.tbl{width:100%;border-collapse:collapse;font-size:13px;min-width:640px}
.tbl th{text-align:right;color:var(--muted);font-weight:500;font-size:11.5px;
  padding:7px 9px;border-bottom:1px solid var(--border);white-space:nowrap}
.tbl th:first-child,.tbl td:first-child{text-align:left}
.tbl td{padding:8px 9px;border-bottom:1px solid var(--border);text-align:right;
  font-variant-numeric:tabular-nums;white-space:nowrap}
.tbl td.b{font-weight:600;font-variant-numeric:normal}
.tbl .c{color:var(--muted);font-size:11px}
.tbl tbody tr:hover{background:rgba(127,127,127,.06)}
.bar{display:inline-block;height:7px;border-radius:3px;vertical-align:middle}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:12px}
.chip .dot{width:8px;height:8px;border-radius:50%}
.empty{color:var(--muted);padding:26px;text-align:center}
.foot{color:var(--muted);font-size:12px;margin-top:20px;line-height:1.6}
"""

_SCRIPT = """
<script>
(function(){
  function esc(t){var d=document.createElement('div');d.textContent=t==null?'':String(t);return d.innerHTML;}
  function fmtNum(v){if(v==null)return '—';var s;if(Math.abs(v-Math.round(v))<1e-9){s=Math.round(v).toLocaleString('ru-RU');}else{s=v.toLocaleString('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2});}return s;}
  document.querySelectorAll('.cdata').forEach(function(node){
    var d; try{d=JSON.parse(node.textContent);}catch(e){return;}
    var id=node.getAttribute('data-for');
    var box=node.closest('.chartbox');
    var svg=box.querySelector('.chart[data-chart-id="'+id+'"]');
    var xh=svg.querySelector('.xhair');
    var hit=svg.querySelector('.hit');
    var tip=box.querySelector('#tip-'+id);
    var geo=d.geo;
    function toViewX(evt){
      var pt=svg.createSVGPoint();pt.x=evt.clientX;pt.y=evt.clientY;
      var m=svg.getScreenCTM();if(!m)return null;var p=pt.matrixTransform(m.inverse());return p.x;
    }
    function nearest(vx){var best=0,bd=1e9;for(var i=0;i<d.xs.length;i++){var dd=Math.abs(d.xs[i]-vx);if(dd<bd){bd=dd;best=i;}}return best;}
    function show(evt){
      var vx=toViewX(evt);if(vx==null)return;var i=nearest(vx);var x=d.xs[i];
      var parts='<line class="xh-line" x1="'+x+'" y1="'+geo.top+'" x2="'+x+'" y2="'+geo.bottom+'"/>';
      var rows='';
      d.series.forEach(function(s){
        if(s.ys[i]==null)return;
        parts+='<circle class="xh-dot" cx="'+x+'" cy="'+s.ys[i]+'" r="4" style="fill:var('+s.var+')"/>';
        rows+='<div class="tt-row"><span class="tt-l"><span class="tt-k" style="background:var('+s.var+')"></span>'+esc(s.name)+'</span><span class="tt-v">'+fmtNum(s.vals[i])+esc(d.unit)+'</span></div>';
      });
      xh.innerHTML=parts;
      tip.innerHTML='<div class="tt-x">'+esc(d.labels[i])+'</div>'+rows;
      tip.hidden=false;
      var r=svg.getBoundingClientRect();
      var px=r.left+ (x/geo.W)*r.width;
      var left=px - r.left + 14;
      if(left> r.width-150) left=left-160;
      tip.style.left=Math.max(4,left)+'px';
      tip.style.top='8px';
    }
    function hide(){xh.innerHTML='';tip.hidden=true;}
    hit.addEventListener('pointermove',show);
    hit.addEventListener('pointerdown',show);
    hit.addEventListener('pointerleave',hide);
    svg.addEventListener('pointerleave',hide);
  });
})();
</script>
"""

_HEAD = ('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
         '<meta name="viewport" content="width=device-width, initial-scale=1"><title>')
_MID = ('</title><style>' + _STYLE + '</style></head><body>')
_TAIL = (_SCRIPT + '</body></html>')
