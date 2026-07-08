# -*- coding: utf-8 -*-
"""
Хранение данных в текстовом виде (удобно для git и GitHub Pages):
  data/history.csv          — одна строка на прогон, все метрики (тренды)
  data/latest_prices.json   — последний снимок АЗС с ценами (для таблиц)
  data/latest_gdebenz.json  — последний снимок наличия
  data/status.json          — статус последнего прогона (ошибки, свежесть)
"""

import csv
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY = os.path.join(DATA_DIR, "history.csv")
LATEST_PRICES = os.path.join(DATA_DIR, "latest_prices.json")
LATEST_GDEBENZ = os.path.join(DATA_DIR, "latest_gdebenz.json")
STATUS = os.path.join(DATA_DIR, "status.json")


def _fieldnames(cfg):
    fn = ["ts_utc", "ts_msk", "azs_total", "azs_available"]
    for f in cfg.get("price_fuels", []):
        fn += [f"p_med_{f}", f"p_p10_{f}", f"p_p90_{f}", f"p_min_{f}",
               f"p_max_{f}", f"p_n_{f}", f"p_navail_{f}"]
    fn += ["gb_total", "gb_yes", "gb_no", "gb_queue", "gb_low", "gb_unknown"]
    for g in cfg.get("gdebenz_grades", []):
        fn += [f"gb_now_{g}"]
    return fn


def build_row(cfg, ts_utc, ts_msk, price_summary, gd_summary):
    row = {"ts_utc": ts_utc, "ts_msk": ts_msk}
    if price_summary:
        row["azs_total"] = price_summary["azs_total"]
        row["azs_available"] = price_summary["azs_available"]
        for f in cfg.get("price_fuels", []):
            d = price_summary["fuels"].get(f, {})
            row[f"p_med_{f}"] = d.get("median")
            row[f"p_p10_{f}"] = d.get("p10")
            row[f"p_p90_{f}"] = d.get("p90")
            row[f"p_min_{f}"] = d.get("min")
            row[f"p_max_{f}"] = d.get("max")
            row[f"p_n_{f}"] = d.get("n")
            row[f"p_navail_{f}"] = d.get("n_avail")
    if gd_summary:
        row["gb_total"] = gd_summary["total"]
        row["gb_yes"] = gd_summary["n_yes"]
        row["gb_no"] = gd_summary["n_no"]
        row["gb_queue"] = gd_summary["n_queue"]
        row["gb_low"] = gd_summary["n_low"]
        row["gb_unknown"] = gd_summary["n_unknown"]
        for g in cfg.get("gdebenz_grades", []):
            row[f"gb_now_{g}"] = gd_summary["now"].get(g)
    return row


def append_history(cfg, row):
    os.makedirs(DATA_DIR, exist_ok=True)
    exists = os.path.exists(HISTORY)
    if exists:
        with open(HISTORY, encoding="utf-8", newline="") as f:
            fields = next(csv.reader(f))
    else:
        fields = _fieldnames(cfg)
    with open(HISTORY, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", restval="")
        if not exists:
            w.writeheader()
        w.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in fields})


def write_json(path, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def load_history():
    if not os.path.exists(HISTORY):
        return []
    out = []
    with open(HISTORY, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rec = {}
            for k, v in row.items():
                if k in ("ts_utc", "ts_msk"):
                    rec[k] = v
                elif v == "" or v is None:
                    rec[k] = None
                else:
                    try:
                        rec[k] = float(v)
                    except ValueError:
                        rec[k] = v
            out.append(rec)
    return out


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
