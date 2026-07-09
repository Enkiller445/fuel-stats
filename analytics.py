# -*- coding: utf-8 -*-
"""
Аналитика над историей замеров (data/history.csv, теперь почасовой):
дневная выборка в фиксированный час, скользящее среднее, дельты 24ч/7д,
разрезы по дню недели и часу суток. Без внешних зависимостей.
"""

from datetime import datetime, timedelta

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def parse_ts(row):
    try:
        return datetime.strptime(row["ts_msk"], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def daily_sample(hist, hour):
    """По одному замеру на день — ближайший к hour:00 МСК. -> (dates, rows)."""
    best = {}
    for r in hist:
        dt = parse_ts(r)
        if not dt:
            continue
        day = dt.date()
        target = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
        diff = abs((dt - target).total_seconds())
        if day not in best or diff < best[day][0]:
            best[day] = (diff, r)
    days = sorted(best)
    return days, [best[d][1] for d in days]


def col(rows, name):
    out = []
    for r in rows:
        v = r.get(name)
        try:
            out.append(float(v) if v not in (None, "") else None)
        except (TypeError, ValueError):
            out.append(None)
    return out


def moving_avg(vals, window=3):
    """Трейлинг-среднее по последним `window` непустым значениям."""
    out = []
    for i in range(len(vals)):
        seg = [v for v in vals[max(0, i - window + 1): i + 1] if v is not None]
        out.append(round(sum(seg) / len(seg), 2) if seg else None)
    return out


def _val(row, name):
    v = row.get(name)
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def value_at_ago(hist, name, hours, tol_hours=None):
    """Значение метрики примерно `hours` назад (ближайший замер в пределах tol)."""
    if not hist:
        return None
    last_dt = parse_ts(hist[-1])
    if not last_dt:
        return None
    target = last_dt - timedelta(hours=hours)
    tol = timedelta(hours=tol_hours if tol_hours is not None else max(2, hours * 0.15))
    best = None
    for r in hist:
        dt = parse_ts(r)
        if not dt:
            continue
        d = abs((dt - target).total_seconds())
        if d <= tol.total_seconds() and (best is None or d < best[0]):
            v = _val(r, name)
            if v is not None:
                best = (d, v)
    return best[1] if best else None


def delta(hist, name, hours):
    """(текущее - значение hours назад). None если не с чем сравнить."""
    if not hist:
        return None
    curv = _val(hist[-1], name)
    prev = value_at_ago(hist, name, hours)
    if curv is None or prev is None:
        return None
    return round(curv - prev, 2)


def daily_delta(daily_rows, name, days_back):
    """Дельта строго по ДНЕВНОЙ выборке (тот же час к тому же часу N дней назад),
    а не «ближайший замер» — чтобы не поймать суточный профиль вместо тренда."""
    vals = col(daily_rows, name)
    idx = [i for i, v in enumerate(vals) if v is not None]
    if len(idx) < 2:
        return None
    last = idx[-1]
    prev = [i for i in idx if i <= last - days_back]
    if not prev:
        return None
    return round(vals[last] - vals[prev[-1]], 2)


def by_weekday(daily_rows, name):
    """Среднее значение метрики по дням недели (из дневной выборки)."""
    acc = {i: [] for i in range(7)}
    for r in daily_rows:
        dt = parse_ts(r)
        v = _val(r, name)
        if dt and v is not None:
            acc[dt.weekday()].append(v)
    return [round(sum(acc[i]) / len(acc[i]), 1) if acc[i] else None for i in range(7)]


def by_hour(hist, name):
    """Среднее метрики по часу суток (0..23). -> (avg[24], n[24])."""
    acc = {h: [] for h in range(24)}
    for r in hist:
        dt = parse_ts(r)
        v = _val(r, name)
        if dt and v is not None:
            acc[dt.hour].append(v)
    avg = [round(sum(acc[h]) / len(acc[h]), 1) if acc[h] else None for h in range(24)]
    n = [len(acc[h]) for h in range(24)]
    return avg, n


def monitoring_days(hist):
    if not hist:
        return 0
    a, b = parse_ts(hist[0]), parse_ts(hist[-1])
    if not a or not b:
        return 0
    return (b.date() - a.date()).days + 1


def col_min_max(hist, name):
    vals = [v for v in col(hist, name) if v is not None]
    return (min(vals), max(vals)) if vals else (None, None)
