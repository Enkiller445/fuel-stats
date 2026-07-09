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

    # --- по каждой марке ---
    fuels = {}
    for f in FUELS:
        g = G[f]
        n = cur(f"p_n_{f}")
        fresh = cur(f"p_fresh_{f}")
        navail = cur(f"p_navail_{f}")
        now = cur(f"gb_now_{g}")
        low = fresh is None or fresh < min_fresh
        diverge = bool(low and (now or 0) >= 40 and (now or 0) > 2 * (n or 1))
        s = bd._fuel_summary(f, hist, drows, cfg)
        fuels[f] = {
            "grade": g, "color": FUEL_HEX[f],
            "price": cur(f"p_med_{f}"),
            "price_d1": analytics.daily_delta(drows, f"p_med_{f}", 1),
            "price_d7": analytics.daily_delta(drows, f"p_med_{f}", 7),
            "n": _int(n), "fresh": _int(fresh), "navail": _int(navail), "now": _int(now),
            "share_all": _pct(n, tot), "work_pct": _pct(navail, n),
            "low": low, "diverge": diverge,
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


def _brands_price(stations, tot):
    if not stations:
        return []
    agg = {}
    for s in stations:
        a = agg.setdefault(bd._norm_brand(s.get("brand")), {"n": 0, "p": {f: [] for f in FUELS}})
        a["n"] += 1
        for f in FUELS:
            v = (s.get("prices") or {}).get(f)
            if v is not None:
                a["p"][f].append(v)
    out = []
    for b, a in sorted(agg.items(), key=lambda kv: -kv[1]["n"])[:15]:
        out.append({"brand": b, "n": a["n"],
                    "prices": {f: (round(median(a["p"][f]), 2) if a["p"][f] else None) for f in FUELS}})
    return out


def _brands_gd(stations):
    if not stations:
        return []
    grades = [G[f] for f in FUELS]
    agg = {}
    for s in stations:
        a = agg.setdefault(bd._norm_brand(s.get("brand")), {"n": 0, "yes": 0, **{g: 0 for g in grades}})
        a["n"] += 1
        a["yes"] += 1 if s.get("status") == "yes" else 0
        fs = {x.strip() for x in (s.get("fuels_now") or "").split(",") if x.strip()}
        for g in grades:
            if g in fs:
                a[g] += 1
    out = []
    for b, a in sorted(agg.items(), key=lambda kv: -kv[1]["n"])[:15]:
        out.append({"brand": b, "n": a["n"], "yes": a["yes"],
                    "byFuel": {G[f]: a[G[f]] for f in FUELS}})
    return out


if __name__ == "__main__":
    print("data.json:", write(BASE))
