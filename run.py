# -*- coding: utf-8 -*-
"""
Оркестратор сбора: цены (petrolplus) + наличие (gdebenz) -> история/снимки -> дашборд.

Устойчив к сбою одного источника: если что-то недоступно (например, заблокировано
из зарубежного дата-центра), другой источник и дашборд всё равно обновятся, а на
странице появится пометка о свежести/ошибке.

Запуск (локально или в GitHub Actions):  python run.py
"""

import json
import os
import sys
import traceback
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    MSK = ZoneInfo("Europe/Moscow")
except Exception:
    MSK = None

import store
import collect
import collect_gdebenz
import build_dashboard

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def now_pair():
    n = datetime.now(timezone.utc)
    utc = n.strftime("%Y-%m-%d %H:%M:%S")
    msk = n.astimezone(MSK).strftime("%Y-%m-%d %H:%M:%S") if MSK else utc
    return utc, msk


def main():
    with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    ts_utc, ts_msk = now_pair()
    print(f"=== Прогон {ts_msk} МСК · {cfg.get('region_name')} ===")

    status = store.load_json(store.STATUS) or {}
    price_summary = gd_summary = None
    price_stations = gd_stations = None

    # 1) Цены
    try:
        price_summary, price_stations = collect.collect_prices(cfg)
        status["prices"] = {"ok": True, "ts_msk": ts_msk, "error": None,
                            "azs_total": price_summary["azs_total"],
                            "azs_available": price_summary["azs_available"]}
        print(f"  Цены: АЗС {price_summary['azs_total']} / доступных "
              f"{price_summary['azs_available']}; "
              + ", ".join(f"{f}={d['median']}" for f, d in price_summary['fuels'].items()))
    except Exception as e:
        status.setdefault("prices", {})
        status["prices"].update({"ok": False, "error": str(e)})
        print("  ЦЕНЫ: ОШИБКА:", e)
        traceback.print_exc()

    # 2) Наличие
    try:
        gd_summary, gd_stations = collect_gdebenz.collect_availability(cfg)
        status["gdebenz"] = {"ok": True, "ts_msk": ts_msk, "error": None,
                             "total": gd_summary["total"], "yes": gd_summary["n_yes"],
                             "no": gd_summary["n_no"]}
        print(f"  Наличие: станций {gd_summary['total']}, есть {gd_summary['n_yes']}, "
              f"нет {gd_summary['n_no']}, очередь {gd_summary['n_queue']}")
    except Exception as e:
        status.setdefault("gdebenz", {})
        status["gdebenz"].update({"ok": False, "error": str(e)})
        print("  НАЛИЧИЕ: ОШИБКА:", e)
        traceback.print_exc()

    # 2.5) Автоподборка событий из новостей (не критично)
    try:
        import collect_events
        ev = collect_events.collect_to_file(
            cfg, os.path.join(BASE_DIR, "data", "events_auto.json"))
        print(f"  События (автоподборка): {len(ev)}")
    except Exception as e:
        print("  СОБЫТИЯ: пропущено:", e)

    # 3) История (если хоть один источник ответил)
    if price_summary or gd_summary:
        row = store.build_row(cfg, ts_utc, ts_msk, price_summary, gd_summary)
        store.append_history(cfg, row)
        print("  История дописана.")
    else:
        print("  Оба источника недоступны — история не изменена.")

    status["last_run_msk"] = ts_msk
    status["region"] = cfg.get("region_name")
    store.write_json(store.STATUS, status)

    # 4) Дашборд (снимки станций передаём из памяти, на диск не сохраняем)
    out = build_dashboard.build(BASE_DIR, price_stations=price_stations,
                                gd_stations=gd_stations)
    print("  Дашборд собран:", out)

    # Ненулевой код выхода только если ОБА источника упали (для сигнала в CI)
    if not price_summary and not gd_summary:
        sys.exit(2)


if __name__ == "__main__":
    main()
