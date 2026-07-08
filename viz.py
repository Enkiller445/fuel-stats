# -*- coding: utf-8 -*-
"""
Общие компоненты для дашбордов (petrolplus и gdebenz):
форматирование, KPI-плитки, inline-SVG графики и HTML-обёртка со стилями.
Никаких внешних зависимостей — всё рисуется вручную, файл автономный.
"""

import html
from datetime import datetime


def fmt(v, unit=""):
    if v is None:
        return "—"
    if isinstance(v, float):
        if v == int(v):                       # целое число без дробной части
            s = f"{int(v):,}".replace(",", " ")
        else:
            s = f"{v:,.2f}".replace(",", " ").replace(".", ",")
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


def legend(items):
    sp = "".join(
        f'<span class="lg"><i style="background:{c}"></i>{html.escape(n)}</span>'
        for n, c in items
    )
    return f'<div class="legend">{sp}</div>'


def kpi(title, cur, prev, unit="", good_down=True, sub=""):
    val = fmt(cur, unit)
    delta_html = '<div class="delta flat">— нет предыдущего замера</div>'
    if cur is not None and prev is not None:
        d = round(cur - prev, 2)
        if abs(d) < 1e-9:
            delta_html = '<div class="delta flat">без изменений</div>'
        else:
            up = d > 0
            good = (not up) if good_down else up
            arrow = "▲" if up else "▼"
            cls = "good" if good else "bad"
            delta_html = f'<div class="delta {cls}">{arrow} {fmt(abs(d), unit)}</div>'
    sub_html = f'<div class="sub">{html.escape(sub)}</div>' if sub else ""
    return (f'<div class="kpi"><div class="kpi-t">{html.escape(title)}</div>'
            f'<div class="kpi-v">{val}</div>{delta_html}{sub_html}</div>')


def line_chart(labels, series, band=None, unit="", height=260, y_int=False):
    """
    labels: подписи X (str)
    series: [{'name','color','points':[y|None,...]}]
    band:   (lows[], highs[]) — заливка коридора
    """
    W, H = 820, height
    padL, padR, padT, padB = 54, 16, 16, 34
    plotW, plotH = W - padL - padR, H - padT - padB

    ys = [y for s in series for y in s["points"] if y is not None]
    if band:
        ys += [y for y in band[0] if y is not None] + [y for y in band[1] if y is not None]
    if not ys:
        return '<div class="empty">Пока нет данных для графика</div>'
    ymin, ymax = min(ys), max(ys)
    if ymin == ymax:
        ymin -= 1
        ymax += 1
    padv = (ymax - ymin) * 0.12
    ymin, ymax = ymin - padv, ymax + padv
    if y_int:
        ymin = max(0, ymin)

    n = len(labels)
    def X(i):
        return padL + (plotW * (i / (n - 1)) if n > 1 else plotW / 2)
    def Y(v):
        return padT + plotH * (1 - (v - ymin) / (ymax - ymin))

    parts = [f'<svg viewBox="0 0 {W} {H}" class="chart" preserveAspectRatio="xMidYMid meet" '
             f'xmlns="http://www.w3.org/2000/svg">']
    for k in range(5):
        val = ymin + (ymax - ymin) * k / 4
        y = Y(val)
        parts.append(f'<line x1="{padL}" y1="{y:.1f}" x2="{W-padR}" y2="{y:.1f}" class="grid"/>')
        lab = f"{val:.0f}" if y_int else f"{val:,.1f}".replace(",", " ").replace(".", ",")
        parts.append(f'<text x="{padL-8}" y="{y+4:.1f}" class="ylab">{lab}</text>')

    idxs = sorted(set([0, n - 1] + [round(n * f) for f in (0.25, 0.5, 0.75)] if n > 4 else range(n)))
    idxs = [i for i in idxs if 0 <= i < n]
    for i in idxs:
        anchor = "start" if i == 0 else ("end" if i == n - 1 else "middle")
        parts.append(f'<text x="{X(i):.1f}" y="{H-12}" class="xlab" '
                     f'style="text-anchor:{anchor}">{html.escape(labels[i])}</text>')

    if band:
        lows, highs = band
        pts_top = [f"{X(i):.1f},{Y(highs[i]):.1f}" for i in range(n) if highs[i] is not None]
        pts_bot = [f"{X(i):.1f},{Y(lows[i]):.1f}" for i in range(n) if lows[i] is not None][::-1]
        if len(pts_top) > 1:
            parts.append(f'<polygon points="{" ".join(pts_top+pts_bot)}" '
                         f'fill="{series[0]["color"]}" opacity="0.08"/>')

    for s in series:
        poly = [f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(s["points"]) if v is not None]
        if len(poly) > 1:
            parts.append(f'<polyline points="{" ".join(poly)}" fill="none" '
                         f'stroke="{s["color"]}" stroke-width="2.5" '
                         f'stroke-linejoin="round" stroke-linecap="round"/>')
        for i, v in enumerate(s["points"]):
            if v is None:
                continue
            tip = f'{html.escape(labels[i])}: {fmt(v)}{unit}'
            parts.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3.4" '
                         f'fill="{s["color"]}"><title>{tip}</title></circle>')
    parts.append("</svg>")
    return "".join(parts)


