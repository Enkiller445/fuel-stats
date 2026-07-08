# -*- coding: utf-8 -*-
"""
Сборка ЕДИНОЙ страницы дашборда index.html из data/history.csv + latest_*.json.
Автономный HTML (inline-SVG, без интернета и библиотек), тема светлая/тёмная.

Разделы: плитки цен по видам топлива, график динамики цен, доступность АЗС
(petrolplus), наличие бензина (gdebenz), марки в наличии сейчас, таблицы по сетям.
"""

import html
import json
import os
from statistics import median

import store
import viz

FUEL_COLORS = {
    "АИ-92": "#0891b2", "АИ-95": "#2563eb", "АИ-98": "#9333ea",
    "АИ-100": "#db2777", "ДТ": "#64748b",
}
GRADE_COLORS = {"92": "#0891b2", "95": "#2563eb", "98": "#9333ea",
                "100": "#db2777", "ДТ": "#64748b"}
C_YES, C_NO, C_Q, C_LOW, C_TOTAL = "#059669", "#dc2626", "#d97706", "#eab308", "#94a3b8"


def _cfg(base):
    with open(os.path.join(base, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def _series(hist, col):
    return [r.get(col) for r in hist]


def _stale_banner(status):
    bits = []
    for key, label in (("prices", "Цены (petrolplus)"), ("gdebenz", "Наличие (gdebenz)")):
        s = status.get(key) or {}
        if s.get("ok") is False:
            err = (s.get("error") or "")[:120]
            bits.append(f"{label}: последний сбор не удался ({html.escape(err)}) — "
                        f"показаны прошлые данные.")
    if not bits:
        return ""
    return '<div class="banner">⚠ ' + "<br>".join(bits) + "</div>"


def build(base_dir):
    cfg = _cfg(base_dir)
    hist = store.load_history()
    lp = store.load_json(store.LATEST_PRICES) or {}
    lg = store.load_json(store.LATEST_GDEBENZ) or {}
    status = store.load_json(store.STATUS) or {}
    out_path = os.path.join(base_dir, "index.html")

    price_fuels = cfg.get("price_fuels", [])
    grades = cfg.get("gdebenz_grades", [])

    if not hist:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(viz.wrap("Бензин · дашборд", "<p class='empty'>Данных ещё нет.</p>"))
        return out_path

    labels = [viz.short_dt(r["ts_msk"]) for r in hist]
    last, prev = hist[-1], (hist[-2] if len(hist) > 1 else None)

    def cur(col):
        return last.get(col)

    def pre(col):
        return prev.get(col) if prev else None

    # --- плитки цен ---
    tiles = []
    for fuel in price_fuels:
        med = cur(f"p_med_{fuel}")
        n = cur(f"p_n_{fuel}")
        p10, p90 = cur(f"p_p10_{fuel}"), cur(f"p_p90_{fuel}")
        sub = (f"{viz.fmt(int(n) if n else 0)} АЗС · p10–p90 "
               f"{viz.fmt(p10)}–{viz.fmt(p90)}") if med is not None else "нет данных"
        tiles.append(viz.kpi(fuel, med, pre(f"p_med_{fuel}"), " ₽", sub=sub))
    fuel_tiles = f'<section class="kpis five">{"".join(tiles)}</section>'

    # --- плитки доступности/наличия ---
    av_tiles = "".join([
        viz.kpi("Доступных АЗС", cur("azs_available"), pre("azs_available"),
                good_down=False,
                sub=f"из {viz.fmt(int(cur('azs_total')) if cur('azs_total') else 0)} АЗС · petrolplus"),
        viz.kpi("Есть бензин сейчас", cur("gb_yes"), pre("gb_yes"), good_down=False,
                sub="АЗС со статусом «есть» · gdebenz"),
        viz.kpi("Нет бензина", cur("gb_no"), pre("gb_no"), good_down=True,
                sub="АЗС со статусом «нет» · gdebenz"),
        viz.kpi("Очереди", cur("gb_queue"), pre("gb_queue"), good_down=True,
                sub="АЗС со статусом «очередь» · gdebenz"),
    ])
    av_tiles = f'<section class="kpis">{av_tiles}</section>'

    # --- график цен ---
    price_series = [{"name": f, "color": FUEL_COLORS.get(f, "#2563eb"),
                     "points": _series(hist, f"p_med_{f}")} for f in price_fuels]
    chart_prices = viz.line_chart(labels, price_series, unit=" ₽")
    price_legend = viz.legend([(f, FUEL_COLORS.get(f, "#2563eb")) for f in price_fuels])

    # --- доступность petrolplus ---
    chart_avail = viz.line_chart(labels, [
        {"name": "Доступные", "color": C_YES, "points": _series(hist, "azs_available")},
        {"name": "Всего", "color": C_TOTAL, "points": _series(hist, "azs_total")},
    ], y_int=True)

    # --- наличие gdebenz ---
    chart_status = viz.line_chart(labels, [
        {"name": "Есть", "color": C_YES, "points": _series(hist, "gb_yes")},
        {"name": "Нет", "color": C_NO, "points": _series(hist, "gb_no")},
        {"name": "Очередь", "color": C_Q, "points": _series(hist, "gb_queue")},
        {"name": "Мало", "color": C_LOW, "points": _series(hist, "gb_low")},
    ], y_int=True)

    # --- марки в наличии сейчас (gdebenz) ---
    now_series = [{"name": f"АИ-{g}" if g != "ДТ" else "ДТ",
                   "color": GRADE_COLORS.get(g, "#2563eb"),
                   "points": _series(hist, f"gb_now_{g}")} for g in grades]
    chart_now = viz.line_chart(labels, now_series, y_int=True)
    now_legend = viz.legend([(f"АИ-{g}" if g != "ДТ" else "ДТ",
                              GRADE_COLORS.get(g, "#2563eb")) for g in grades])

    # свежесть
    ps = status.get("prices") or {}
    gs = status.get("gdebenz") or {}
    meta = (f"Цены: <b>{html.escape(viz.short_dt(ps.get('ts_msk','')) or '—')}</b> · "
            f"Наличие: <b>{html.escape(viz.short_dt(gs.get('ts_msk','')) or '—')}</b> МСК · "
            f"замеров: <b>{len(hist)}</b> · {html.escape(cfg.get('region_name',''))}")

    body = f"""
    <header>
      <h1>Бензин · Москва и ближнее Подмосковье</h1>
      <div class="meta">{meta}</div>
    </header>
    {_stale_banner(status)}

    <h3 class="sec">Цены по видам топлива <span class="hint">медиана · последний замер</span></h3>
    {fuel_tiles}

    <section class="card"><h2>Динамика цен <span class="hint">медиана по АЗС, ₽</span></h2>
      {price_legend}{chart_prices}</section>

    <h3 class="sec">Доступность и наличие</h3>
    {av_tiles}
    <section class="grid2">
      <div class="card"><h2>Доступность АЗС <span class="hint">petrolplus · «высокая доступность»</span></h2>
        {viz.legend([("Доступные", C_YES), ("Всего", C_TOTAL)])}{chart_avail}</div>
      <div class="card"><h2>Наличие бензина <span class="hint">gdebenz · статусы АЗС</span></h2>
        {viz.legend([("Есть", C_YES), ("Нет", C_NO), ("Очередь", C_Q), ("Мало", C_LOW)])}{chart_status}</div>
    </section>

    <section class="card"><h2>Какие марки есть сейчас <span class="hint">gdebenz · число АЗС с маркой в наличии</span></h2>
      {now_legend}{chart_now}</section>

    <section class="card"><h2>Цены по сетям <span class="hint">последний замер · медиана, ₽ (число АЗС)</span></h2>
      {price_brand_table(lp, price_fuels)}</section>

    <section class="card"><h2>Наличие по сетям <span class="hint">последний замер · gdebenz</span></h2>
      {gdebenz_brand_table(lg)}</section>

    <p class="foot">
      Цены — petrolplus / АЗС-Локатор (выгрузка StationList.xls). АИ-98/100 продаются на
      небольшом числе АЗС и публикуются редко — ряды могут быть разреженными (число АЗС
      указано у каждой цифры). Наличие — gdebenz.ru, данные краудсорсные (сообщают
      пользователи), это оценка «снизу». Обе величины справочные.
    </p>
    """
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(viz.wrap(f"Бензин · {viz.short_dt(last['ts_msk'])}", body))
    return out_path


def price_brand_table(lp, fuels):
    stations = lp.get("stations", []) if lp else []
    if not stations:
        return "<div class='empty'>Нет снимка цен</div>"
    agg = {}
    for s in stations:
        a = agg.setdefault(s.get("brand") or "—",
                           {"n": 0, "avail": 0, "p": {f: [] for f in fuels}})
        a["n"] += 1
        if s.get("available"):
            a["avail"] += 1
        for f in fuels:
            v = (s.get("prices") or {}).get(f)
            if v is not None:
                a["p"][f].append(v)
    head = "".join(f"<th>{html.escape(f)}</th>" for f in fuels)
    trs = []
    for b, a in sorted(agg.items(), key=lambda kv: -kv[1]["n"])[:15]:
        cells = ""
        for f in fuels:
            vals = a["p"][f]
            cells += (f"<td class='num'>{viz.fmt(round(median(vals),2),' ₽')}"
                      f"<span class='c'> · {len(vals)}</span></td>") if vals else "<td class='num'>—</td>"
        trs.append(f"<tr><td class='b'>{html.escape(b)}</td><td>{a['n']}</td>"
                   f"<td>{a['avail']}</td>{cells}</tr>")
    return ("<div class='tablewrap'><table class='brands'><thead><tr>"
            "<th>Сеть</th><th>АЗС</th><th>Доступно</th>" + head +
            "</tr></thead><tbody>" + "".join(trs) + "</tbody></table></div>")


def gdebenz_brand_table(lg):
    stations = lg.get("stations", []) if lg else []
    if not stations:
        return "<div class='empty'>Нет снимка наличия</div>"
    agg = {}
    for s in stations:
        a = agg.setdefault(s.get("brand") or "—", {"n": 0, "yes": 0, "no": 0, "g95": 0, "g98": 0})
        a["n"] += 1
        if s.get("status") == "yes":
            a["yes"] += 1
        elif s.get("status") == "no":
            a["no"] += 1
        fs = {x.strip() for x in (s.get("fuels_now") or "").split(",") if x.strip()}
        a["g95"] += "95" in fs
        a["g98"] += "98" in fs
    trs = []
    for b, a in sorted(agg.items(), key=lambda kv: -kv[1]["n"])[:15]:
        share = viz.pct(a["yes"], a["yes"] + a["no"])
        trs.append(f"<tr><td class='b'>{html.escape(b)}</td><td>{a['n']}</td>"
                   f"<td>{a['yes']}</td><td>{a['no']}</td>"
                   f"<td class='num'>{viz.fmt(share)}%</td>"
                   f"<td class='num'>{a['g95']}</td><td class='num'>{a['g98']}</td></tr>")
    return ("<div class='tablewrap'><table class='brands'><thead><tr>"
            "<th>Сеть</th><th>АЗС</th><th>Есть</th><th>Нет</th><th>Есть, %</th>"
            "<th>95 сейчас</th><th>98 сейчас</th></tr></thead><tbody>"
            + "".join(trs) + "</tbody></table></div>")


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    print("Собран:", build(base))
