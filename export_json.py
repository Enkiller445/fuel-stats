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

BASE = os.path.dirname(os.path.abspath(__file__))
FUELS = bd.FUELS
G = bd.FUEL_TO_GRADE
FUEL_HEX = {"АИ-92": "f92", "АИ-95": "f95", "АИ-98": "f98", "АИ-100": "f100", "ДТ": "fdt"}


def _lv(hist, c):
    return analytics._val(hist[-1], c) if hist else None


def build_payload(base_dir, price_stations=None, gd_stations=None):
    with open(os.path.join(base_dir, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    hist = store.load_history()
    status = store.load_json(store.STATUS) or {}
    if not hist:
        return {"empty": True}

    # доп. показатели в строки (как в build_dashboard)
    for r in hist:
        pp, gd = bd._av_pcts(r)
        r["work_pp"], r["gd_bal"] = pp, gd
        # availShare по каждой марке (для честного тренда: navail / полная база)
        tot_r = analytics._val(r, "azs_total")
        for f in FUELS:
            nv = analytics._val(r, f"p_navail_{f}")
            r[f"avs_{f}"] = round(100 * nv / tot_r, 1) if (nv is not None and tot_r) else None

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
    gd_resp = sum(x for x in (cur("gb_yes"), cur("gb_no"), cur("gb_queue"), cur("gb_low"))
                  if x is not None) or None
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

        # честная доступность = navail / полная база (не среди продающих)
        avail_share = _int(_clamp(round(100 * navail / tot), 0, 100)) if (navail is not None and tot) else None
        r = round(now / navail, 2) if (now is not None and navail) else None
        # r, нормированный на покрытие gdebenz (= gd_share/availShare) — устойчив к размеру выборки
        r_norm = round(r / gd_cover, 2) if (r is not None and gd_cover) else None
        gd_share = _int(round(100 * now / gd_resp)) if (now is not None and gd_resp) else None
        pp_healthy = (fresh is not None and fresh >= min_fresh) and (age is None or age <= 12)
        blinded = bool(r is not None and r > 3 and not pp_healthy)  # petrolplus ослеп по марке
        # уверенность в НАЛИЧИИ (не в цене): выборка, ослепление, крошечный n
        avail_conf = "low" if ((navail is None) or (n is None) or (n < 8) or blinded) else "high"

        # уровень-светофор: кандидат по availShare -> шортедж-пул r<0.4 -> кап conf/age
        if n is None or n == 0 or avail_share is None or (now is None and navail is None):
            level = "gray"
        else:
            level = "green" if avail_share >= 50 else ("yellow" if avail_share >= 20 else "red")
            if level == "green" and r_norm is not None and r_norm < 0.4:
                level = "yellow"                      # умеренный дефицит массовой марки (по нормированному r)
            if level == "green" and (avail_conf == "low" or (age is not None and age > 12)):
                level = "yellow"                      # зелёный запрещён при LOW / старье

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

        s = bd._fuel_summary(f, hist, drows, cfg)
        fuels[f] = {
            "grade": g, "color": FUEL_HEX[f],
            "price": cur(f"p_med_{f}"),
            "price_d1": analytics.daily_delta(drows, f"p_med_{f}", 1),
            "price_d7": analytics.daily_delta(drows, f"p_med_{f}", 7),
            "n": _int(n), "fresh": _int(fresh), "navail": _int(navail), "now": _int(now),
            "age": age,
            # --- trust-first поля (ведущие) ---
            "availShare": avail_share, "r": r, "rNorm": r_norm, "gdShare": gd_share, "blinded": blinded,
            "availConf": avail_conf, "level": level,
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
            },
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
        # честная городская строка: медиана availShare массовых марок (не workPp — тот про открытые АЗС)
        "cityAvail": (lambda m: _int(round(median(m))) if m else None)(
            [fuels[x]["availShare"] for x in ("АИ-92", "АИ-95", "ДТ") if fuels[x]["availShare"] is not None]),
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
        "bestHour": _best(analytics.by_hour(hist, "azs_available")[0], 6),
        "bestDay": _best_wd(analytics.by_weekday(drows, "azs_available")),
        "alerts": _alerts_list(hist, cfg),
        "brandsPrice": _brands_price(price_stations, tot),
        "brandsGd": _brands_gd(gd_stations),
        "geo": _geo(gd_stations),
    }
    return payload


def write(base_dir, price_stations=None, gd_stations=None):
    payload = build_payload(base_dir, price_stations, gd_stations)
    out_dir = os.path.join(base_dir, "web", "public")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "data.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
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


def _best_wd(vals):
    have = [i for i, v in enumerate(vals) if v is not None]
    return analytics.WEEKDAYS[max(have, key=lambda i: vals[i])] if len(have) >= 3 else None


def _alerts_list(hist, cfg):
    al = cfg.get("alerts", {})
    out = []
    yes = analytics._val(hist[-1], "gb_yes")
    ymin = al.get("avail_yes_min")
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


def _geo(stations):
    """Срез наличия Москва↔область по координатам gdebenz: внутри МКАД vs за МКАД.
    Порог — расстояние от центра Москвы (грубый прокси «город/область»)."""
    if not stations:
        return None
    import math
    clat, clon, R = 55.7558, 37.6173, 19.0  # км, ≈радиус МКАД
    acc = {"in": {"resp": 0, "yes": 0}, "out": {"resp": 0, "yes": 0}}
    for s in stations:
        lat, lon, stt = s.get("lat"), s.get("lon"), s.get("status")
        if lat is None or lon is None or stt not in ("yes", "no", "queue", "low"):
            continue
        dlat = math.radians(lat - clat)
        dlon = math.radians(lon - clon)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(clat)) * math.cos(math.radians(lat)) * math.sin(dlon / 2) ** 2)
        km = 2 * 6371 * math.asin(min(1, math.sqrt(a)))
        side = "in" if km <= R else "out"
        acc[side]["resp"] += 1
        if stt in ("yes", "queue", "low"):  # «есть» (в т.ч. с трудом)
            acc[side]["yes"] += 1
    def pack(d):
        return {"resp": d["resp"], "yes": d["yes"],
                "pct": round(100 * d["yes"] / d["resp"]) if d["resp"] else None}
    return {"in": pack(acc["in"]), "out": pack(acc["out"])}


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
