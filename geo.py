# -*- coding: utf-8 -*-
"""
Гео-помощники для регионов: расстояние и «точка внутри полигона».

Зачем: у gdebenz есть только координаты (нет региона/города), поэтому границу
области задаём грубым полигоном (config.regions[].gd_polygon). У petrolplus,
наоборот, есть поле «Регион» — там фильтруем по нему (точнее полигона).
"""

import math


def km(lat1, lon1, lat2, lon2):
    """Расстояние по большому кругу, км."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(a)))


def in_polygon(lat, lon, poly):
    """Ray casting. poly — список [lat, lon]. Полигон грубый (граница области ±пара км)."""
    if not poly:
        return True
    inside = False
    n = len(poly)
    for i in range(n):
        y1, x1 = poly[i]
        y2, x2 = poly[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            xint = (x2 - x1) * (lat - y1) / ((y2 - y1) or 1e-12) + x1
            if lon < xint:
                inside = not inside
    return inside


def in_bbox(lat, lon, bb):
    return (bb["lat_min"] <= lat <= bb["lat_max"]) and (bb["lon_min"] <= lon <= bb["lon_max"])


def in_focus(lat, lon, focus):
    """Точка внутри «фокуса» региона (круг вокруг центра)."""
    if not focus or lat is None or lon is None:
        return None
    c = focus.get("center")
    r = focus.get("radius_km")
    if not c or not r:
        return None
    return km(c[0], c[1], lat, lon) <= r


def city_in_focus(city, address, focus):
    """Для petrolplus (координат нет) — попадание по названию города/адреса."""
    if not focus:
        return None
    cities = focus.get("cities")
    if not cities:
        return None
    hay = f"{city or ''} {address or ''}".lower()
    return any(c.lower() in hay for c in cities)
