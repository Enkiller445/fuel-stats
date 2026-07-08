# -*- coding: utf-8 -*-
"""
Сбор ЦЕН на топливо с petrolplus / «АЗС-Локатор» (locator.transitcard.ru).

Скачивает ту же выгрузку StationList.xls, что кнопка «скачать» на сайте
(отдельно все точки и только с высокой доступностью), разбирает её и считает
метрики по каждому виду топлива (АИ-92/95/98/100/ДТ): медиана, коридор p10–p90,
число АЗС с ценой (всего и среди доступных).

Экспортирует collect_prices(cfg) -> (summary, stations). Без БД: хранение и
дашборд вынесены в store.py / build_dashboard.py, оркестрация — в run.py.
"""

import statistics
import time
import urllib.parse
import urllib.request

import xlrd

API = "https://locator.transitcard.ru/web/v1/report/points"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Referer": "https://locator.transitcard.ru/",
    "Accept": "application/vnd.ms-excel,*/*",
}


def fetch_report(cfg, available_only):
    bb = cfg["bbox"]
    params = {
        "pointTypes": cfg.get("point_types", "8;10"),
        "x1": bb["lat_min"], "x2": bb["lat_max"],
        "y1": bb["lon_min"], "y2": bb["lon_max"],
    }
    if available_only:
        params["fuelAvailability"] = "available"
    url = API + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(1, cfg.get("request_retries", 3) + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=cfg.get("request_timeout_sec", 120)) as r:
                data = r.read()
            if not data or data[:4] != b"\xd0\xcf\x11\xe0":
                raise ValueError(f"ответ не похож на .xls (первые байты: {data[:8]!r})")
            return data
        except Exception as e:
            last = e
            time.sleep(3 * attempt)
    raise RuntimeError(f"petrolplus: не удалось скачать выгрузку "
                       f"(available_only={available_only}): {last}")


def parse_report(xls_bytes):
    """XLS -> (rows, fuel_names). Заголовки в строке 1, данные с 3."""
    wb = xlrd.open_workbook(file_contents=xls_bytes)
    sh = wb.sheet_by_index(0)
    header = {sh.cell_value(1, c): c for c in range(sh.ncols)}
    col = {k: header.get(v) for k, v in {
        "region": "Регион", "city": "Город", "address": "Адрес",
        "brand": "Бренд", "type": "Тип ТО"}.items()}
    fuels = {}
    for name, c in header.items():
        if isinstance(name, str) and name.endswith(" цена"):
            fuels[name[:-len(" цена")].strip()] = {"price": c, "date": header.get(name[:-len(" цена")].strip() + " дата")}

    rows = []
    for r in range(3, sh.nrows):
        def cv(key):
            c = col[key]
            return str(sh.cell_value(r, c)).strip() if c is not None else ""
        rec = {"region": cv("region"), "city": cv("city"), "address": cv("address"),
               "brand": cv("brand"), "type": cv("type")}
        if not any([rec["region"], rec["city"], rec["address"], rec["brand"]]):
            continue
        for fuel, cc in fuels.items():
            rec[f"price_{fuel}"] = _to_price(sh.cell_value(r, cc["price"]))
            rec[f"date_{fuel}"] = (str(sh.cell_value(r, cc["date"])).strip()
                                   if cc["date"] is not None else "")
        rows.append(rec)
    return rows, list(fuels.keys())


def _to_price(v):
    if v is None or v == "":
        return None
    try:
        return round(float(str(v).replace(",", ".").replace("\xa0", "").strip()), 2)
    except Exception:
        return None


def station_key(rec):
    return "|".join([rec.get("brand", ""), rec.get("region", ""),
                     rec.get("city", ""), rec.get("address", "")]).lower()


def _pct(sv, q):
    if not sv:
        return None
    if len(sv) == 1:
        return sv[0]
    pos = q * (len(sv) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sv) - 1)
    return sv[lo] * (1 - (pos - lo)) + sv[hi] * (pos - lo)


def price_stats(values):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return dict(n=0, median=None, p10=None, p90=None, min=None, max=None, mean=None)
    return dict(
        n=len(vals),
        median=round(statistics.median(vals), 2),
        p10=round(_pct(vals, 0.10), 2),
        p90=round(_pct(vals, 0.90), 2),
        min=round(vals[0], 2),
        max=round(vals[-1], 2),
        mean=round(statistics.mean(vals), 2),
    )


def collect_prices(cfg):
    """
    Вернёт (summary, stations).
      summary: {azs_total, azs_available, fuels:{fuel:{median,p10,p90,min,max,n,n_avail}}}
      stations: список АЗС с ценами по всем видам + флаг available (для последнего снимка)
    """
    fuels = cfg.get("price_fuels", ["АИ-95", "АИ-98"])
    lo, hi = cfg.get("price_sane_min", 20.0), cfg.get("price_sane_max", 250.0)

    xls_all = fetch_report(cfg, available_only=False)
    xls_av = fetch_report(cfg, available_only=True)
    rows_all, _ = parse_report(xls_all)
    rows_av, _ = parse_report(xls_av)
    avail_keys = {station_key(r) for r in rows_av}
    for r in rows_all:
        r["_available"] = station_key(r) in avail_keys

    azs = [r for r in rows_all if r.get("type") == "АЗС"]
    azs_av = [r for r in azs if r["_available"]]

    def sane(rows, fuel):
        return [r.get(f"price_{fuel}") for r in rows
                if r.get(f"price_{fuel}") is not None and lo <= r.get(f"price_{fuel}") <= hi]

    summary = {
        "azs_total": len(azs),
        "azs_available": len(azs_av),
        "fuels": {},
    }
    for fuel in fuels:
        st = price_stats(sane(azs, fuel))
        st["n_avail"] = len(sane(azs_av, fuel))
        summary["fuels"][fuel] = st

    # последний снимок станций (компактно, для дашборда)
    stations = []
    for r in azs:
        rec = {"brand": r.get("brand"), "region": r.get("region"),
               "city": r.get("city"), "address": r.get("address"),
               "available": bool(r["_available"]), "prices": {}}
        for fuel in fuels:
            p = r.get(f"price_{fuel}")
            if p is not None and lo <= p <= hi:
                rec["prices"][fuel] = p
        stations.append(rec)
    return summary, stations


if __name__ == "__main__":
    import json
    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    s, st = collect_prices(cfg)
    print("azs_total", s["azs_total"], "azs_available", s["azs_available"])
    for fuel, d in s["fuels"].items():
        print(f"  {fuel}: median={d['median']} n={d['n']} navail={d['n_avail']}")
