# -*- coding: utf-8 -*-
"""
Хранение данных в текстовом виде (мало места, удобно для git и GitHub Pages):
  data/history.csv   — одна строка на прогон, все метрики (тренды). Дозаписывается.
  data/status.json   — статус/свежесть последнего прогона.
Снимки станций на диск НЕ сохраняются: run.py передаёт их в дашборд из памяти.
"""

import csv
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY = os.path.join(DATA_DIR, "history.csv")
STATUS = os.path.join(DATA_DIR, "status.json")


def _fieldnames(cfg):
    fn = ["ts_utc", "ts_msk", "azs_total", "azs_available"]
    for f in cfg.get("price_fuels", []):
        fn += [f"p_med_{f}", f"p_p10_{f}", f"p_p90_{f}", f"p_min_{f}",
               f"p_max_{f}", f"p_n_{f}", f"p_navail_{f}", f"p_fresh_{f}"]
    fn += ["gb_total", "gb_yes", "gb_no", "gb_queue", "gb_low", "gb_unknown"]
    for g in cfg.get("gdebenz_grades", []):
        fn += [f"gb_now_{g}"]
    for f in cfg.get("price_fuels", []):
        fn += [f"net_net_{f}", f"net_indep_{f}", f"net_spread_{f}"]
    fn += ["net95_med", "net95_n", "indep95_med", "indep95_n", "spread95"]
    for nw in cfg.get("tracked_networks", []):
        fn += [f"net95_{nw}"]
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
            row[f"p_fresh_{f}"] = d.get("n_fresh")
        net = price_summary.get("net") or {}
        pf = net.get("per_fuel", {})
        for f in cfg.get("price_fuels", []):
            d = pf.get(f, {})
            row[f"net_net_{f}"] = d.get("net")
            row[f"net_indep_{f}"] = d.get("indep")
            row[f"net_spread_{f}"] = d.get("spread")
        d95 = pf.get("АИ-95", {})
        row["net95_med"] = d95.get("net")
        row["net95_n"] = d95.get("n_net")
        row["indep95_med"] = d95.get("indep")
        row["indep95_n"] = d95.get("n_indep")
        row["spread95"] = d95.get("spread")
        for nw, med in (net.get("by95") or {}).items():
            row[f"net95_{nw}"] = med
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
    """Дозаписать строку. При изменении схемы (напр. добавили колонку) файл
    прозрачно мигрируется: новый заголовок = желаемые поля + существующие лишние
    (чтобы не терять старые данные), старые строки добиваются пустыми значениями."""
    os.makedirs(DATA_DIR, exist_ok=True)
    desired = _fieldnames(cfg)
    if os.path.exists(HISTORY):
        with open(HISTORY, encoding="utf-8", newline="") as f:
            existing = next(csv.reader(f), [])
        fields = desired + [c for c in existing if c not in desired]
        if fields != existing:                      # схема изменилась — мигрируем
            with open(HISTORY, encoding="utf-8", newline="") as f:
                old_rows = list(csv.DictReader(f))
            with open(HISTORY, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields, restval="")
                w.writeheader()
                for r in old_rows:
                    w.writerow({k: r.get(k, "") for k in fields})
    else:
        fields = desired
        with open(HISTORY, "w", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()
    with open(HISTORY, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", restval="")
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
