# -*- coding: utf-8 -*-
"""
Сборка единой страницы public/index.html (v5) — мобильный, простой.

Меньше графиков, крупнее и понятнее. Обзор: 2 большие цифры (цена АИ-95 +
объединённый ИНДЕКС ДОСТУПНОСТИ из обоих источников) → карточки по видам →
5 ключевых графиков → ключевые события → таблицы по сетям.
"""

import html
import json
import os
from datetime import datetime, timezone
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
NET_COLORS = {"Роснефть": "--f92", "Газпромнефть": "--f100", "Лукойл": "--fdt"}


def _cfg(base):
    with open(os.path.join(base, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def _i(v):
    return int(v) if v is not None else None


# нормализация названий сетей (дубли регистра/языка → единый вид)
_BRAND_CANON = {
    "роснефть": "Роснефть", "rosneft": "Роснефть",
    "лукойл": "Лукойл", "lukoil": "Лукойл",
    "газпромнефть": "Газпромнефть", "газпром нефть": "Газпромнефть", "gazpromneft": "Газпромнефть",
    "газпром": "Газпром (газ)", "росгаз": "Росгаз (газ)", "пропан": "Пропан (газ)",
    "агзс": "АГЗС (газ)", "lpg": "LPG (газ)", "метан": "Метан (газ)",
    "татнефть": "Татнефть", "tatneft": "Татнефть",
    "teboil": "Teboil", "тебойл": "Teboil",
    "нефтьмагистраль": "Нефтьмагистраль", "shell": "Shell", "шелл": "Shell",
    "трасса": "Трасса", "опти": "Опти", "opti": "Опти", "башнефть": "Башнефть",
    "тнк": "ТНК", "tnk": "ТНК", "сургутнефтегаз": "Сургутнефтегаз",
}


def _norm_brand(name):
    if not name or not str(name).strip():
        return "Без бренда"
    key = str(name).strip().lower()
    if key in _BRAND_CANON:
        return _BRAND_CANON[key]
    for k, v in _BRAND_CANON.items():           # частичное совпадение (порядок важен)
        if k in key:
            return v
    s = str(name).strip()
    return s.title() if s.isupper() else s


# --- ДВА разнородных показателя доступности, НЕ усредняем ---
def _av_pcts(r):
    """Возвращает (work_pp, gd_bal):
    work_pp  — доля работающих АЗС (petrolplus, ПОЛНАЯ база) — честная станционная доступность.
    gd_bal   — БАЛАНС сообщений gdebenz: (есть+очередь+мало)/(все ответившие). Очередь/мало = топливо
               ЕСТЬ (с трудом), поэтому в «есть». Это оценка «снизу» (краудсорс смещён к жалобам),
               подписывается как «баланс сообщений», не как «доступность»."""
    y = analytics._val(r, "gb_yes"); no = analytics._val(r, "gb_no")
    q = analytics._val(r, "gb_queue"); low = analytics._val(r, "gb_low")
    resp = sum(x for x in (y, no, q, low) if x is not None)
    pos = sum(x for x in (y, q, low) if x is not None)
    gd_bal = round(100 * pos / resp, 1) if resp else None
    tot = analytics._val(r, "azs_total"); av = analytics._val(r, "azs_available")
    work_pp = round(100 * av / tot, 1) if (av is not None and tot) else None
    return work_pp, gd_bal


# ---------------------------------------------- Сводка по марке (ассистент) ---
def _work_pct(hist, f):
    n = _lv(hist, f"p_n_{f}")
    nav = _lv(hist, f"p_navail_{f}")
    return round(100 * nav / n) if (n and nav is not None) else None


def _fuel_summary(f, hist, drows, cfg):
    g = FUEL_TO_GRADE[f]
    fresh = _lv(hist, f"p_fresh_{f}")
    low = fresh is None or fresh < 15
    work = _work_pct(hist, f)
    n_sell = _lv(hist, f"p_n_{f}")
    spread = _lv(hist, f"net_spread_{f}")
    spread_d7 = analytics.daily_delta(drows, f"net_spread_{f}", 7)
    price_d7 = analytics.daily_delta(drows, f"p_med_{f}", 7)
    # тренд доступности вида — по petrolplus (полная база), не по смещённому краудсорсу
    avail_d7 = analytics.daily_delta(drows, f"p_navail_{f}", 7)
    # лучшее время — глобально по petrolplus (полная база), одинаково для всех марок
    havg, _ = analytics.by_hour(hist, "azs_available")
    hh = [h for h in range(24) if havg[h] is not None]
    best_hour = max(hh, key=lambda h: havg[h]) if len(hh) >= 6 else None
    wd = analytics.by_weekday(drows, "azs_available")
    wdi = [i for i in range(7) if wd[i] is not None]
    best_day = analytics.WEEKDAYS[max(wdi, key=lambda i: wd[i])] if len(wdi) >= 3 else None

    # что происходит
    if low:
        level, state = "unknown", f"{f}: данных мало — оценка неточная."
    elif work is None:
        level, state = "unknown", f"{f}: данных пока нет."
    elif work >= 88:
        level, state = "ok", f"Спокойно: {f} есть на большинстве работающих АЗС."
    elif work >= 74:
        level, state = "warn", f"Умеренный дефицит {f}: есть не везде, местами лимиты."
    else:
        level, state = "crit", f"Острый дефицит {f}: найти сложно."
    if spread is not None and spread >= 5 and not low:
        state += " Независимые заметно дороже сетей — признак напряжённости."

    # чего ждать
    if low or avail_d7 is None:
        trend = "Данных мало для тренда."
    else:
        thr = max(10, 0.04 * (n_sell or 300))
        a = ("Тренд на улучшение" if avail_d7 > thr else
             "Ухудшение" if avail_d7 < -thr else "Стабильно")
        pr = ("; цены растут" if (price_d7 or 0) > 0.2 else
              "; цены снижаются" if (price_d7 or 0) < -0.2 else "; цены стабильны")
        trend = a + pr + "."
        note = cfg.get("normalization_note", "")
        if note:
            trend += f" Ориентир: {note}."

    # что делать
    if level == "ok" and (avail_d7 is None or avail_d7 >= -8):
        act = "Заправляйтесь как обычно, спешки нет."
    elif level == "unknown":
        act = "Смотрите наличие по видам ниже."
    else:
        act = "Держите бак от 2/3, лучше залиться в ближайшие дни."
    if best_day and best_hour is not None:
        act += f" Оптимально: {best_day} около {best_hour:02d}:00."

    # барометр (на «мало данных» спред по маркам недостоверен — глушим)
    if low or spread is None:
        b_level, b_text = "unknown", ("мало данных" if low else "нет данных")
    elif spread < 3:
        b_level, b_text = "ok", "Спокойно"
    elif spread <= 6:
        b_level, b_text = "warn", "Напряжённость"
    else:
        b_level, b_text = "crit", "Дефицит усиливается"
    b_arrow = ("↑" if spread_d7 > 0 else "↓") if (spread_d7 is not None and abs(spread_d7) >= 0.1) else ""
    return dict(level=level, state=state, trend=trend, action=act, low=low,
               spread=spread, b_level=b_level, b_text=b_text, b_arrow=b_arrow)


def _summary_blocks(hist, drows, cfg):
    out = ""
    for i, f in enumerate(FUELS):
        s = _fuel_summary(f, hist, drows, cfg)
        badge = ""
        sp = (f' · спред {viz.fmt(s["spread"]," ₽")} <span class="baro-arrow">{s["b_arrow"]}</span>'
              if (s["spread"] is not None and not s["low"]) else "")
        out += (f'<div class="fsum" data-fuel="{html.escape(f)}"{"" if i == 1 else " hidden"}>'
                f'<div class="fs-row lvl-{s["level"]}"><span class="fs-ic"></span>'
                f'<div><div class="fs-lbl">Что происходит</div><div class="fs-txt">{html.escape(s["state"])}</div></div></div>'
                f'<div class="fs-row"><span class="fs-ic fs-ar">→</span>'
                f'<div><div class="fs-lbl">Чего ждать</div><div class="fs-txt">{html.escape(s["trend"])}</div></div></div>'
                f'<div class="fs-row"><span class="fs-ic fs-ok">✓</span>'
                f'<div><div class="fs-lbl">Что делать</div><div class="fs-txt">{html.escape(s["action"])}</div></div></div>'
                f'<div class="barometer bl-{s["b_level"]}">Барометр дефицита ({html.escape(f)}): '
                f'<b>{s["b_text"]}</b>{sp}{badge}</div></div>')
    return out


def _fuel_selector():
    btns = "".join(
        f'<button class="fbtn{" on" if i == 1 else ""}" data-fuel="{html.escape(f)}" data-si="{i}" '
        f'style="--c:var({viz.FUEL_VAR[f]})"><span class="fb-dot"></span>{html.escape(f)}</button>'
        for i, f in enumerate(FUELS))
    return f'<div class="fuelsel" role="tablist">{btns}</div>'


def build(base_dir, price_stations=None, gd_stations=None):
    cfg = _cfg(base_dir)
    hist = store.load_history()
    status = store.load_json(store.STATUS) or {}
    show_events = cfg.get("show_events", False)
    events = _load_events(base_dir) if show_events else []
    auto_events = _load_auto(base_dir) if show_events else []
    out_dir = os.path.join(base_dir, "public")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")

    if not hist:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(viz.wrap("Бензин · дашборд", "<p class='empty'>Данных ещё нет.</p>"))
        return out_path

    # два раздельных показателя — в каждую строку истории (для трендов и дельт)
    for r in hist:
        pp, gd = _av_pcts(r)
        r["work_pp"], r["gd_bal"] = pp, gd

    last = hist[-1]
    cur = lambda c: analytics._val(last, c)
    sample_hour = cfg.get("daily_sample_hour", 20)
    days, drows = analytics.daily_sample(hist, sample_hour)
    dlabels = [d.strftime("%d.%m") for d in days]

    body = "".join([
        _header(cfg, status, hist),
        _alerts(hist, cfg),
        f'<div class="sec">Сводка по марке {viz.help_badge("Три вывода по ВЫБРАННОЙ марке из текущих данных: что происходит (по доле работающих АЗС и спреду цен), чего ждать (тренд за 7 дней), что делать. Переключайте марку кнопками — меняются сводка, карточки и акцент на графиках. На марках «мало данных» тренд не считается.")}</div>',
        _fuel_selector(),
        _summary_blocks(hist, drows, cfg),
        _hero(hist, cur, drows),
        f'<div class="sec">По видам топлива {viz.help_badge("По каждому виду. Цена — petrolplus. «Продают» — сколько АЗС продают вид. «Из них станция работает %» — доля продающих АЗС, где идут транзакции (petrolplus). ВАЖНО: это СТАНЦИОННЫЙ сигнал (станция вообще торгует), не гарантия именно этого вида — работающая АЗС обычно отпускает все свои виды, но не всегда. «gdebenz (сообщений «есть»)» — сколько пользователей отметили наличие (краудсорс, оценка снизу). Это разные метрики, не смешивать.", _v_fuel_avail(hist))}</div>',
        f'<div class="fuelgrid">{"".join(_fuel_card(f, hist, cur, drows) for f in FUELS)}</div>',
        _availability_chart(cfg, hist, drows, dlabels),
        _price_charts(cfg, hist, days, drows, dlabels, events + auto_events),
        _timing_charts(hist, drows),
        (_events_section(events, auto_events) if show_events else ""),
        '<div class="sec">По сетям · последний замер</div>',
        '<div class="stat-row" style="margin:-6px 0 12px"><span>⚠ Две таблицы — про '
        '<b>разные наборы АЗС</b>: «Цены» из petrolplus, «Наличие» из gdebenz (разные базы). '
        'Число АЗС у одной сети в них отличается — напрямую не сравнивайте.</span></div>',
        f'<section class="card"><h2>Цены по сетям <span class="hint">медиана, ₽ · источник petrolplus</span>{viz.help_badge("Медиана цены по каждой сети и виду (petrolplus). Названия сетей нормализованы (дубли регистра/языка сведены), «Без бренда» — АЗС без распознанной сети.", _v_spread(hist))}</h2>{_price_brand_table(price_stations)}</section>',
        f'<section class="card"><h2>Наличие по сетям <span class="hint">число АЗС «есть» · источник gdebenz</span>{viz.help_badge("По каждой сети: сколько АЗС со статусом «есть» и на скольких сейчас есть каждый вид (gdebenz, краудсорс). Это ДРУГОЙ набор АЗС, чем в «Ценах по сетям».")}</h2>{_gdebenz_brand_table(gd_stations)}</section>',
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
        return f"{int(mins)} мин назад", viz.ST_GOOD
    if mins < 60 * 12:
        return f"{int(mins//60)} ч назад", viz.ST_WARN
    return f"{int(mins//1440)} дн назад", viz.ST_CRIT


def _header(cfg, status, hist):
    ps, gs = status.get("prices") or {}, status.get("gdebenz") or {}
    p_ago, p_c = _ago(ps.get("ts_msk"))
    g_ago, g_c = _ago(gs.get("ts_msk"))
    ndays = analytics.monitoring_days(hist)
    fresh = (f'<div class="fresh">'
             f'<span class="fbadge" style="border-color:var({p_c})">'
             f'<span class="dot" style="background:var({p_c})"></span>Цены · petrolplus: <b>{html.escape(p_ago)}</b></span>'
             f'<span class="fbadge" style="border-color:var({g_c})">'
             f'<span class="dot" style="background:var({g_c})"></span>Наличие · gdebenz: <b>{html.escape(g_ago)}</b></span>'
             f'<span class="fdays">{ndays} дн наблюдений</span></div>')
    return (f'<header><h1>Бензин · Москва и область</h1>'
            f'<div class="meta">Обновляется каждый час · {html.escape(cfg.get("region_name",""))}</div>'
            f'</header>{fresh}')


# ------------------------------------------------------------------ alerts ---
def _alerts(hist, cfg):
    al = cfg.get("alerts", {})
    msgs = []
    yes = analytics._val(hist[-1], "gb_yes")
    ymin = al.get("avail_yes_min")
    if yes is not None and ymin is not None and yes < ymin:
        msgs.append(f"Мало сообщений «есть»: <b>{int(yes)}</b> (порог {int(ymin)}) — возможен дефицит.")
    thr = al.get("price_day_rise_pct")
    d = analytics.delta(hist, "p_med_АИ-95", 24)
    base = analytics.value_at_ago(hist, "p_med_АИ-95", 24)
    if d is not None and base and thr is not None and 100 * d / base >= thr:
        msgs.append(f"АИ-95 подорожал на <b>{100*d/base:.1f}%</b> за сутки.")
    return ('<div class="alert">⚠ ' + "<br>".join(msgs) + "</div>") if msgs else ""


# -------------------------------------------------------------------- hero ---
def _hero(hist, cur, drows):
    price_tile = _tile(
        "Медиана цены АИ-95", viz.fmt(cur("p_med_АИ-95"), " ₽"),
        viz.sparkline(analytics.col(drows, "p_med_АИ-95"), "--f95", w=120, h=38),
        _dd(drows, "p_med_АИ-95", " ₽", good_down=True),
        viz.help_badge("Медианная цена АИ-95 по всем АЗС в рамке (устойчивее среднего к выбросам). "
                       "Изменение — по дневной выборке (тот же час к тому же часу).",
                       _v_price95(hist)))
    av_tile = _tile(
        "Работающих АЗС", viz.fmt(cur("work_pp"), " %"),
        viz.sparkline(analytics.col(drows, "work_pp"), viz.ST_GOOD, w=120, h=38),
        _dd(drows, "work_pp", " %", good_down=False),
        viz.help_badge("Доля всех АЗС, где идут транзакции (petrolplus, ПОЛНАЯ база) — честная "
                       "станционная доступность (не по видам). Отдельно ниже — «баланс сообщений» "
                       "по gdebenz (краудсорс, оценка снизу); их НЕ усредняем — это разные вещи.",
                       _v_work(hist)))
    return f'<div class="tiles c2">{price_tile}{av_tile}</div>'


def _tile(label, value, spark, dd, help_html):
    return (f'<div class="tile big"><div class="t-label">{label} {help_html}</div>'
            f'<div class="t-row"><div class="t-value">{value}</div>{spark}</div>'
            f'<div class="t-delta">{dd}</div></div>')


def _dd(drows, col_name, unit="", good_down=True):
    # дельты строго по дневной выборке (тот же час), не «ближайший замер»
    parts = []
    for lbl, days in (("сут", 1), ("нед", 7)):
        d = analytics.daily_delta(drows, col_name, days)
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
def _fuel_card(f, hist, cur, drows):
    g = FUEL_TO_GRADE[f]
    var = viz.FUEL_VAR[f]
    med = cur(f"p_med_{f}")
    n = _i(cur(f"p_n_{f}"))                 # продают этот вид (petrolplus)
    fresh = _i(cur(f"p_fresh_{f}"))         # свежих цен за медианой
    navail = _i(cur(f"p_navail_{f}"))       # из них с высокой доступностью (работают)
    now = _i(cur(f"gb_now_{g}"))            # gdebenz: краудсорс-подтверждение
    share = viz.pct(navail or 0, n) if n else None   # знаменатель = ПРОДАЮЩИЕ, не все
    spark = viz.sparkline(analytics.col(drows, f"p_med_{f}"), var, w=84, h=30)
    low = fresh is None or fresh < 15       # разреженная статистика цены
    badge = ' <span class="ev-auto" title="цена по малому числу свежих АЗС — шумно">мало данных</span>' if low else ""
    return f"""
    <div class="fuelcard" data-fuel="{html.escape(f)}" style="--accent:var({var})">
      <div class="fc-head"><span class="fc-dot" style="background:var({var})"></span>
        <span class="fc-name">{html.escape(f)}</span>{badge}</div>
      <div class="fc-price"><div class="fc-val">{viz.fmt(med,' ₽') if med is not None else '—'}</div>{spark}</div>
      <div class="fc-avail">
        <div class="fc-arow"><span class="lbl">Продают</span><span class="num">{viz.fmt(n)} АЗС</span></div>
        <div class="fc-arow"><span class="lbl">Из них станция работает</span><span class="num">{viz.fmt(share)}%</span></div>
        {viz.meter(share, viz.ST_GOOD)}
        <div class="fc-sub" style="margin-top:6px">gdebenz (сообщений «есть»): {viz.fmt(now)}</div>
      </div>
    </div>"""


# --------------------------------------------------------- availability ---
def _availability_chart(cfg, hist, drows, dlabels):
    ma_n = cfg.get("ma_days", 3)
    wp = analytics.col(drows, "work_pp")
    work_chart = viz.line_chart("availwork", dlabels, [
        {"name": "Работающих АЗС, %", "var": viz.ST_GOOD, "points": wp},
        {"name": f"{ma_n}-дн. среднее", "var": "--f95", "points": analytics.moving_avg(wp, ma_n)},
    ], unit=" %", end_labels=False)
    gd_chart = viz.line_chart("availgd", dlabels, [
        {"name": "Баланс сообщений, %", "var": "--f92", "points": analytics.col(drows, "gd_bal")},
    ], unit=" %", area=True, end_labels=False)
    status_chart = viz.line_chart("gbstatus", dlabels, [
        {"name": "Есть", "var": viz.ST_GOOD, "points": analytics.col(drows, "gb_yes")},
        {"name": "Очередь", "var": viz.ST_SERIOUS, "points": analytics.col(drows, "gb_queue")},
        {"name": "Мало", "var": viz.ST_WARN, "points": analytics.col(drows, "gb_low")},
        {"name": "Нет", "var": viz.ST_CRIT, "points": analytics.col(drows, "gb_no")},
    ], y_int=True, end_labels=False)
    fuel_avail = viz.line_chart("availfuel", dlabels,
        [{"name": f, "var": viz.FUEL_VAR[f], "points": analytics.col(drows, f"gb_now_{FUEL_TO_GRADE[f]}")}
         for f in FUELS], y_int=True, end_labels=False)
    return f"""
    <div class="sec">Доступность топлива</div>
    <section class="grid2">
      <div class="card"><h2>Работающих АЗС, % <span class="hint">petrolplus · полная база + {ma_n}-дн. среднее</span>{viz.help_badge("Доля всех АЗС, где идут транзакции (petrolplus, полная база) — честная станционная доступность (не по видам). ПРАВЫЙ график — это про другое: баланс сообщений пользователей (gdebenz), не смешивать.", _v_work(hist))}</h2>
        {viz.legend([("Работающих АЗС, %", viz.ST_GOOD), (f"{ma_n}-дн. среднее", "--f95")], "availwork")}{work_chart}</div>
      <div class="card"><h2>Баланс сообщений о наличии, % <span class="hint">gdebenz · краудсорс</span>{viz.help_badge("(есть+очередь+мало) ÷ все сообщения пользователей о станции. НЕ «доля АЗС с топливом»: краудсорс смещён к жалобам (люди чаще отмечают проблемы), охват неполный. Это индикатор настроения/дефицита, а не полная доступность. Очередь и «мало» здесь считаются как «топливо есть».", _v_gd_bal(hist))}</h2>
        {gd_chart}</div>
    </section>
    <section class="grid2">
      <div class="card"><h2>Статусы АЗС <span class="hint">gdebenz · сообщения · по дням</span>{viz.help_badge("Число сообщений пользователей по статусам. «Есть/Очередь/Мало» — топливо ЕСТЬ (очередь/мало — с трудом); «Нет» — топлива нет. Это отметки людей о станции (любое топливо), не сумма по видам и не полная база.", _v_fuel_avail(hist))}</h2>
        {viz.legend([("Есть", viz.ST_GOOD, "rect"), ("Очередь", viz.ST_SERIOUS, "rect"), ("Мало", viz.ST_WARN, "rect"), ("Нет", viz.ST_CRIT, "rect")], "gbstatus")}{status_chart}</div>
      <div class="card"><h2>Наличие по видам, сообщений <span class="hint">gdebenz · по дням</span>{viz.help_badge("Сколько АЗС пользователи отметили как имеющие марку сейчас (gdebenz, краудсорс — оценка снизу). Видно, какой вид просаживается первым.", _v_fuel_avail(hist))}</h2>
        {viz.legend([(f, viz.FUEL_VAR[f]) for f in FUELS], "availfuel")}{fuel_avail}</div>
    </section>"""


# ---------------------------------------------------------------- prices ---
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
        if ed < lo or ed > hi:
            continue
        idx = next((i for i, d in enumerate(days) if d >= ed), len(days) - 1)
        anns.append({"i": idx, "label": "◆", "full": f'{e["date"]}: {e["title"]}'})
    return anns[:6]


def _price_charts(cfg, hist, days, drows, dlabels, all_events):
    anns = _event_annotations(all_events, days)
    price_daily = viz.line_chart("pxday", dlabels,
        [{"name": f, "var": viz.FUEL_VAR[f], "points": analytics.col(drows, f"p_med_{f}")} for f in FUELS],
        unit=" ₽", annotations=anns, end_labels=False)
    net_series = [
        {"name": "Независимые", "var": viz.ST_CRIT, "points": analytics.col(drows, "indep95_med")},
        {"name": "Сети", "var": "--f95", "points": analytics.col(drows, "net95_med")},
    ]
    for nw in cfg.get("tracked_networks", []):
        net_series.append({"name": nw, "var": NET_COLORS.get(nw, "--f98"),
                           "points": analytics.col(drows, f"net95_{nw}")})
    net = viz.line_chart("pxnet", dlabels, net_series, unit=" ₽", end_labels=False)
    spread = viz.line_chart("spread", dlabels,
        [{"name": "Спред", "var": viz.ST_SERIOUS, "points": analytics.col(drows, "spread95")}],
        unit=" ₽", area=True, end_labels=False)
    return f"""
    <div class="sec">Цены · динамика и сигнал дефицита</div>
    <section class="card"><h2>Медианная цена по видам <span class="hint">по дням · ₽ · наведите для значений</span>{viz.help_badge("Медианная цена каждого вида по дням (замер около заданного часа — без внутрисуточного шума).", _v_price95(hist))}</h2>
      {viz.legend([(f, viz.FUEL_VAR[f]) for f in FUELS], "pxday")}{price_daily}</section>
    <section class="grid2">
      <div class="card"><h2>АИ-95: независимые vs сети <span class="hint">₽ · по дням</span>{viz.help_badge("Независимые АЗС (вне ВИНК) поднимают цены раньше сетей — их отрыв сигналит о дефиците. Смотрите на ДИНАМИКУ (направление), а не на абсолют: медианы считаются по разным наборам АЗС, поэтому спред отражает и тип АЗС, и географию, не только дефицитную наценку.", _v_spread(hist))}</h2>
        {viz.legend([("Независимые", viz.ST_CRIT), ("Сети", "--f95")] + [(nw, NET_COLORS.get(nw, "--f98")) for nw in cfg.get("tracked_networks", [])], "pxnet")}{net}</div>
      <div class="card"><h2>Насколько независимые дороже <span class="hint">спред, ₽ · по дням</span>{viz.help_badge("Разница медиан: независимые минус сети. РОСТ = дефицит усиливается (ранний сигнал). Важно направление, не абсолют: наборы АЗС разные (тип+география), поэтому абсолютное значение спреда переоценивать не стоит.", _v_spread(hist))}</h2>
        {spread}</div>
    </section>"""


# ---------------------------------------------------------------- timing ---
def _timing_charts(hist, drows):
    # строим на petrolplus (полная база, azs_available), а не на смещённых по времени отметках gdebenz
    hour_avg, _ = analytics.by_hour(hist, "azs_available")
    have = [h for h in range(24) if hour_avg[h] is not None]
    best_txt = (f"Больше всего работающих АЗС около <b>{max(have, key=lambda h: hour_avg[h]):02d}:00</b> МСК"
                if len(have) >= 6 else "Копим почасовые данные…")
    hour_bars = viz.bar_chart([str(h) for h in range(24)], hour_avg, var=viz.ST_GOOD, highlight="max")
    wd = analytics.by_weekday(drows, "azs_available")
    wd_bars = viz.bar_chart(analytics.WEEKDAYS, wd, var=viz.ST_GOOD, highlight="max", unit=" АЗС")
    return f"""
    <div class="sec">Когда заправляться</div>
    <section class="grid2">
      <div class="card"><h2>Лучшее время заправки <span class="hint">работающих АЗС по часу · petrolplus</span>{viz.help_badge("Среднее число РАБОТАЮЩИХ АЗС по часу суток (petrolplus, полная база). Считаем по нему, а не по отметкам gdebenz: краудсорс смещён по времени (днём отметок больше просто из-за активности людей, а не наличия). Зелёный столбец — когда работающих АЗС обычно больше.", _v_best_hour(hist))}</h2>
        <div class="stat-row" style="margin:0 0 8px">{best_txt}</div>{hour_bars}</div>
      <div class="card"><h2>Лучший день для заправки <span class="hint">работающих АЗС по дням · petrolplus</span>{viz.help_badge("Среднее число работающих АЗС (petrolplus) по дням недели. Зелёный столбец — день, когда заправиться обычно легче.", _v_best_day(drows))}</h2>
        {wd_bars}</div>
    </section>"""


# ----------------------------------------------------------------- events ---
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


def _events_section(manual, auto):
    hb = viz.help_badge("Ключевые новости по топливу (Google News) + ваши ручные пометки "
                        "(events.json). ◆ на графике цен — событие в его диапазоне. Автоподборка "
                        "не проверена — сверяйтесь с источником.")

    def item(e, is_auto):
        title = html.escape(str(e.get("title", "")))
        link = (f'<a href="{html.escape(e["url"])}" target="_blank" rel="noopener">{title}</a>'
                if e.get("url") else title)
        src = f'<span class="ev-src">· {html.escape(e.get("source",""))}</span>' if e.get("source") else ""
        badge = '<span class="ev-auto">авто</span>' if is_auto else ""
        return (f'<li><span class="ed">{html.escape(str(e.get("date","")))}</span>'
                f'<span>{link} {src} {badge}</span></li>')

    rows = "".join(item(e, False) for e in sorted(manual, key=lambda x: x.get("date", ""), reverse=True))
    rows += "".join(item(e, True) for e in auto[:6])          # только ключевые
    inner = (f'<ul class="events">{rows}</ul>' if rows else
             '<div class="fc-sub">Подборка новостей появится после ближайшего сбора.</div>')
    return (f'<div class="sec">Ключевые события {hb}</div><section class="card">{inner}'
            '<div class="fc-sub" style="margin-top:8px">«авто» — из новостей (Google News), '
            '<b>проверяйте по источнику</b>.</div></section>')


# ------------------------------------------------------------------ tables ---
def _price_brand_table(stations):
    if not stations:
        return "<div class='empty'>Снимок появится после ближайшего сбора</div>"
    agg = {}
    for s in stations:
        a = agg.setdefault(_norm_brand(s.get("brand")), {"n": 0, "p": {f: [] for f in FUELS}})
        a["n"] += 1
        for f in FUELS:
            v = (s.get("prices") or {}).get(f)
            if v is not None:
                a["p"][f].append(v)
    head = "".join(f"<th>{html.escape(f)}</th>" for f in FUELS)
    trs = ""
    for b, a in sorted(agg.items(), key=lambda kv: -kv[1]["n"])[:12]:
        cells = ""
        for f in FUELS:
            vals = a["p"][f]
            cells += (f'<td>{viz.fmt(round(median(vals),2)," ₽")}</td>' if vals else '<td>—</td>')
        trs += f'<tr><td class="b">{html.escape(b)}</td><td>{a["n"]}</td>{cells}</tr>'
    return ('<div class="tablewrap"><table class="tbl"><thead><tr><th>Сеть</th><th>АЗС</th>'
            + head + '</tr></thead><tbody>' + trs + '</tbody></table></div>')


def _gdebenz_brand_table(stations):
    if not stations:
        return "<div class='empty'>Снимок появится после ближайшего сбора</div>"
    grades = [FUEL_TO_GRADE[f] for f in FUELS]
    agg = {}
    for s in stations:
        a = agg.setdefault(_norm_brand(s.get("brand")), {"n": 0, "yes": 0, **{g: 0 for g in grades}})
        a["n"] += 1
        a["yes"] += 1 if s.get("status") == "yes" else 0
        fs = {x.strip() for x in (s.get("fuels_now") or "").split(",") if x.strip()}
        for g in grades:
            if g in fs:
                a[g] += 1
    ghead = "".join(f"<th>{html.escape('АИ-'+g if g != 'ДТ' else g)}</th>" for g in grades)
    trs = ""
    for b, a in sorted(agg.items(), key=lambda kv: -kv[1]["n"])[:12]:
        cells = "".join(f'<td>{a[g] or "—"}</td>' for g in grades)
        trs += f'<tr><td class="b">{html.escape(b)}</td><td>{a["n"]}</td><td>{a["yes"]}</td>{cells}</tr>'
    return ('<div class="tablewrap"><table class="tbl"><thead><tr><th>Сеть</th><th>АЗС</th>'
            '<th>Есть</th>' + ghead + '</tr></thead><tbody>' + trs + '</tbody></table></div>')


def _footer():
    return ('<p class="foot"><b>Работающих АЗС %</b> — доля всех АЗС с транзакциями (petrolplus, '
            'полная база) — честная станционная доступность. <b>Баланс сообщений %</b> = '
            '(есть+очередь+мало) ÷ все отметки пользователей (gdebenz, краудсорс, смещён к жалобам) — '
            'индикатор настроения/дефицита, НЕ полная доступность; очередь/мало = топливо есть с трудом. '
            'Эти два НЕ усредняем — разные вещи. По видам: «станция работает %» — станционный сигнал '
            '(станция торгует), не гарантия конкретного вида. Цена — petrolplus, медиана по свежим '
            'ценам. Спред «независимые − сети» — ранний сигнал дефицита (важно направление, не абсолют). '
            'Дельты — по дневной выборке (тот же час). Всё справочно.</p>')


# --------------------------------------------------------------- verdicts ---
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
                   (f" на {viz.fmt(abs(d7),' ₽')} ({p:+.1f}%)" if abs(d7) > 0.01 and p is not None else ""))
    if d24 is not None and abs(d24) >= 0.02:
        seg.append(f"за сутки {'↑' if d24 > 0 else '↓'}{viz.fmt(abs(d24),' ₽')}")
    return "АИ-95 " + ", ".join(seg) + "."


def _v_work(hist):
    pp, _ = _av_pcts(hist[-1])
    if pp is None:
        return "Данные копятся."
    return f"Сейчас работают {pp}% всех АЗС (petrolplus, полная база)."


def _v_gd_bal(hist):
    _, gd = _av_pcts(hist[-1])
    if gd is None:
        return "Сообщений пока мало."
    return (f"Баланс сообщений {gd}% (есть+очередь+мало). Это настроение пользователей, "
            f"а не полная доступность — краудсорс смещён к жалобам.")


def _v_spread(hist):
    cur = _lv(hist, "spread95")
    if cur is None:
        return "Данные по сетям/независимым копятся."
    d7 = analytics.delta(hist, "spread95", 168)
    s = f"Независимые дороже сетей на {viz.fmt(cur,' ₽')}."
    if d7 is not None and abs(d7) >= 0.1:
        s += (f" Спред за неделю {'вырос' if d7 > 0 else 'сузился'} на {viz.fmt(abs(d7),' ₽')}"
              f" → дефицит {'усиливается' if d7 > 0 else 'ослабевает'}.")
    return s


def _v_fuel_avail(hist):
    items = [(f, _lv(hist, f"gb_now_{FUEL_TO_GRADE[f]}")) for f in FUELS]
    items = [(f, v) for f, v in items if v is not None]
    if not items:
        return "Данные копятся."
    f, v = min(items, key=lambda x: x[1])
    return f"Реже всего отмечают наличие {f} ({int(v)} АЗС по gdebenz)."


def _v_best_hour(hist):
    avg, _ = analytics.by_hour(hist, "azs_available")
    have = [h for h in range(24) if avg[h] is not None]
    if len(have) < 6:
        return "Нужно ≥ суток почасовых данных — копится."
    return f"Больше всего работающих АЗС около {max(have, key=lambda h: avg[h]):02d}:00 МСК."


def _v_best_day(drows):
    wd = analytics.by_weekday(drows, "azs_available")
    have = [i for i in range(7) if wd[i] is not None]
    if len(have) < 3:
        return "Нужно несколько дней — копится."
    best = max(have, key=lambda i: wd[i])
    worst = min(have, key=lambda i: wd[i])
    return (f"Больше всего работающих АЗС в {analytics.WEEKDAYS[best]}, меньше — "
            f"в {analytics.WEEKDAYS[worst]}.")


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    print("Собран:", build(base))
