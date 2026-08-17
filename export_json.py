# -*- coding: utf-8 -*-
"""
Экспорт всех метрик в web/public/data.json — его читает React-дашборд (web/).
Переиспользует логику build_dashboard (сводка ассистента, показатели, разрезы).
Вызывается из run.py со снимками станций (для таблиц/карты).
"""

import json
import os
from statistics import median

import store
import analytics
import build_dashboard as bd
import geo

BASE = os.path.dirname(os.path.abspath(__file__))
FUELS = bd.FUELS
G = bd.FUEL_TO_GRADE
FUEL_HEX = {"АИ-92": "f92", "АИ-95": "f95", "АИ-98": "f98", "АИ-100": "f100", "ДТ": "fdt"}


def _lv(hist, c):
    return analytics._val(hist[-1], c) if hist else None


def build_payload(base_dir, price_stations=None, gd_stations=None, region=None, cfg=None, status=None):
    if cfg is None:
        with open(os.path.join(base_dir, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
    region = region or {}
    slug = region.get("slug", "msk")
    hist = store.load_history(store.history_path(slug))
    if status is None:
        status = store.load_json(store.STATUS) or {}
    if slug != "msk":                       # статус региона лежит в своей ветке
        status = (status.get("regions") or {}).get(slug) or {}
    if not hist:
        return {"empty": True}

    # доп. показатели в строки (как в build_dashboard)
    for r in hist:
        pp, gd = bd._av_pcts(r)
        r["work_pp"], r["gd_bal"] = pp, gd
        # availShare по каждой марке (для честного тренда: navail / полная база)
        tot_r = analytics._val(r, "azs_total")
        gbt_r = analytics._val(r, "gb_total")
        for f in FUELS:
            nv = analytics._val(r, f"p_navail_{f}")
            r[f"avs_{f}"] = round(100 * nv / tot_r, 1) if (nv is not None and tot_r) else None
            # доля станций gdebenz, подтвердивших марку (для графика «подтверждено» по марке)
            nw = analytics._val(r, f"gb_now_{G[f]}")
            r[f"gbs_{G[f]}"] = round(100 * nw / gbt_r, 1) if (nw is not None and gbt_r) else None

    days, drows = analytics.daily_sample(hist, cfg.get("daily_sample_hour", 20))
    dlabels = [d.strftime("%d.%m") for d in days]
    cur = lambda c: _lv(hist, c)
    tot = cur("azs_total")
    min_fresh = cfg.get("min_fresh_prices", 30)

    ps, gs = status.get("prices") or {}, status.get("gdebenz") or {}
    p_ago, _ = bd._ago(ps.get("ts_msk"))
    g_ago, _ = bd._ago(gs.get("ts_msk"))

    def col(name):
        return analytics.col(drows, name)

    # --- trust-first константы/помощники ---
    mon_days = analytics.monitoring_days(hist)
    gb_total = cur("gb_total")
    n_report = cur("gb_n_report")            # станции, сообщившие состав топлива
    gd_resp = sum(x for x in (cur("gb_yes"), cur("gb_no"), cur("gb_queue"), cur("gb_low"))
                  if x is not None) or None
    # доля станций, которые вообще отпускают (устойчива к времени суток: размах 0.98x)
    _pos = sum(x for x in (cur("gb_yes"), cur("gb_queue"), cur("gb_low")) if x is not None)
    station_ok = (_pos / gd_resp) if gd_resp else None
    # покрытие gdebenz в этом прогоне: краудсорс собирает то больше, то меньше АЗС.
    # Нормируем r на покрытие, иначе меньшая выборка gdebenz роняет r у ВСЕХ марок
    # и ложно красит массовые марки в жёлтый (шум сбора, а не дефицит).
    gd_cover = gd_resp / tot if (gd_resp and tot) else None
    WORD = {"green": "Есть почти везде", "yellow": "Есть не на каждой",
            "red": "Редко", "gray": "Наличие не подтверждено"}
    ACT = {"green": "заправляйтесь как обычно", "yellow": "планируйте, держите запас",
           "red": "держите бак полным, ищите заранее", "gray": "данные не удалось подтвердить сейчас"}
    TRW = {"up": "Ситуация выправляется", "down": "Дефицит усиливается", "stable": "Стабильно"}

    def _clamp(v, lo, hi):
        return max(lo, min(hi, v))

    # --- по каждой марке ---
    fuels = {}
    for f in FUELS:
        g = G[f]
        n = cur(f"p_n_{f}")
        fresh = cur(f"p_fresh_{f}")
        navail = cur(f"p_navail_{f}")
        now = cur(f"gb_now_{g}")
        age = cur(f"p_age_{f}")
        low = fresh is None or fresh < min_fresh
        diverge = bool((now or 0) >= 40 and (now or 0) >= 3 * ((fresh or 0) + 1))

        # ДВЕ границы доступности (обе несовершенны, правда между ними):
        #  availShare (petrolplus) = navail/azs_total — ВЕРХНЯЯ: в прайсе И станция работает.
        #    НО «работает» — station-level (отпускает любое топливо), не значит, что ЭТА марка залита.
        #  physShare  (gdebenz)    = now/gb_total — физически подтверждено людьми (оценка снизу).
        # ВАЖНО: каждая доля считается ВНУТРИ своего каталога. Базы разного размера
        # (в Тверской petrolplus знает ~130 АЗС, gdebenz ~290) — деля крауд-числитель на
        # каталог petrolplus, мы бы раздули долю вдвое.
        avail_share = _int(_clamp(round(100 * navail / tot), 0, 100)) if (navail is not None and tot) else None
        # Нижняя граница БЕЗ суточного шума.
        # Проблема: now/gb_total скачет вдвое за сутки (ночью 16%, вечером 30%), потому что
        # состав топлива (fuels_now) заполняется активностью людей, а не наличием.
        # Решение: разложить на две устойчивые части (проверено на 41 дне, размах по часам 1.06x):
        #   P(есть марка) = P(станция вообще отпускает) x P(есть марка | сообщили состав)
        # Обе доли считаются внутри одного слоя, поэтому активность сокращается.
        if now is not None and n_report and station_ok is not None:
            phys_share = _int(_clamp(round(100 * station_ok * now / n_report), 0, 100))
        else:
            # НЕ подставляем запасную формулу: она даёт другое число (34% против 63%) и делает
            # сайт невоспроизводимым из репозитория. Нет отчётов водителей — нет нижней границы.
            phys_share = None
        gd_share = _int(round(100 * now / gd_resp)) if (now is not None and gd_resp) else None  # физ. оценка
        r = round(now / navail, 2) if (now is not None and navail) else None
        r_norm = round(r / gd_cover, 2) if (r is not None and gd_cover) else None
        # крауд-цена: доверяем только если её дали хотя бы MIN_CPN АЗС (иначе шум одиночек)
        MIN_CPN = 10
        cpn = cur(f"cpn_{g}")
        cprice = cur(f"cp_{g}") if (cpn or 0) >= MIN_CPN else None
        pp_price = cur(f"p_med_{f}")
        price_agree = None
        if cprice is not None and pp_price:
            price_agree = round(cprice - pp_price, 2)   # расхождение крауд vs прайс, ₽

        pp_healthy = (fresh is not None and fresh >= min_fresh) and (age is None or age <= 12)
        blinded = bool(r is not None and r > 3 and not pp_healthy)  # petrolplus ослеп по марке
        avail_conf = "low" if ((navail is None) or (n is None) or (n < 8) or blinded) else "high"

        # светофор — по ХУДШЕЙ из двух границ: не называем «есть», пока физически не подтвердили
        RANK = {"green": 3, "yellow": 2, "red": 1}
        def _band(sh):
            if sh is None:
                return None
            return "green" if sh >= 50 else ("yellow" if sh >= 20 else "red")
        if avail_share is None and now is None:
            level = "gray"
        elif now is None:                              # физически не подтверждено — не выше жёлтого
            b = _band(avail_share)
            level = "yellow" if b == "green" else b
        elif avail_share is None:
            level = _band(phys_share) or "gray"
        else:
            # по ХУДШЕЙ из границ, но нижняя берётся УСТОЙЧИВАЯ (phys_share), а не gd_share:
            # gd_share шумит вдвое за сутки, из-за чего цвет менялся от времени открытия сайта
            bands = [b for b in (_band(avail_share), _band(phys_share)) if b]
            level = min(bands, key=lambda x: RANK[x]) if bands else "gray"
            if level == "green" and (age is not None and age > 12):
                level = "yellow"                       # зелёный запрещён при старье

        # тренд по Δ(availShare); пока <3 дней — честное «накопление»
        tr = analytics.daily_delta(drows, f"avs_{f}", 3)
        if mon_days < 3 or tr is None:
            trend_state = "накопление"
        elif tr <= -3:
            trend_state = "down"
        elif tr >= 3:
            trend_state = "up"
        else:
            trend_state = "stable"

        if trend_state == "down" and level in ("green", "yellow"):
            action = "залейтесь в ближайшие дни — предложение снижается"
        else:
            action = ACT[level]
        trend_label = ("Наблюдаем первые дни — направление появится через ~3 суток"
                       if trend_state == "накопление" else TRW[trend_state])

        # --- прогноз на завтра ---
        # Проверено скользящей проверкой на 21 дне: сложная модель (сегодня + жалобы «нет»)
        # НЕ лучше наивной «завтра как сегодня» (1.81 vs 1.80 п.п.). Поэтому не выдумываем
        # модель, а честно даём инерцию + измеренный разброс суточных изменений.
        fc = None
        if mon_days >= 7:
            hist_avs = [x for x in col(f"avs_{f}") if x is not None]
            if len(hist_avs) >= 7:
                jumps = [abs(hist_avs[i + 1] - hist_avs[i]) for i in range(len(hist_avs) - 1)]
                jumps.sort()
                typ = jumps[len(jumps) // 2]                      # медианное суточное изменение
                band = max(2, round(jumps[int(0.9 * (len(jumps) - 1))]))   # p90 — честный коридор
                # ВАЖНО: прогноз относится к ТОМУ ЖЕ числу, что показано главным (к диапазону
                # целиком), а не к одной верхней границе — иначе рядом с «32–76%» появлялось
                # «завтра 72–80%», и это читалось как обещание роста.
                fc = {"typical": round(typ, 1), "band": _int(band),
                      "text": f"завтра примерно то же — за сутки обычно меняется на {typ:.1f} п.п. "
                              f"(редко больше {band})"}

        s = bd._fuel_summary(f, hist, drows, cfg)
        fuels[f] = {
            "grade": g, "color": FUEL_HEX[f],
            "price": cur(f"p_med_{f}"),
            "price_d1": analytics.daily_delta(drows, f"p_med_{f}", 1),
            "price_d7": analytics.daily_delta(drows, f"p_med_{f}", 7),
            "n": _int(n), "fresh": _int(fresh), "navail": _int(navail), "now": _int(now),
            "age": age,
            # --- trust-first поля (ведущие) ---
            "availShare": avail_share, "physShare": phys_share, "gdShare": gd_share,
            "r": r, "rNorm": r_norm, "blinded": blinded,
            # крауд-цена (новое поле gdebenz prices_now): независимая проверка цены petrolplus
            "cPrice": cprice, "cPriceN": _int(cpn), "priceAgree": price_agree,
            "availConf": avail_conf, "level": level,
            "forecast": fc,
            "verdict": {"word": WORD[level], "action": action, "trendLabel": trend_label,
                        "confBadge": "данные надёжны" if avail_conf == "high" else "данных мало, оценка снизу",
                        "trendState": trend_state},
            # --- прежние поля (для свёрнутых деталей/легаси) ---
            "share_all": _pct(n, tot), "work_pct": _pct(navail, n),
            "low": low, "diverge": diverge,
            "priceReliable": not low, "priceSuspect": False, "priceTrusted": False,
            "spread": cur(f"net_spread_{f}"),
            "spread_d7": analytics.daily_delta(drows, f"net_spread_{f}", 7),
            "summary": {"level": s["level"], "state": s["state"], "trend": s["trend"],
                        "action": s["action"], "baroLevel": s["b_level"],
                        "baroText": s["b_text"], "baroArrow": s["b_arrow"]},
            "series": {
                "price": col(f"p_med_{f}"),
                "now": col(f"gb_now_{g}"),
                "spread": col(f"net_spread_{f}"),
                "net": col(f"net_net_{f}"), "indep": col(f"net_indep_{f}"),
                # ряды ПО МАРКЕ для переключаемых графиков доступности
                "avail": col(f"avs_{f}"),          # % всех АЗС, где марка в прайсе и станция работает
                "confirm": col(f"gbs_{g}"),        # % станций gdebenz, подтвердивших марку
            },
            # срез «фокус региона» именно по этой марке (внутри МКАД / Конаковский р-н)
            "geo": _focus_split(gd_stations, region.get("focus"), grade=g),
        }

    # «Октановый абсурд» TOL 0.10 ₽ -> priceSuspect; затем priceTrusted (что показывать)
    ladder = ["АИ-92", "АИ-95", "АИ-98", "АИ-100"]
    for i, f in enumerate(ladder):
        p = fuels[f]["price"]
        if p is None:
            continue
        for hf in ladder[i + 1:]:
            hp = fuels[hf]["price"]
            if hp is not None and not fuels[hf]["low"] and p > hp + 0.10:
                fuels[f]["priceSuspect"] = True
                break
    for f in FUELS:
        fd = fuels[f]
        fd["priceReliable"] = not fd["low"] and not fd["priceSuspect"]
        a = fd["age"]
        # цену показываем ТОЛЬКО при доверии: есть медиана (fresh>=FRESH_MIN) + не старьё + не абсурд
        fd["priceTrusted"] = bool(fd["price"] is not None and (a is None or a <= 12) and not fd["priceSuspect"])

    payload = {
        "empty": False,
        "generatedMsk": status.get("last_run_msk"),
        "region": cfg.get("region_name", ""),
        "monitoringDays": analytics.monitoring_days(hist),
        "measurements": len(hist),
        "freshDays": cfg.get("fresh_days", 4),
        "fresh": {"pricesAgo": p_ago, "pricesOk": ps.get("ok"),
                  "gdAgo": g_ago, "gdOk": gs.get("ok")},
        "fuels": FUELS,
        "defaultFuel": "АИ-95",
        # городская строка по массовым маркам: диапазон физ.подтверждено ↔ в прайсе+работает
        "cityAvail": (lambda m: _int(round(median(m))) if m else None)(
            [fuels[x]["availShare"] for x in ("АИ-92", "АИ-95", "ДТ") if fuels[x]["availShare"] is not None]),
        "cityPhys": (lambda m: _int(round(median(m))) if m else None)(
            [fuels[x]["physShare"] for x in ("АИ-92", "АИ-95", "ДТ") if fuels[x]["physShare"] is not None]),
        "gdResp": _int(gd_resp),
        "monDays": mon_days,
        "byFuel": fuels,
        "overall": {
            "workPp": cur("work_pp"), "workPp_d1": analytics.daily_delta(drows, "work_pp", 1),
            "workPp_d7": analytics.daily_delta(drows, "work_pp", 7),
            "gdBal": cur("gd_bal"), "gdBal_d7": analytics.daily_delta(drows, "gd_bal", 7),
            "azsTotal": _int(tot), "azsAvailable": _int(cur("azs_available")),
            "gbYes": _int(cur("gb_yes")), "gbNo": _int(cur("gb_no")),
            "gbQueue": _int(cur("gb_queue")), "gbLow": _int(cur("gb_low")),
        },
        "days": dlabels,
        "series": {
            "workPp": col("work_pp"), "gdBal": col("gd_bal"),
            "status": {"yes": col("gb_yes"), "no": col("gb_no"),
                       "queue": col("gb_queue"), "low": col("gb_low")},
        },
        "hourAvail": _round_list(analytics.by_hour(hist, "azs_available")[0]),
        "weekdayAvail": _round_list(analytics.by_weekday(drows, "azs_available")),
        "weekdays": analytics.WEEKDAYS,
        # «Когда заправляться»: профиль + автопроверка, можно ли ему верить (см. _when_profile)
        "whenHour": _when_profile(hist, "hour"),
        "whenDay": _when_profile(hist, "wd"),
        "bestHour": None,
        "bestDay": _best_wd(analytics.by_weekday(drows, "azs_available")),
        "weekdaySpread": _weekday_spread(drows),   # насколько вообще различаются дни

        "alerts": _alerts_list(hist, cfg),
        "brandsPrice": _brands_price(price_stations, tot),
        "brandsGd": _brands_gd(gd_stations),
        "geo": _focus_split(gd_stations, region.get("focus")),
        "focusName": (region.get("focus") or {}).get("name"),
        "focusOther": (region.get("focus") or {}).get("other_name"),
        "focusStations": _focus_stations(gd_stations, price_stations, cfg),
        # свежесть наблюдений (новое: у крауд-цен есть время — раньше времени не было вовсе)
        "seenFresh": _int(cur("gb_seen_fresh")), "seenAny": _int(cur("gb_seen_any")),
        "gbTotal": _int(gb_total),
    }
    return payload


def write(base_dir, snapshots=None, price_stations=None, gd_stations=None):
    """snapshots: {slug: (price_stations, gd_stations)} — снимки из текущего прогона.
    price_stations/gd_stations — легаси-путь (один регион msk)."""
    with open(os.path.join(base_dir, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    status = store.load_json(store.STATUS) or {}
    regions = cfg.get("regions") or [{"slug": "msk", "name": cfg.get("region_name", "")}]
    if snapshots is None:
        snapshots = {"msk": (price_stations, gd_stations)}

    out = {"regions": [], "defaultRegion": regions[0]["slug"]}
    for reg in regions:
        ps, gd = snapshots.get(reg["slug"], (None, None))
        p = build_payload(base_dir, ps, gd, region=reg, cfg=cfg, status=status)
        p["slug"] = reg["slug"]
        p["name"] = reg.get("name", "")
        p["short"] = reg.get("short") or reg.get("name", "")
        out["regions"].append(p)
    # легаси-совместимость: поля первого региона на верхнем уровне
    first = out["regions"][0]
    if not first.get("empty"):
        out.update({k: v for k, v in first.items() if k not in ("slug", "name", "short")})
    out["empty"] = all(r.get("empty") for r in out["regions"])

    out_dir = os.path.join(base_dir, "web", "public")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "data.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    return os.path.join(out_dir, "data.json")


# ------------------------------------------------------------- helpers ---
def _int(v):
    return int(v) if v is not None else None


def _pct(part, whole):
    return round(100 * part / whole) if (part is not None and whole) else None


def _round_list(vals):
    return [round(v, 1) if v is not None else None for v in vals]


def _best(vals, minpts):
    have = [i for i, v in enumerate(vals) if v is not None]
    return max(have, key=lambda i: vals[i]) if len(have) >= minpts else None


def _fuel_chance(r):
    """Шанс застать топливо на станции = (есть+очередь+мало)/ответившие, %.
    Нормировано на ответивших → не зависит от суточной активности краудсорса."""
    y = analytics._val(r, "gb_yes"); n = analytics._val(r, "gb_no")
    q = analytics._val(r, "gb_queue"); l = analytics._val(r, "gb_low")
    if None in (y, n, q, l):
        return None
    resp = y + n + q + l
    return 100 * (y + q + l) / resp if resp >= 100 else None


def _when_profile(hist, key):
    """Профиль «когда лучше заправляться» + ЧЕСТНАЯ проверка, можно ли ему верить.

    Считаем профиль отдельно по первой и второй половине истории и смотрим, повторяется ли он
    (корреляция). На 41 дне часы дали r=0.08, дни недели r=-0.27 — то есть «лучший час» гулял
    (июль 12ч, август 09ч). Поэтому советуем время ТОЛЬКО при r>=0.5 и размахе больше шума,
    иначе честно пишем «разницы нет». Когда данных станет больше (или начнётся острый дефицит
    с очередями), проверка сама разрешит совет."""
    from collections import defaultdict
    rows = [r for r in hist if analytics.parse_ts(r)]
    if len(rows) < 40:
        return None

    def keyof(r):
        t = analytics.parse_ts(r)
        return t.hour if key == "hour" else t.weekday()

    def prof(rs, minn):
        d = defaultdict(list)
        for r in rs:
            v = _fuel_chance(r)
            if v is not None:
                d[keyof(r)].append(v)
        return {k: median(x) for k, x in d.items() if len(x) >= minn}, d

    full, raw = prof(rows, 5)
    if len(full) < 5:
        return None
    half = len(rows) // 2
    pa, _ = prof(rows[:half], 3)
    pb, _ = prof(rows[half:], 3)
    ks = sorted(set(pa) & set(pb))
    rel = None
    if len(ks) >= 5:
        xs = [pa[k] for k in ks]; ys = [pb[k] for k in ks]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den = ((sum((x - mx) ** 2 for x in xs)) * (sum((y - my) ** 2 for y in ys))) ** 0.5
        rel = round(num / den, 2) if den else None

    noise = median([statistics_pstdev(x) for x in raw.values() if len(x) >= 5]) or 0
    best = max(full, key=full.get); worst = min(full, key=full.get)
    spread = full[best] - full[worst]
    trust = bool(rel is not None and rel >= 0.5 and spread > 1.5 * noise)
    return {
        "labels": [f"{k:02d}" for k in sorted(full)] if key == "hour"
                  else [analytics.WEEKDAYS[k] for k in sorted(full)],
        "values": [round(full[k], 1) for k in sorted(full)],
        "best": (f"{best:02d}:00" if key == "hour" else analytics.WEEKDAYS[best]),
        "worst": (f"{worst:02d}:00" if key == "hour" else analytics.WEEKDAYS[worst]),
        "spread": round(spread, 1), "noise": round(noise, 1),
        "reliability": rel, "trust": trust,
    }


def statistics_pstdev(x):
    import statistics as _s
    return _s.pstdev(x) if len(x) > 1 else 0.0


def _weekday_spread(drows):
    """Размах доступности по дням недели, п.п. Меньше ~3 — разница в пределах шума."""
    vals = [v for v in analytics.by_weekday(drows, "azs_available") if v is not None]
    if len(vals) < 5:
        return None
    tot = [analytics._val(r, "azs_total") for r in drows]
    base = median([t for t in tot if t]) if any(tot) else None
    if not base:
        return None
    return round(100 * (max(vals) - min(vals)) / base, 1)


def _best_wd(vals):
    have = [i for i, v in enumerate(vals) if v is not None]
    return analytics.WEEKDAYS[max(have, key=lambda i: vals[i])] if len(have) >= 3 else None


def _alerts_list(hist, cfg):
    al = cfg.get("alerts", {})
    out = []
    yes = analytics._val(hist[-1], "gb_yes")
    ymin = al.get("avail_yes_min")
    # порог задан для московского масштаба (~1250 АЗС) — масштабируем под размер региона,
    # иначе в Тверской (292 станции) он срабатывает всегда и врёт
    gbt = analytics._val(hist[-1], "gb_total")
    if ymin is not None and gbt:
        ymin = ymin * gbt / 1250.0
    if yes is not None and ymin is not None and yes < ymin:
        out.append(f"Мало сообщений «есть»: {int(yes)} (порог {int(ymin)}) — возможен дефицит.")
    thr = al.get("price_day_rise_pct")
    d = analytics.delta(hist, "p_med_АИ-95", 24)
    base = analytics.value_at_ago(hist, "p_med_АИ-95", 24)
    if d is not None and base and thr is not None and 100 * d / base >= thr:
        out.append(f"АИ-95 подорожал на {100*d/base:.1f}% за сутки.")
    return out


def _classify(brand_canon):
    """petrol | gas | none — газовые АЗС и нераспознанные вынести из бензиновых сетей."""
    if brand_canon == "Без бренда":
        return "none"
    if "(газ)" in brand_canon:
        return "gas"
    return "petrol"


def _brands_price(stations, tot):
    """Медианы цен по бензиновым сетям. Газовые АЗС исключены (их цены — не бензин).
    «Без бренда» показываем отдельной приглушённой строкой."""
    if not stations:
        return []
    agg = {}
    for s in stations:
        b = bd._norm_brand(s.get("brand"))
        if _classify(b) == "gas":
            continue  # газовые в бензиновую таблицу цен не мешаем
        a = agg.setdefault(b, {"n": 0, "p": {f: [] for f in FUELS}})
        a["n"] += 1
        for f in FUELS:
            v = (s.get("prices") or {}).get(f)
            if v is not None:
                a["p"][f].append(v)
    rows = [{"brand": b, "n": a["n"], "kind": _classify(b),
             "prices": {f: (round(median(a["p"][f]), 2) if a["p"][f] else None) for f in FUELS}}
            for b, a in agg.items()]
    # бензиновые сети по величине парка, «Без бренда» — в конец
    petrol = sorted([r for r in rows if r["kind"] == "petrol"], key=lambda r: -r["n"])[:12]
    none = sorted([r for r in rows if r["kind"] == "none"], key=lambda r: -r["n"])
    return petrol + none


def _focus_split(stations, focus, grade=None):
    """Срез «фокус региона ↔ остальное» по координатам gdebenz.
    Для Москвы фокус = внутри МКАД, для Тверской = Конаковский район.
    Если задан grade — считаем не «станция отпускает», а «на станции есть ЭТА марка»."""
    if not stations or not focus:
        return None
    acc = {"in": {"resp": 0, "yes": 0}, "out": {"resp": 0, "yes": 0}}
    for s in stations:
        stt = s.get("status")
        if stt not in ("yes", "no", "queue", "low"):
            continue
        if grade is not None:
            fs = {x.strip() for x in (s.get("fuels_now") or "").split(",") if x.strip()}
            has_fuel = grade in fs          # именно ЭТА марка отмечена на станции
        else:
            has_fuel = stt in ("yes", "queue", "low")   # станция отпускает хоть что-то
        inf = s.get("focus")
        if inf is None:
            inf = geo.in_focus(s.get("lat"), s.get("lon"), focus)
        if inf is None:
            continue
        side = "in" if inf else "out"
        acc[side]["resp"] += 1
        if has_fuel:
            acc[side]["yes"] += 1

    def pack(d):
        return {"resp": d["resp"], "yes": d["yes"],
                "pct": round(100 * d["yes"] / d["resp"]) if d["resp"] else None}
    return {"in": pack(acc["in"]), "out": pack(acc["out"])}


def _focus_stations(gd_stations, price_stations, cfg, limit=14):
    """Поимённый список АЗС фокуса. В маленьком районе (Конаковский: ~20 точек)
    поимённо полезнее любых процентов — видно, куда конкретно ехать."""
    if not gd_stations:
        return []
    grades = [G[f] for f in FUELS]
    STW = {"yes": "есть", "queue": "очередь", "low": "мало", "no": "нет"}
    out = []
    for s in gd_stations:
        if not s.get("focus"):
            continue
        fs = {x.strip() for x in (s.get("fuels_now") or "").split(",") if x.strip()}
        out.append({
            "brand": bd._norm_brand(s.get("brand")),
            "addr": (s.get("addr") or "").strip(),
            "status": s.get("status"),
            "statusText": STW.get(s.get("status")),
            "fuels": [g for g in grades if g in fs],
            "seenH": s.get("seen_h"),
        })
    # свежесть: наблюдение старше STALE_H — не «сейчас», уводим вниз и помечаем
    STALE_H = cfg.get("crowd_fresh_hours", 48)
    for x in out:
        x["stale"] = bool(x["seenH"] is None or x["seenH"] > STALE_H)
    rank = {"yes": 0, "queue": 1, "low": 2, "no": 3, None: 4}
    out.sort(key=lambda x: (x["stale"], rank.get(x["status"], 4), -(len(x["fuels"])), x["brand"]))
    return out[:limit]


def _brands_gd(stations):
    """Наличие по сетям (gdebenz). «Есть %» = (есть+очередь+лимит)/(ответившие),
    неизвестные НЕ в знаменателе. Показываем сколько ответили из скольких точек.
    Газовые и «Без бренда» — отдельными приглушёнными строками."""
    if not stations:
        return []
    grades = [G[f] for f in FUELS]
    yesish = {"yes", "queue", "low"}
    resp_set = {"yes", "no", "queue", "low"}

    def newrec():
        return {"n": 0, "resp": 0, "yes": 0, **{g: 0 for g in grades}}

    agg = {}
    for s in stations:
        b = bd._norm_brand(s.get("brand"))
        a = agg.setdefault(b, newrec())
        a["n"] += 1
        stt = s.get("status")
        if stt in resp_set:
            a["resp"] += 1
        if stt in yesish:
            a["yes"] += 1  # «есть» (в т.ч. с трудом)
        fs = {x.strip() for x in (s.get("fuels_now") or "").split(",") if x.strip()}
        for g in grades:
            if g in fs:
                a[g] += 1

    def mkrow(b, a):
        return {"brand": b, "n": a["n"], "resp": a["resp"], "yes": a["yes"],
                "kind": _classify(b),
                "availPct": round(100 * a["yes"] / a["resp"]) if a["resp"] else None,
                "byFuel": {G[f]: a[G[f]] for f in FUELS}}

    rows = [mkrow(b, a) for b, a in agg.items()]
    petrol = sorted([r for r in rows if r["kind"] == "petrol"], key=lambda r: -r["n"])[:12]
    # газовые и «без бренда» — сводим каждую в одну строку, чтобы не засоряли рейтинг
    def consolidate(kind, label):
        grp = [a for b, a in agg.items() if _classify(b) == kind]
        if not grp:
            return None
        tot = newrec()
        for a in grp:
            tot["n"] += a["n"]; tot["resp"] += a["resp"]; tot["yes"] += a["yes"]
            for g in grades:
                tot[g] += a[g]
        row = mkrow(label, tot)
        row["kind"] = kind  # метка «Газовые…» не содержит «(газ)» — задаём явно
        return row
    tail = [r for r in (consolidate("gas", f"Газовые (АГЗС · {sum(1 for b in agg if _classify(b)=='gas')})"),
                        consolidate("none", "Без бренда")) if r]
    return petrol + tail


if __name__ == "__main__":
    print("data.json:", write(BASE))
