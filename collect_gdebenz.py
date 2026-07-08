# -*- coding: utf-8 -*-
"""
Сбор НАЛИЧИЯ бензина с «ГдеБЕНЗ» (gdebenz.ru) — краудсорсный трекер.
По каждой АЗС: есть ли сейчас топливо (status: yes/no/queue/low) и какие марки
доступны (fuels_now). Считаем распределение статусов и число АЗС, где сейчас
есть каждая марка.

Экспортирует collect_availability(cfg) -> (summary, stations).
"""

import time
import requests

HOME = "https://www.gdebenz.ru/"
API = "https://www.gdebenz.ru/api/stations"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://www.gdebenz.ru/moskva",
    "Accept": "application/json",
}


def fetch_stations(cfg):
    bb = cfg["bbox"]
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


def collect_availability(cfg):
    grades = cfg.get("gdebenz_grades", ["92", "95", "98", "100", "ДТ"])
    stations_raw = fetch_stations(cfg)

    summary = {"total": len(stations_raw), "n_yes": 0, "n_no": 0, "n_queue": 0,
               "n_low": 0, "n_unknown": 0, "now": {g: 0 for g in grades}}
    stations = []
    for st in stations_raw:
        status = st.get("status")
        key = {"yes": "n_yes", "no": "n_no", "queue": "n_queue", "low": "n_low"}.get(status, "n_unknown")
        summary[key] += 1
        fs = _fuels_set(st.get("fuels_now"))
        for g in grades:
            if g in fs:
                summary["now"][g] += 1
        stations.append({"brand": st.get("brand"), "addr": st.get("addr"),
                         "lat": st.get("lat"), "lon": st.get("lon"),
                         "status": status, "fuels_now": st.get("fuels_now")})
    return summary, stations


if __name__ == "__main__":
    import json
    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    s, st = collect_availability(cfg)
    print("total", s["total"], "yes", s["n_yes"], "no", s["n_no"],
          "queue", s["n_queue"], "now", s["now"])
