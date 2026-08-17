# -*- coding: utf-8 -*-
"""
Сбор НАЛИЧИЯ бензина с «ГдеБЕНЗ» (gdebenz.ru) — краудсорсный трекер.
По каждой АЗС: есть ли сейчас топливо (status: yes/no/queue/low) и какие марки
доступны (fuels_now). Считаем распределение статусов и число АЗС, где сейчас
есть каждая марка.

Экспортирует collect_availability(cfg) -> (summary, stations).
"""

import statistics
import time
from datetime import datetime, timezone, timedelta

import requests

import geo

MSK = timezone(timedelta(hours=3))

HOME = "https://www.gdebenz.ru/"
API = "https://www.gdebenz.ru/api/stations"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://www.gdebenz.ru/moskva",
    "Accept": "application/json",
}


def fetch_stations(cfg, bbox=None):
    bb = bbox or cfg["bbox"]
    params = {"lat1": bb["lat_min"], "lon1": bb["lon_min"],
              "lat2": bb["lat_max"], "lon2": bb["lon_max"]}
    last = None
    for attempt in range(1, cfg.get("request_retries", 3) + 1):
        try:
            s = requests.Session()
            s.headers.update(HEADERS)
            s.get(HOME, timeout=cfg.get("request_timeout_sec", 120))  # ddos-guard warmup
            r = s.get(API, params=params, timeout=cfg.get("request_timeout_sec", 120))
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, list):
                raise ValueError(f"ожидался список, получено {type(data)}")
            return data
        except Exception as e:
            last = e
            time.sleep(3 * attempt)
    raise RuntimeError(f"gdebenz: не удалось получить станции: {last}")


def _fuels_set(s):
    return {p.strip() for p in (s or "").split(",") if p.strip()}


def _price_age_hours(t, now_utc):
    """Возраст крауд-цены в часах. t — 'YYYY-MM-DD HH:MM:SS' (МСК)."""
    if not t:
        return None
    try:
        dt = datetime.strptime(str(t).strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=MSK)
    except Exception:
        return None
    return max(0.0, (now_utc - dt).total_seconds() / 3600.0)


def collect_availability(cfg, region=None):
    """Наличие + НОВОЕ: крауд-цены `prices_now` (у них есть время наблюдения и число
    подтверждений). region — элемент cfg["regions"]: bbox + gd_polygon + focus."""
    region = region or {}
    bbox = region.get("bbox") or cfg["bbox"]
    poly = region.get("gd_polygon")
    focus = region.get("focus")
    grades = cfg.get("gdebenz_grades", ["92", "95", "98", "100", "ДТ"])
    lo, hi = cfg.get("price_sane_min", 20.0), cfg.get("price_sane_max", 250.0)
    fresh_h = cfg.get("crowd_fresh_hours", 48)
    now_utc = datetime.now(timezone.utc)

    stations_raw = fetch_stations(cfg, bbox=bbox)
    # bbox шире области → отсекаем соседние регионы грубым полигоном
    if poly:
        stations_raw = [s for s in stations_raw
                        if s.get("lat") is not None and s.get("lon") is not None
                        and geo.in_polygon(s["lat"], s["lon"], poly)]

    summary = {"total": len(stations_raw), "n_yes": 0, "n_no": 0, "n_queue": 0,
               "n_low": 0, "n_unknown": 0, "now": {g: 0 for g in grades},
               # крауд-цены: медиана свежих + сколько АЗС их дали
               "cprice": {g: None for g in grades}, "cprice_n": {g: 0 for g in grades},
               # свежесть наблюдений (раньше у отметок вообще не было времени)
               "seen_fresh": 0, "seen_any": 0}
    cvals = {g: [] for g in grades}
    stations = []
    for st in stations_raw:
        status = st.get("status")
        key = {"yes": "n_yes", "no": "n_no", "queue": "n_queue", "low": "n_low"}.get(status, "n_unknown")
        summary[key] += 1
        fs = _fuels_set(st.get("fuels_now"))
        for g in grades:
            if g in fs:
                summary["now"][g] += 1

        # --- крауд-цены (новое поле prices_now) ---
        pn = st.get("prices_now") or {}
        age_min = None
        for g, v in pn.items():
            if g not in cvals or not isinstance(v, dict):
                continue
            p = v.get("p")
            age = _price_age_hours(v.get("t"), now_utc)
            if age is not None and (age_min is None or age < age_min):
                age_min = age
            # в медиану — только свежие и вменяемые
            if p is not None and lo <= p <= hi and age is not None and age <= fresh_h:
                cvals[g].append(float(p))
        if age_min is not None:
            summary["seen_any"] += 1
            if age_min <= fresh_h:
                summary["seen_fresh"] += 1

        stations.append({"brand": st.get("brand"), "addr": st.get("addr"),
                         "lat": st.get("lat"), "lon": st.get("lon"),
                         "status": status, "fuels_now": st.get("fuels_now"),
                         "focus": geo.in_focus(st.get("lat"), st.get("lon"), focus),
                         "seen_h": round(age_min, 1) if age_min is not None else None})

    for g in grades:
        if cvals[g]:
            summary["cprice"][g] = round(statistics.median(cvals[g]), 2)
            summary["cprice_n"][g] = len(cvals[g])
    return summary, stations


if __name__ == "__main__":
    import json
    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    s, st = collect_availability(cfg)
    print("total", s["total"], "yes", s["n_yes"], "no", s["n_no"],
          "queue", s["n_queue"], "now", s["now"])
