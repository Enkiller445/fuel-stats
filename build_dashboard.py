# -*- coding: utf-8 -*-
"""
Сборка единой страницы public/index.html (v4).

Организация вокруг видов топлива + аналитика по времени: почасовой сбор, дневные
срезы в фиксированный час, скользящее среднее, дельты 24ч/7д, сети-vs-независимые
и спред, «лучший час заправки», разрез по дню недели, алерты, лента событий.
Чётко разделены «наличие» (gdebenz) и «транзакции идут» (petrolplus).
"""

import html
import json
import os
from datetime import datetime, timezone, timedelta
from statistics import median

import store
import viz
import analytics

try:
    from zoneinfo import ZoneInfo
    MSK = ZoneInfo("Europe/Moscow")
except Exception:
    MSK = None

FUELS = ["АИ-92", "АИ-95", "АИ-98", "АИ-100", "ДТ"]
FUEL_TO_GRADE = {"АИ-92": "92", "АИ-95": "95", "АИ-98": "98", "АИ-100": "100", "ДТ": "ДТ"}
NET_COLORS = {"Роснефть": "--f95", "Газпромнефть": "--f92", "Лукойл": "--f100"}


def _cfg(base):
    with open(os.path.join(base, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def _i(v):
    return int(v) if v is not None else None


# ------------------------------------------------------ авто-выводы (?) ---
def _lv(hist, c):
    return analytics._val(hist[-1], c)


def _pctf(a, b):
    return (100 * (a - b) / b) if (a is not None and b) else None


def _v_price95(hist):
    cur = _lv(hist, "p_med_АИ-95")
    d7 = analytics.delta(hist, "p_med_АИ-95", 168)
    d24 = analytics.delta(hist, "p_med_АИ-95", 24)
    if d7 is None and d24 is None:
        return "Тренд появится за 1–7 дней сбора."
    seg = []
    if d7 is not None:
        p = _pctf(cur, analytics.value_at_ago(hist, "p_med_АИ-95", 168))
        w = "вырос" if d7 > 0.01 else "снизился" if d7 < -0.01 else "стабилен"
        seg.append(f"за неделю {w}" +
                   (f" на {viz.fmt(abs(d7), ' ₽')} ({p:+.1f}%)" if abs(d7) > 0.01 and p is not None else ""))
    if d24 is not None and abs(d24) >= 0.02:
        seg.append(f"за сутки {'↑' if d24 > 0 else '↓'}{viz.fmt(abs(d24), ' ₽')}")
    return "АИ-95 " + ", ".join(seg) + "."


def _v_spread(hist):
    cur = _lv(hist, "spread95")
    if cur is None:
        return "Данные по ценам сетей/независимых накапливаются."
    d7 = analytics.delta(hist, "spread95", 168)
    s = f"Независимые дороже сетей на {viz.fmt(cur, ' ₽')}."
    if d7 is not None and abs(d7) >= 0.1:
        s += (f" Спред за неделю {'вырос' if d7 > 0 else 'сузился'} на {viz.fmt(abs(d7), ' ₽')}"
              f" → дефицит {'усиливается' if d7 > 0 else 'ослабевает'}.")
    elif cur > 3:
        s += " Спред заметный — независимые ощущают дефицит сильнее сетей."
    return s


def _v_avail(hist):
    yc, no = _lv(hist, "gb_yes"), _lv(hist, "gb_no")
    q, low = _lv(hist, "gb_queue"), _lv(hist, "gb_low")
    den = sum(x for x in (yc, no, q, low) if x is not None)
    seg = []
    if yc is not None and den:
        seg.append(f"сейчас «есть» у {round(100*yc/den)}% ответивших АЗС")
    d24 = analytics.delta(hist, "gb_yes", 24)
    if d24 is not None and abs(d24) >= 1:
        seg.append(f"за сутки {'↑' if d24 > 0 else '↓'}{viz.fmt(abs(int(d24)))} АЗС")
    return ("Наличие: " + ", ".join(seg) + ".") if seg else "Наличие копится."


def _v_fuel_avail(hist):
    items = [(f, _lv(hist, f"gb_now_{FUEL_TO_GRADE[f]}")) for f in FUELS]
    items = [(f, v) for f, v in items if v is not None]
    if not items:
        return "Наличие по видам накапливается."
    f, v = min(items, key=lambda x: x[1])
    return f"Труднее всего найти {f} — есть на {int(v)} АЗС сейчас."


def _v_best_hour(hist):
    avg, _ = analytics.by_hour(hist, "gb_yes")
    have = [h for h in range(24) if avg[h] is not None]
    if len(have) < 6:
        return "Нужно ≥ суток почасовых данных — копится."
    bh = max(have, key=lambda h: avg[h])
    return f"Больше всего топлива около {bh:02d}:00 МСК — лучшее время заправиться."


def _v_weekday(drows):
    wd = analytics.by_weekday(drows, "gb_yes")
    have = [i for i in range(7) if wd[i] is not None]
    if len(have) < 4:
        return "Нужно ≥ недели данных — копится."
    worst = min(have, key=lambda i: wd[i])
    best = max(have, key=lambda i: wd[i])
    return f"Хуже всего с топливом в {analytics.WEEKDAYS[worst]}, лучше — в {analytics.WEEKDAYS[best]}."


def _load_events(base):
    try:
        with open(os.path.join(base, "events.json"), encoding="utf-8") as f:
            ev = json.load(f)
        return [e for e in ev if e.get("title") and not str(e["title"]).startswith("ПРИМЕР")]
    except Exception:
        return []


def _load_auto(base):
    try:
        with open(os.path.join(base, "data", "events_auto.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def build(base_dir, price_stations=None, gd_stations=None):
    cfg = _cfg(base_dir)
    hist = store.load_history()
    status = store.load_json(store.STATUS) or {}
    events = _load_events(base_dir)
    auto_events = _load_auto(base_dir)
    out_dir = os.path.join(base_dir, "public")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")

    if not hist:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(viz.wrap("Бензин · дашборд", "<p class='empty'>Данных ещё нет.</p>"))
        return out_path

    last = hist[-1]
    cur = lambda c: analytics._val(last, c)

    # дневная выборка (по фиксированному часу) — основа трендов
    sample_hour = cfg.get("daily_sample_hour", 20)
    ma_days = cfg.get("ma_days", 3)
    days, drows = analytics.daily_sample(hist, sample_hour)
    dlabels = [d.strftime("%d.%m") for d in days]

    body = "".join([
        _header(cfg, status, hist),
        _alerts(hist, cfg),
        _situation(hist, cur),
        f'<div class="sec">Цены и доступность по видам топлива '
        f'{viz.help_badge("По каждому виду: цена (petrolplus, медиана по свежим ценам) и доступность. «Есть сейчас» — наличие по gdebenz (краудсорс). «Транзакции идут» — доля АЗС с высокой доступностью среди продающих этот вид (petrolplus). Это разные метрики.", _v_fuel_avail(hist))}</div>',
        f'<div class="fuelgrid">{"".join(_fuel_card(f, hist, cur) for f in FUELS)}</div>',
        _prices_section(cfg, hist, days, drows, dlabels, events + auto_events),
        _availability_section(cfg, hist, days, drows, dlabels),
        _events_section(events, auto_events),
        '<div class="sec">По сетям · последний замер</div>',
        f'<section class="card"><h2>Цены по сетям <span class="hint">медиана, ₽ (число АЗС) · petrolplus</span>'
        f'{viz.help_badge("Медиана цены по каждой сети и виду топлива (petrolplus). Рядом — число АЗС сети с ценой на этот вид.", _v_spread(hist))}</h2>{_price_brand_table(price_stations)}</section>',
        f'<section class="card"><h2>Наличие по сетям <span class="hint">gdebenz · число АЗС с маркой сейчас</span>'
        f'{viz.help_badge("По каждой сети: сколько её АЗС со статусом «есть»/«нет» и на скольких сейчас есть каждый вид топлива (gdebenz, краудсорс).")}</h2>{_gdebenz_brand_table(gd_stations)}</section>',
        _footer(),
    ])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(viz.wrap(f"Бензин · {viz.short_dt(last['ts_msk'])}", body))
    return out_path


# ------------------------------------------------------------------ header ---
def _ago(ts_msk):
    if not MSK or not ts_msk:
        return "—", "--muted"
    try:
        t = datetime.strptime(ts_msk, "%Y-%m-%d %H:%M:%S").replace(tzinfo=MSK)
    except Exception:
        return "—", "--muted"
    mins = (datetime.now(MSK) - t).total_seconds() / 60
    if mins < 90:
        txt, color = (f"{int(mins)} мин назад", viz.ST_GOOD)
    elif mins < 60 * 12:
        txt, color = (f"{int(mins//60)} ч назад", viz.ST_WARN)
    else:
        txt, color = (f"{int(mins//1440)} дн назад", viz.ST_CRIT)
    return txt, color


def _header(cfg, status, hist):
    ps, gs = status.get("prices") or {}, status.get("gdebenz") or {}
    p_ago, p_c = _ago(ps.get("ts_msk"))
    g_ago, g_c = _ago(gs.get("ts_msk"))
    ndays = analytics.monitoring_days(hist)
    ymin, ymax = analytics.col_min_max(hist, "p_med_АИ-95")
    amin, amax = analytics.col_min_max(hist, "gb_yes")
    fresh = (f'<div class="fresh">'
             f'<span class="src"><span class="dot" style="background:var({p_c})"></span>'
             f'Цены (petrolplus): {html.escape(p_ago)}</span>'
             f'<span class="src"><span class="dot" style="background:var({g_c})"></span>'
             f'Наличие (gdebenz): {html.escape(g_ago)}</span></div>')
    stat = (f'<div class="stat-row">'
            f'<span>Мониторинг: <b>{ndays}</b> дн · <b>{len(hist)}</b> замеров</span>'
            f'<span>АИ-95 за период: <b>{viz.fmt(ymin," ₽")}</b> … <b>{viz.fmt(ymax," ₽")}</b></span>'
            f'<span>«Есть бензин» за период: <b>{viz.fmt(_i(amin))}</b> … <b>{viz.fmt(_i(amax))}</b> АЗС</span></div>')
    return (f'<header><h1>Бензин · Москва и ближнее Подмосковье</h1>'
            f'<div class="meta">Сбор ежечасно · {html.escape(cfg.get("region_name",""))}</div>'
            f'</header>{fresh}{stat}')


# ------------------------------------------------------------------ alerts ---
def _alerts(hist, cfg):
    al = cfg.get("alerts", {})
    msgs = []
    yes = analytics._val(hist[-1], "gb_yes")
    ymin = al.get("avail_yes_min")
    if yes is not None and ymin is not None and yes < ymin:
        msgs.append(f"Наличие бензина низкое: <b>{int(yes)}</b> АЗС «есть» "
                    f"(порог {int(ymin)}).")
    thr = al.get("price_day_rise_pct")
    d = analytics.delta(hist, "p_med_АИ-95", 24)
    base = analytics.value_at_ago(hist, "p_med_АИ-95", 24)
    if d is not None and base and thr is not None:
        pct = 100 * d / base
        if pct >= thr:
            msgs.append(f"АИ-95 подорожал на <b>{pct:.1f}%</b> за сутки "
                        f"(+{viz.fmt(round(d,2),' ₽')}).")
    if not msgs:
        return ""
    return '<div class="alert">⚠ ' + "<br>".join(msgs) + "</div>"


# --------------------------------------------------------------- situation ---
def _situation(hist, cur):
    return (f'<div class="situation">'
            f'<span class="lead">Средняя АИ-95 · {viz.fmt(cur("p_med_АИ-95")," ₽")}'
            f'{viz.help_badge("Медианная цена АИ-95 по всем АЗС в рамке. Медиана устойчивее среднего к выбросам. Δ24ч/Δ7д — изменение за сутки и неделю.", _v_price95(hist))}</span>'
            f'{_dd(hist, "p_med_АИ-95", " ₽", good_down=True)}'
            f'<span class="pill"><span class="dot" style="background:var({viz.ST_GOOD})"></span>'
            f'Есть бензин: {viz.fmt(_i(cur("gb_yes")))}</span>'
            f'<span class="pill"><span class="dot" style="background:var({viz.ST_CRIT})"></span>'
            f'Нет: {viz.fmt(_i(cur("gb_no")))}</span>'
            f'<span class="pill"><span class="dot" style="background:var({viz.ST_SERIOUS})"></span>'
            f'Очередь: {viz.fmt(_i(cur("gb_queue")))}</span></div>')


def _dd(hist, col_name, unit="", good_down=True):
    parts = []
    for lbl, hrs in (("24ч", 24), ("7д", 168)):
        d = analytics.delta(hist, col_name, hrs)
        if d is None:
            parts.append(f'<span>{lbl} —</span>')
        elif abs(d) < 1e-9:
            parts.append(f'<span>{lbl} =</span>')
        else:
            up = d > 0
            good = (not up) if good_down else up
            parts.append(f'<span>{lbl} <span class="{"good" if good else "bad"}">'
                         f'{"↑" if up else "↓"}{viz.fmt(abs(d), unit)}</span></span>')
    return '<div class="dd">' + "".join(parts) + '</div>'


# -------------------------------------------------------------- fuel cards ---
def _fuel_card(f, hist, cur):
    g = FUEL_TO_GRADE[f]
    var = viz.FUEL_VAR[f]
    med = cur(f"p_med_{f}")
    n = _i(cur(f"p_n_{f}"))
    fresh = _i(cur(f"p_fresh_{f}"))
    navail = _i(cur(f"p_navail_{f}"))
    now = _i(cur(f"gb_now_{g}"))
    share = viz.pct(navail or 0, n) if n else None
    spark = viz.sparkline(analytics.col(hist, f"p_med_{f}"), var, w=92, h=28)
    psub = (f"по {viz.fmt(fresh)} свежим ценам" if fresh and fresh >= 5
            else f"{viz.fmt(n)} АЗС · свежих мало")
    return f"""
    <div class="fuelcard" style="--accent:var({var})">
      <div class="fc-head"><span class="fc-dot" style="background:var({var})"></span>
        <span class="fc-name">{html.escape(f)}</span></div>
      <div class="fc-price"><div class="fc-val">{viz.fmt(med,' ₽') if med is not None else '—'}</div>{spark}</div>
      <div class="fc-sub">{psub}</div>
      {_dd(hist, f"p_med_{f}", " ₽", good_down=True)}
      <div class="fc-avail">
        <div class="fc-arow"><span class="lbl">Есть сейчас</span>
          <span class="num">{viz.fmt(now)} АЗС</span></div>
        <div class="fc-arow"><span class="lbl">Транзакции идут</span>
          <span class="num">{viz.fmt(share)}%</span></div>
        {viz.meter(share, viz.ST_GOOD)}
      </div>
    </div>"""


# ------------------------------------------------------------ prices block ---
def _event_annotations(events, days):
    if not days:
        return []
    lo, hi = days[0], days[-1]
    anns = []
    for e in events:
        try:
            ed = datetime.strptime(e["date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if ed < lo or ed > hi:            # метка только если событие в диапазоне графика
            continue
        idx = next((i for i, d in enumerate(days) if d >= ed), len(days) - 1)
        anns.append({"i": idx, "label": "◆", "full": f'{e["date"]}: {e["title"]}'})
    return anns[:8]


def _prices_section(cfg, hist, days, drows, dlabels, events):
    anns = _event_annotations(events, days)
    price_daily = viz.line_chart("pxday", dlabels,
        [{"name": f, "var": viz.FUEL_VAR[f], "points": analytics.col(drows, f"p_med_{f}")} for f in FUELS],
        unit=" ₽", annotations=anns)

    # АИ-95: независимые vs сети (+ отслеживаемые сети)
    series = [
        {"name": "Независимые", "var": viz.ST_CRIT, "points": analytics.col(drows, "indep95_med")},
        {"name": "Сети (ВИНК)", "var": "--muted", "points": analytics.col(drows, "net95_med")},
    ]
    for nw in cfg.get("tracked_networks", []):
        series.append({"name": nw, "var": NET_COLORS.get(nw, "--f98"),
                       "points": analytics.col(drows, f"net95_{nw}")})
    netchart = viz.line_chart("pxnet", dlabels, series, unit=" ₽")

    # спред независимые - сети
    spread = viz.line_chart("spread", dlabels,
        [{"name": "Спред", "var": viz.ST_SERIOUS, "points": analytics.col(drows, "spread95")}],
        unit=" ₽", area=True, end_labels=False)

    h_daily = viz.help_badge(
        f"Медианная цена по каждому виду, по дням (берётся замер около {cfg.get('daily_sample_hour',20)}:00 МСК, чтобы убрать внутрисуточный шум). Наведите — значения всех видов; ◆ — событие.",
        _v_price95(hist))
    h_net = viz.help_badge(
        "Независимые АЗС (вне крупных ВИНК) обычно поднимают цены раньше сетей — их опережение сигналит о дефиците. Показаны независимые, сети в целом и отслеживаемые сети.",
        _v_spread(hist))
    h_spread = viz.help_badge(
        "Разница медиан: независимые минус сети (АИ-95). Растёт — дефицит усиливается; сужается — рынок успокаивается.",
        _v_spread(hist))
    return f"""
    <div class="sec">Цены · динамика по дням</div>
    <section class="card"><h2>Медианная цена по видам <span class="hint">по дням, замер ~{cfg.get('daily_sample_hour',20)}:00 МСК · наведите для значений</span>{h_daily}</h2>
      {viz.legend([(f, viz.FUEL_VAR[f]) for f in FUELS])}{price_daily}</section>
    <section class="grid2">
      <div class="card"><h2>АИ-95: независимые vs сети <span class="hint">независимые реагируют на дефицит первыми</span>{h_net}</h2>
        {viz.legend([("Независимые", viz.ST_CRIT), ("Сети (ВИНК)", "--muted")] + [(nw, NET_COLORS.get(nw,"--f98")) for nw in cfg.get("tracked_networks", [])])}
        {netchart}</div>
      <div class="card"><h2>Спред «независимые − сети» <span class="hint">рост спреда = дефицит усиливается</span>{h_spread}</h2>
        {spread}</div>
    </section>"""


# ------------------------------------------------------ availability block ---
def _daily_yes_pct(drows):
    out = []
    for r in drows:
        y = analytics._val(r, "gb_yes")
        den = sum(x for x in (analytics._val(r, "gb_yes"), analytics._val(r, "gb_no"),
                              analytics._val(r, "gb_queue"), analytics._val(r, "gb_low"))
                  if x is not None)
        out.append(round(100 * y / den, 1) if (y is not None and den) else None)
    return out


def _availability_section(cfg, hist, days, drows, dlabels):
    yes_pct = _daily_yes_pct(drows)
    ma = analytics.moving_avg(yes_pct, cfg.get("ma_days", 3))
    share_chart = viz.line_chart("availshare", dlabels, [
        {"name": "Доля «есть», %", "var": viz.ST_GOOD, "points": yes_pct},
        {"name": f"{cfg.get('ma_days',3)}-дн. среднее", "var": "--f95", "points": ma},
    ], unit=" %", end_labels=False)

    fuel_avail = viz.line_chart("availfuelday", dlabels,
        [{"name": f, "var": viz.FUEL_VAR[f], "points": analytics.col(drows, f"gb_now_{FUEL_TO_GRADE[f]}")}
         for f in FUELS], y_int=True, end_labels=False)

    # лучший час заправки (среднее «есть» по часу суток)
    hour_avg, hour_n = analytics.by_hour(hist, "gb_yes")
    best_hour = max(range(24), key=lambda h: (hour_avg[h] is not None, hour_avg[h] or -1))
    best_txt = (f"Исторически больше всего наличия около <b>{best_hour:02d}:00</b> МСК"
                if hour_avg[best_hour] is not None else "Накапливаем почасовые данные…")
    hour_bars = viz.bar_chart([f"{h}" for h in range(24)], hour_avg, var=viz.ST_GOOD, highlight="max")

    # день недели
    wd = analytics.by_weekday(drows, "gb_yes")
    wd_bars = viz.bar_chart(analytics.WEEKDAYS, wd, var=viz.ST_GOOD, highlight="max")

    ma_n = cfg.get('ma_days', 3)
    h_share = viz.help_badge(
        f"Доля АЗС со статусом «есть» среди ответивших (gdebenz), по дням. Линия «{ma_n}-дн. среднее» сглаживает суточный шум и показывает тренд, а не колебания.",
        _v_avail(hist))
    h_fuel = viz.help_badge(
        "Число АЗС, где марка есть в наличии сейчас (gdebenz), по дням. Видно, какой вид просаживается первым.",
        _v_fuel_avail(hist))
    h_hour = viz.help_badge(
        "Среднее число АЗС с наличием по часу суток за всё время наблюдений. Пик — когда топлива обычно больше всего.",
        _v_best_hour(hist))
    h_wd = viz.help_badge(
        "Среднее наличие по дням недели (из дневной выборки). Проверка гипотезы про пятнично-субботний провал.",
        _v_weekday(drows))
    return f"""
    <div class="sec">Наличие · динамика и разрезы</div>
    <section class="grid2">
      <div class="card"><h2>Доля АЗС с наличием, % <span class="hint">по дням + {ma_n}-дн. среднее · gdebenz</span>{h_share}</h2>
        {viz.legend([("Доля «есть», %", viz.ST_GOOD), (f"{ma_n}-дн. среднее", "--f95")])}
        {share_chart}</div>
      <div class="card"><h2>Наличие по видам, АЗС <span class="hint">по дням · gdebenz</span>{h_fuel}</h2>
        {viz.legend([(f, viz.FUEL_VAR[f]) for f in FUELS])}{fuel_avail}</div>
    </section>
    <section class="grid2">
      <div class="card"><h2>Лучшее время заправки <span class="hint">среднее «есть» по часу суток</span>{h_hour}</h2>
        <div class="stat-row" style="margin:0 0 8px">{best_txt}</div>{hour_bars}</div>
      <div class="card"><h2>По дням недели <span class="hint">среднее «есть» · пятница/суббота?</span>{h_wd}</h2>
        {wd_bars}</div>
    </section>"""


# ----------------------------------------------------------------- events ---
def _events_section(manual, auto):
    hb = viz.help_badge(
        "События из новостей (Google News, автоподборка по топливной теме) и ваши ручные "
        "пометки из events.json. ◆ на графике цен — событие в его диапазоне. Автоподборка "
        "не проверена — сверяйтесь с источником по ссылке.")

    def item(e, is_auto):
        title = html.escape(str(e.get("title", "")))
        link = (f'<a href="{html.escape(e["url"])}" target="_blank" rel="noopener">{title}</a>'
                if e.get("url") else title)
        src = (f'<span class="ev-src">· {html.escape(e.get("source",""))}</span>'
               if e.get("source") else "")
        badge = '<span class="ev-auto">авто</span>' if is_auto else ""
        return (f'<li><span class="ed">{html.escape(str(e.get("date","")))}</span>'
                f'<span>{link} {src} {badge}</span></li>')

    rows = "".join(item(e, False) for e in sorted(manual, key=lambda x: x.get("date", ""), reverse=True))
    rows += "".join(item(e, True) for e in auto[:12])
    inner = (f'<ul class="events">{rows}</ul>' if rows else
             '<div class="fc-sub">Автоподборка новостей появится после ближайшего сбора; '
             'свои события добавляйте в <b>events.json</b>.</div>')
    return (f'<div class="sec">Лента событий {hb}</div><section class="card">{inner}'
            '<div class="fc-sub" style="margin-top:8px">«авто» — из новостной подборки '
            '(Google News), <b>проверяйте по источнику</b>. Без пометки — добавлено вручную.</div>'
            '</section>')


# ------------------------------------------------------------------ tables ---
def _price_brand_table(stations):
    if not stations:
        return "<div class='empty'>Снимок появится после ближайшего сбора</div>"
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
        return "<div class='empty'>Снимок появится после ближайшего сбора</div>"
    grades = [FUEL_TO_GRADE[f] for f in FUELS]
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


def _footer():
    return ('<p class="foot"><b>Две разные метрики, не смешивать:</b> '
            '«Есть сейчас» / «наличие» — <b>gdebenz.ru</b> (краудсорс: наличие топлива сообщают '
            'пользователи, оценка «снизу»); «транзакции идут» / «доступны» — <b>petrolplus</b> / '
            'АЗС-Локатор (высокая доступность транзакций на АЗС, безотносительно конкретной марки). '
            'Цена — petrolplus (выгрузка StationList.xls), медиана по свежим ценам (≤ дней из '
            'config; при малом числе — по всем). Дневные графики берут замер около заданного часа. '
            '«Независимые» — АЗС вне крупных ВИНК. АИ-98/100 продаются на немногих АЗС — ряды '
            'разреженные. Все величины справочные.</p>')


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    print("Собран:", build(base))
