# -*- coding: utf-8 -*-
"""
Сборка единой страницы public/index.html из data/history.csv (+ снимки станций из памяти).

Дашборд организован ВОКРУГ ВИДОВ ТОПЛИВА: по каждому виду — цена и доступность отдельно
(«есть сейчас» из gdebenz + «транзакции идут» из petrolplus), а не общая доступность АЗС.
Разделы: строка-ситуация, per-fuel карточки, динамика цен, доступность по видам,
общая ситуация с наличием, таблицы по сетям.
"""

import html
import json
import os
from statistics import median

import store
import viz

FUELS = ["АИ-92", "АИ-95", "АИ-98", "АИ-100", "ДТ"]
FUEL_TO_GRADE = {"АИ-92": "92", "АИ-95": "95", "АИ-98": "98", "АИ-100": "100", "ДТ": "ДТ"}


def _cfg(base):
    with open(os.path.join(base, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def _i(v):
    return int(v) if v is not None else None


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

    # ---- строка-ситуация ----
    situation = f"""
    <div class="situation">
      <span class="lead">Средняя АИ-95 · {viz.fmt(cur('p_med_АИ-95'),' ₽')}</span>
      <span class="pill"><span class="dot" style="background:var({viz.ST_GOOD})"></span>Есть бензин: {viz.fmt(_i(cur('gb_yes')))}</span>
      <span class="pill"><span class="dot" style="background:var({viz.ST_CRIT})"></span>Нет: {viz.fmt(_i(cur('gb_no')))}</span>
      <span class="pill"><span class="dot" style="background:var({viz.ST_SERIOUS})"></span>Очередь: {viz.fmt(_i(cur('gb_queue')))}</span>
      <span class="pill">petrolplus доступны: {viz.fmt(_i(cur('azs_available')))} из {viz.fmt(_i(cur('azs_total')))}</span>
    </div>"""

    # ---- per-fuel карточки ----
    cards = "".join(_fuel_card(f, col, cur, pre) for f in FUELS)
    fuelgrid = f'<div class="fuelgrid">{cards}</div>'

    # ---- график цен ----
    chart_prices = viz.line_chart("prices", labels,
        [{"name": f, "var": viz.FUEL_VAR[f], "points": col(f"p_med_{f}")} for f in FUELS], unit=" ₽")

    # ---- доступность ПО ВИДАМ (gdebenz «есть сейчас») ----
    chart_avail_fuel = viz.line_chart("availfuel", labels,
        [{"name": f, "var": viz.FUEL_VAR[f], "points": col(f"gb_now_{FUEL_TO_GRADE[f]}")}
         for f in FUELS], y_int=True, end_labels=False)

    # ---- общая ситуация (вторично) ----
    chart_status = viz.line_chart("gbstatus", labels, [
        {"name": "Есть", "var": viz.ST_GOOD, "points": col("gb_yes")},
        {"name": "Нет", "var": viz.ST_CRIT, "points": col("gb_no")},
        {"name": "Очередь", "var": viz.ST_SERIOUS, "points": col("gb_queue")},
        {"name": "Мало", "var": viz.ST_WARN, "points": col("gb_low")},
    ], y_int=True, end_labels=False)
    chart_pp = viz.line_chart("availpp", labels, [
        {"name": "Доступные", "var": viz.ST_GOOD, "points": col("azs_available")},
        {"name": "Всего", "var": "--muted", "points": col("azs_total")},
    ], y_int=True, end_labels=False)

    body = f"""
    <header><h1>Бензин · Москва и ближнее Подмосковье</h1>
      <div class="meta">{meta}</div></header>
    {_banner(status)}
    {situation}

    <div class="sec">Цены и доступность по видам топлива</div>
    {fuelgrid}

    <section class="card"><h2>Динамика цен <span class="hint">медиана по АЗС · наведите для значений</span></h2>
      {viz.legend([(f, viz.FUEL_VAR[f]) for f in FUELS])}{chart_prices}</section>

    <section class="card"><h2>Доступность по видам топлива <span class="hint">gdebenz · число АЗС, где марка есть в наличии сейчас</span></h2>
      {viz.legend([(f, viz.FUEL_VAR[f]) for f in FUELS])}{chart_avail_fuel}</section>

    <div class="sec">Общая ситуация с наличием</div>
    <section class="grid2">
      <div class="card"><h2>Статусы АЗС <span class="hint">gdebenz</span></h2>
        {viz.legend([("Есть",viz.ST_GOOD,"rect"),("Нет",viz.ST_CRIT,"rect"),("Очередь",viz.ST_SERIOUS,"rect"),("Мало",viz.ST_WARN,"rect")])}{chart_status}</div>
      <div class="card"><h2>Доступность АЗС <span class="hint">petrolplus · транзакции идут</span></h2>
        {viz.legend([("Доступные",viz.ST_GOOD),("Всего","--muted")])}{chart_pp}</div>
    </section>

    <div class="sec">По сетям</div>
    <section class="card"><h2>Цены по сетям <span class="hint">медиана, ₽ (число АЗС) · petrolplus</span></h2>
      {_price_brand_table(price_stations)}</section>
    <section class="card"><h2>Наличие по сетям <span class="hint">gdebenz</span></h2>
      {_gdebenz_brand_table(gd_stations)}</section>

    <p class="foot">Цена и «продают/транзакции идут» — petrolplus / АЗС-Локатор (выгрузка
      StationList.xls). Медиана считается по <b>свежим ценам</b> (обновлённым за последние 14
      дней); если свежих мало — по всем. «Транзакции идут» = доля АЗС с высокой доступностью
      среди продающих этот вид. «Есть сейчас» — gdebenz.ru, краудсорс (наличие сообщают
      пользователи), оценка «снизу». АИ-98/100 продаются на немногих АЗС — данные разреженные.
      Величины справочные.</p>
    """
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(viz.wrap(f"Бензин · {viz.short_dt(last['ts_msk'])}", body))
    return out_path


# ---------------------------------------------------------------- per-fuel ---
def _fuel_card(f, col, cur, pre):
    g = FUEL_TO_GRADE[f]
    var = viz.FUEL_VAR[f]
    med = cur(f"p_med_{f}")
    n = _i(cur(f"p_n_{f}"))
    fresh = _i(cur(f"p_fresh_{f}"))
    navail = _i(cur(f"p_navail_{f}"))
    now = _i(cur(f"gb_now_{g}"))
    share = viz.pct(navail or 0, n) if n else None
    spark = viz.sparkline(col(f"p_med_{f}"), var, w=92, h=28)
    price_arrow = viz.arrow(med, pre(f"p_med_{f}"), good_down=True, unit=" ₽")
    now_arrow = viz.arrow(now, pre(f"gb_now_{g}"), good_down=False)
    psub = (f"по {viz.fmt(fresh)} свежим ценам" if fresh and fresh >= 5
            else f"{viz.fmt(n)} АЗС · свежих мало")
    return f"""
    <div class="fuelcard" style="--accent:var({var})">
      <div class="fc-head"><span class="fc-dot" style="background:var({var})"></span>
        <span class="fc-name">{html.escape(f)}</span></div>
      <div class="fc-price"><div class="fc-val">{viz.fmt(med,' ₽') if med is not None else '—'}</div>{spark}</div>
      <div class="fc-sub">{price_arrow} · {psub}</div>
      <div class="fc-avail">
        <div class="fc-arow"><span class="lbl">Есть сейчас</span>
          <span class="num">{viz.fmt(now)} АЗС {now_arrow}</span></div>
        <div class="fc-arow"><span class="lbl">Транзакции идут</span>
          <span class="num">{viz.fmt(share)}%</span></div>
        {viz.meter(share, viz.ST_GOOD)}
      </div>
    </div>"""


# ------------------------------------------------------------------ tables ---
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
    grades = [FUEL_TO_GRADE[f] for f in FUELS]   # 92,95,98,100,ДТ
    agg = {}
    for s in stations:
        a = agg.setdefault(s.get("brand") or "—",
                           {"n": 0, "yes": 0, "no": 0, **{g: 0 for g in grades}})
        a["n"] += 1
        st = s.get("status")
        a["yes"] += 1 if st == "yes" else 0
        a["no"] += 1 if st == "no" else 0
        fs = {x.strip() for x in (s.get("fuels_now") or "").split(",") if x.strip()}
        for g in grades:
            if g in fs:
                a[g] += 1
    ghead = "".join(f"<th>{html.escape('АИ-'+g if g != 'ДТ' else g)}</th>" for g in grades)
    trs = ""
    for b, a in sorted(agg.items(), key=lambda kv: -kv[1]["n"])[:15]:
        share = viz.pct(a["yes"], a["yes"] + a["no"])
        cells = "".join(f'<td>{a[g] or "—"}</td>' for g in grades)
        trs += (f'<tr><td class="b">{html.escape(b)}</td><td>{a["n"]}</td>'
                f'<td>{a["yes"]}</td><td>{a["no"]}</td><td>{viz.fmt(share)}%</td>{cells}</tr>')
    return ('<div class="tablewrap"><table class="tbl"><thead><tr><th>Сеть</th><th>АЗС</th>'
            '<th>Есть</th><th>Нет</th><th>Есть, %</th>' + ghead +
            '</tr></thead><tbody>' + trs + '</tbody></table>'
            '<div class="fc-sub" style="margin-top:6px">Столбцы по видам — число АЗС, где марка '
            'есть в наличии сейчас.</div></div>')


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
