# -*- coding: utf-8 -*-
"""
Сборка единой страницы public/index.html из data/history.csv (+ снимки станций,
которые передаёт run.py из памяти — на диск не сохраняются).

Разделы: hero, плитки цен со спарклайнами, СВОДНАЯ доступность по видам топлива
(из petrolplus и gdebenz вместе), интерактивные графики, таблицы по сетям.
"""

import html
import json
import os
from statistics import median

import store
import viz

FUELS = ["АИ-92", "АИ-95", "АИ-98", "АИ-100", "ДТ"]
FUEL_TO_GRADE = {"АИ-92": "92", "АИ-95": "95", "АИ-98": "98", "АИ-100": "100", "ДТ": "ДТ"}
STATUS = {"yes": ("Есть", viz.ST_GOOD), "no": ("Нет", viz.ST_CRIT),
          "queue": ("Очередь", viz.ST_SERIOUS), "low": ("Мало", viz.ST_WARN)}


def _cfg(base):
    with open(os.path.join(base, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def build(base_dir, price_stations=None, gd_stations=None):
    cfg = _cfg(base_dir)
    hist = store.load_history()
    status = store.load_json(store.STATUS) or {}
    out_dir = os.path.join(base_dir, "public")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")

    if not hist:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(viz.wrap("Бензин · дашборд", "<p class='empty'>Данных ещё нет.</p>"))
        return out_path

    labels = [viz.short_dt(r["ts_msk"]) for r in hist]
    last, prev = hist[-1], (hist[-2] if len(hist) > 1 else None)
    col = lambda c: [r.get(c) for r in hist]
    cur = lambda c: last.get(c)
    pre = lambda c: prev.get(c) if prev else None

    ps, gs = status.get("prices") or {}, status.get("gdebenz") or {}
    meta = (f"Цены обновлены <b>{html.escape(viz.short_dt(ps.get('ts_msk','')) or '—')}</b> · "
            f"наличие <b>{html.escape(viz.short_dt(gs.get('ts_msk','')) or '—')}</b> МСК · "
            f"замеров: <b>{len(hist)}</b> · {html.escape(cfg.get('region_name',''))}")

    # ------ HERO ------
    resp = (cur("gb_yes") or 0) + (cur("gb_no") or 0) + (cur("gb_queue") or 0) + (cur("gb_low") or 0)
    hero = f"""
    <div class="hero">
      <div class="card">
        <div class="t-label">Средняя цена АИ-95 <span class="hint">медиана по АЗС</span></div>
        <div class="t-row"><div class="hero-num">{viz.fmt(cur('p_med_АИ-95'),' ₽')}</div>
          {viz.sparkline(col('p_med_АИ-95'), '--f95', w=150, h=44)}</div>
        <div class="t-delta">{_delta(cur('p_med_АИ-95'), pre('p_med_АИ-95'),' ₽', good_down=True)}
          <span class="sub" style="display:inline;margin-left:8px">коридор p10–p90
          {viz.fmt(cur('p_p10_АИ-95'))}–{viz.fmt(cur('p_p90_АИ-95'))} ₽ · {viz.fmt(_i(cur('p_n_АИ-95')))} АЗС</span></div>
      </div>
      <div class="card">
        <div class="t-label">Ситуация с наличием <span class="hint">сейчас</span></div>
        <div class="t-row"><div class="hero-num" style="font-size:40px">{viz.fmt(_i(cur('gb_yes')))}</div>
          <div class="sub" style="text-align:right">есть бензин<br>из {viz.fmt(_i(resp))} ответивших АЗС</div></div>
        <div style="margin-top:10px">{_status_bar(last)}</div>
        <div class="sub" style="margin-top:8px">petrolplus: доступны {viz.fmt(_i(cur('azs_available')))} из {viz.fmt(_i(cur('azs_total')))} АЗС</div>
      </div>
    </div>"""

    # ------ плитки цен ------
    tiles = ""
    for f in FUELS:
        med, n = cur(f"p_med_{f}"), cur(f"p_n_{f}")
        sub = (f"{viz.fmt(_i(n))} АЗС · p10–p90 {viz.fmt(cur(f'p_p10_{f}'))}–{viz.fmt(cur(f'p_p90_{f}'))}"
               if med is not None else "нет данных")
        tiles += viz.kpi(f, med, pre(f"p_med_{f}"), " ₽", sub=sub,
                         spark=col(f"p_med_{f}"), var=viz.FUEL_VAR[f])
    tiles = f'<div class="tiles c5">{tiles}</div>'

    # ------ график цен ------
    price_series = [{"name": f, "var": viz.FUEL_VAR[f], "points": col(f"p_med_{f}")} for f in FUELS]
    chart_prices = viz.line_chart("prices", labels, price_series, unit=" ₽")

    # ------ СВОДНАЯ доступность по видам топлива ------
    avail_matrix = _fuel_availability_table(last)

    # ------ графики наличия ------
    chart_pp = viz.line_chart("availpp", labels, [
        {"name": "Доступные", "var": viz.ST_GOOD, "points": col("azs_available")},
        {"name": "Всего", "var": "--muted", "points": col("azs_total")},
    ], y_int=True)
    chart_gb = viz.line_chart("availgb", labels, [
        {"name": "Есть", "var": viz.ST_GOOD, "points": col("gb_yes")},
        {"name": "Нет", "var": viz.ST_CRIT, "points": col("gb_no")},
        {"name": "Очередь", "var": viz.ST_SERIOUS, "points": col("gb_queue")},
        {"name": "Мало", "var": viz.ST_WARN, "points": col("gb_low")},
    ], y_int=True)
    now_series = [{"name": f, "var": viz.FUEL_VAR[f],
                   "points": col(f"gb_now_{FUEL_TO_GRADE[f]}")} for f in FUELS]
    chart_now = viz.line_chart("nowgb", labels, now_series, y_int=True)

    body = f"""
    <header><h1>Бензин · Москва и ближнее Подмосковье</h1>
      <div class="meta">{meta}</div></header>
    {_banner(status)}
    {hero}

    <div class="sec">Цены по видам топлива</div>
    {tiles}
    <section class="card"><h2>Динамика цен <span class="hint">медиана по АЗС · наведите для значений</span></h2>
      {viz.legend([(f, viz.FUEL_VAR[f]) for f in FUELS])}{chart_prices}</section>

    <div class="sec">Доступность топлива — сводно</div>
    <section class="card"><h2>По видам топлива <span class="hint">из обоих источников · последний замер</span></h2>
      {avail_matrix}</section>
    <section class="grid2">
      <div class="card"><h2>Доступность АЗС <span class="hint">petrolplus · транзакции идут</span></h2>
        {viz.legend([("Доступные", viz.ST_GOOD),("Всего","--muted")])}{chart_pp}</div>
      <div class="card"><h2>Наличие бензина <span class="hint">gdebenz · статусы</span></h2>
        {viz.legend([("Есть",viz.ST_GOOD,"rect"),("Нет",viz.ST_CRIT,"rect"),("Очередь",viz.ST_SERIOUS,"rect"),("Мало",viz.ST_WARN,"rect")])}{chart_gb}</div>
    </section>
    <section class="card"><h2>Какие марки есть сейчас <span class="hint">gdebenz · число АЗС с маркой в наличии</span></h2>
      {viz.legend([(f, viz.FUEL_VAR[f]) for f in FUELS])}{chart_now}</section>

    <div class="sec">По сетям</div>
    <section class="card"><h2>Цены по сетям <span class="hint">медиана, ₽ (число АЗС) · petrolplus</span></h2>
      {_price_brand_table(price_stations)}</section>
    <section class="card"><h2>Наличие по сетям <span class="hint">gdebenz</span></h2>
      {_gdebenz_brand_table(gd_stations)}</section>

    <p class="foot">Цены — petrolplus / АЗС-Локатор (выгрузка StationList.xls); «доступны» =
      высокая доступность транзакций. Наличие — gdebenz.ru, краудсорс (сообщают
      пользователи), оценка «снизу». АИ-98/100 продаются на немногих АЗС — ряды разреженные
      (число АЗС указано у цифр). Величины справочные.</p>
    """
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(viz.wrap(f"Бензин · {viz.short_dt(last['ts_msk'])}", body))
    return out_path


# ---------------------------------------------------------------- helpers ---
def _i(v):
    return int(v) if v is not None else None


def _delta(cur, prev, unit="", good_down=True):
    if cur is None or prev is None:
        return '<span class="d flat">нет прошлого</span>'
    d = round(cur - prev, 2)
    if abs(d) < 1e-9:
        return '<span class="d flat">= без изм.</span>'
    up = d > 0
    good = (not up) if good_down else up
    return f'<span class="d {"good" if good else "bad"}">{"↑" if up else "↓"} {viz.fmt(abs(d), unit)}</span>'


def _status_bar(row):
    segs = [("yes", row.get("gb_yes")), ("low", row.get("gb_low")),
            ("queue", row.get("gb_queue")), ("no", row.get("gb_no"))]
    total = sum(v or 0 for _, v in segs) or 1
    out = '<div style="display:flex;height:10px;border-radius:6px;overflow:hidden;gap:2px">'
    for st, v in segs:
        if not v:
            continue
        name, var = STATUS[st]
        w = 100 * v / total
        out += f'<div title="{name}: {int(v)}" style="width:{w:.1f}%;background:var({var})"></div>'
    out += "</div>"
    chips = " ".join(
        f'<span class="chip"><span class="dot" style="background:var({STATUS[st][1]})"></span>'
        f'{STATUS[st][0]} {viz.fmt(_i(row.get("gb_"+st)))}</span>'
        for st in ("yes", "no", "queue", "low"))
    return out + f'<div style="display:flex;gap:14px;flex-wrap:wrap;margin-top:8px">{chips}</div>'


def _fuel_availability_table(row):
    trs = ""
    for f in FUELS:
        g = FUEL_TO_GRADE[f]
        med = row.get(f"p_med_{f}")
        n = _i(row.get(f"p_n_{f}"))
        navail = _i(row.get(f"p_navail_{f}"))
        nowg = _i(row.get(f"gb_now_{g}"))
        share = viz.pct(navail or 0, n) if n else None
        bar = ""
        if share is not None:
            bar = (f'<span class="bar" style="width:{max(4,share*0.6):.0f}px;'
                   f'background:var({viz.ST_GOOD})"></span> ')
        trs += (f'<tr><td class="b"><span class="chip"><span class="dot" '
                f'style="background:var({viz.FUEL_VAR[f]})"></span>{html.escape(f)}</span></td>'
                f'<td>{viz.fmt(med," ₽") if med is not None else "—"}</td>'
                f'<td>{viz.fmt(n)}</td>'
                f'<td>{bar}{viz.fmt(navail)}<span class="c"> · {viz.fmt(share)}%</span></td>'
                f'<td>{viz.fmt(nowg)}</td></tr>')
    return ('<div class="tablewrap"><table class="tbl" style="min-width:520px"><thead><tr>'
            '<th>Вид топлива</th><th>Медиана цены</th><th>Продают (АЗС)</th>'
            '<th>Доступны · транзакции</th><th>Есть сейчас (gdebenz)</th></tr></thead><tbody>'
            + trs + '</tbody></table></div>')


def _price_brand_table(stations):
    if not stations:
        return "<div class='empty'>Снимок цен появится после первого сбора</div>"
    agg = {}
    for s in stations:
        a = agg.setdefault(s.get("brand") or "—", {"n": 0, "avail": 0, "p": {f: [] for f in FUELS}})
        a["n"] += 1
        a["avail"] += 1 if s.get("available") else 0
        for f in FUELS:
            v = (s.get("prices") or {}).get(f)
            if v is not None:
                a["p"][f].append(v)
    head = "".join(f"<th>{html.escape(f)}</th>" for f in FUELS)
    trs = ""
    for b, a in sorted(agg.items(), key=lambda kv: -kv[1]["n"])[:15]:
        cells = ""
        for f in FUELS:
            vals = a["p"][f]
            cells += (f'<td>{viz.fmt(round(median(vals),2)," ₽")}<span class="c"> · {len(vals)}</span></td>'
                      if vals else '<td>—</td>')
        trs += (f'<tr><td class="b">{html.escape(b)}</td><td>{a["n"]}</td>'
                f'<td>{a["avail"]}</td>{cells}</tr>')
    return ('<div class="tablewrap"><table class="tbl"><thead><tr><th>Сеть</th><th>АЗС</th>'
            '<th>Доступно</th>' + head + '</tr></thead><tbody>' + trs + '</tbody></table></div>')


def _gdebenz_brand_table(stations):
    if not stations:
        return "<div class='empty'>Снимок наличия появится после первого сбора</div>"
    agg = {}
    for s in stations:
        a = agg.setdefault(s.get("brand") or "—", {"n": 0, "yes": 0, "no": 0, "g95": 0, "g98": 0})
        a["n"] += 1
        st = s.get("status")
        a["yes"] += 1 if st == "yes" else 0
        a["no"] += 1 if st == "no" else 0
        fs = {x.strip() for x in (s.get("fuels_now") or "").split(",") if x.strip()}
        a["g95"] += 1 if "95" in fs else 0
        a["g98"] += 1 if "98" in fs else 0
    trs = ""
    for b, a in sorted(agg.items(), key=lambda kv: -kv[1]["n"])[:15]:
        share = viz.pct(a["yes"], a["yes"] + a["no"])
        trs += (f'<tr><td class="b">{html.escape(b)}</td><td>{a["n"]}</td>'
                f'<td>{a["yes"]}</td><td>{a["no"]}</td><td>{viz.fmt(share)}%</td>'
                f'<td>{a["g95"]}</td><td>{a["g98"]}</td></tr>')
    return ('<div class="tablewrap"><table class="tbl"><thead><tr><th>Сеть</th><th>АЗС</th>'
            '<th>Есть</th><th>Нет</th><th>Есть, %</th><th>95 сейчас</th><th>98 сейчас</th>'
            '</tr></thead><tbody>' + trs + '</tbody></table></div>')


def _banner(status):
    bits = []
    for key, label in (("prices", "Цены (petrolplus)"), ("gdebenz", "Наличие (gdebenz)")):
        s = status.get(key) or {}
        if s.get("ok") is False:
            bits.append(f"{label}: последний сбор не удался — показаны прошлые данные "
                        f"({html.escape((s.get('error') or '')[:100])}).")
    return ('<div class="banner">⚠ ' + "<br>".join(bits) + "</div>") if bits else ""


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    print("Собран:", build(base))