def wrap(title, body):
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  --bg:#f6f7f9; --card:#ffffff; --ink:#0f172a; --mut:#64748b; --line:#e5e7eb;
  --good:#059669; --bad:#dc2626; --shadow:0 1px 3px rgba(0,0,0,.06),0 1px 2px rgba(0,0,0,.04);
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#0b1220; --card:#111a2e; --ink:#e6edf6; --mut:#93a2b8; --line:#1e2a44;
    --shadow:0 1px 3px rgba(0,0,0,.4); }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0 auto; max-width:1120px; background:var(--bg); color:var(--ink);
  font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; padding:24px; }}
header h1 {{ margin:0 0 4px; font-size:24px; letter-spacing:-.02em; }}
.meta {{ color:var(--mut); font-size:13px; margin-bottom:16px; }}
.tabs {{ display:flex; gap:8px; margin-bottom:18px; }}
.tabs a {{ text-decoration:none; font-size:13px; padding:6px 12px; border-radius:999px;
  border:1px solid var(--line); color:var(--mut); background:var(--card); }}
.tabs a.on {{ color:#fff; background:#2563eb; border-color:#2563eb; }}
.sec {{ margin:20px 0 10px; font-size:16px; letter-spacing:-.01em; }}
.sec .hint {{ font-size:12px; }}
.banner {{ background:#fef3c7; color:#7c5b12; border:1px solid #f0d98a; border-radius:12px;
  padding:10px 14px; margin-bottom:16px; font-size:13px; line-height:1.5; }}
@media (prefers-color-scheme: dark) {{
  .banner {{ background:#3a2f10; color:#f0d98a; border-color:#5a4a1a; }}
}}
.kpis {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:18px; }}
.kpis.five {{ grid-template-columns:repeat(5,1fr); }}
.tablewrap {{ overflow-x:auto; -webkit-overflow-scrolling:touch; }}
table.brands {{ min-width:560px; }}
.kpi {{ background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:14px 16px; box-shadow:var(--shadow); }}
.kpi-t {{ color:var(--mut); font-size:12.5px; margin-bottom:6px; }}
.kpi-v {{ font-size:26px; font-weight:650; letter-spacing:-.02em; }}
.delta {{ font-size:13px; font-weight:600; margin-top:2px; }}
.delta.good {{ color:var(--good); }} .delta.bad {{ color:var(--bad); }}
.delta.flat {{ color:var(--mut); font-weight:500; }}
.sub {{ color:var(--mut); font-size:11.5px; margin-top:6px; }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:14px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:16px 18px; box-shadow:var(--shadow); margin-bottom:14px; }}
.card h2 {{ margin:0 0 10px; font-size:15.5px; }}
.hint {{ color:var(--mut); font-weight:400; font-size:12px; }}
.chart {{ width:100%; height:auto; display:block; }}
.grid {{ stroke:var(--line); stroke-width:1; }}
.ylab {{ fill:var(--mut); font-size:11px; text-anchor:end; }}
.xlab {{ fill:var(--mut); font-size:11px; text-anchor:middle; }}
.legend {{ display:flex; gap:16px; margin-bottom:6px; flex-wrap:wrap; }}
.lg {{ color:var(--mut); font-size:12.5px; display:flex; align-items:center; gap:6px; }}
.lg i {{ width:11px; height:11px; border-radius:3px; display:inline-block; }}
table.brands {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
.brands th {{ text-align:left; color:var(--mut); font-weight:500; font-size:12px;
  padding:6px 8px; border-bottom:1px solid var(--line); }}
.brands td {{ padding:7px 8px; border-bottom:1px solid var(--line); }}
.brands td.b {{ font-weight:600; }}
.brands td.num {{ text-align:right; white-space:nowrap; }}
.brands .c {{ color:var(--mut); font-size:11px; }}
.empty {{ color:var(--mut); padding:30px; text-align:center; }}
.foot {{ color:var(--mut); font-size:12px; margin-top:18px; line-height:1.6; }}
@media (max-width:820px) {{
  .kpis, .kpis.five {{ grid-template-columns:1fr 1fr; }} .grid2 {{ grid-template-columns:1fr; }}
}}
</style>
</head>
<body>
{body}
</body></html>"""
