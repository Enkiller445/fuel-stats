# -*- coding: utf-8 -*-
"""
Автосборщик событий из Google News RSS (по топливным запросам).
Каждое событие — с датой, заголовком, названием источника и ссылкой (для проверки).
Пишет data/events_auto.json. Это ПОДБОРКА новостей: помечается отдельно от ручных
событий (events.json) и требует проверки по источнику — не факт-чекнутая истина.
"""

import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

GNEWS = "https://news.google.com/rss/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 Chrome/125.0 Safari/537.36"}
KEYWORDS = ("бензин", "топлив", "дизел", "нпз", "азс", "заправк", "лимит", "дефицит", "октан")
DEFAULT_QUERIES = ["дефицит бензина", "лимит на бензин АЗС", "цены на бензин Москва", "НПЗ"]


def _clean_title(t, source):
    t = re.sub(r"\s+", " ", t or "").strip()
    if source and t.endswith(source):
        t = t[: -len(source)].rstrip(" -–—").strip()
    return t


def fetch_events(cfg, days_back=45, cap=18):
    queries = cfg.get("event_queries", DEFAULT_QUERIES)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    items = {}
    for q in queries:
        url = GNEWS + "?" + urllib.parse.urlencode(
            {"q": f"{q} when:{days_back}d", "hl": "ru", "gl": "RU", "ceid": "RU:ru"})
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=cfg.get("request_timeout_sec", 120)) as r:
                root = ET.fromstring(r.read())
        except Exception:
            continue
        for it in root.iter("item"):
            title = it.findtext("title") or ""
            link = it.findtext("link") or ""
            pub = it.findtext("pubDate") or ""
            source = ""
            for ch in it:
                if ch.tag.endswith("source"):
                    source = (ch.text or "").strip()
            try:
                dt = parsedate_to_datetime(pub)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if dt < cutoff:
                continue
            title = _clean_title(title, source)
            low = title.lower()
            if not any(k in low for k in KEYWORDS):
                continue
            key = low[:70]
            if key not in items:
                items[key] = {"date": dt.date().isoformat(), "title": title,
                              "url": link, "source": source, "auto": True}
    return sorted(items.values(), key=lambda e: e["date"], reverse=True)[:cap]


def collect_to_file(cfg, path):
    ev = fetch_events(cfg)
    if ev:  # не затираем прошлую подборку пустым результатом (сеть/сбой)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ev, f, ensure_ascii=False, indent=0)
    return ev


if __name__ == "__main__":
    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    ev = fetch_events(cfg)
    print(f"{len(ev)} событий:")
    for e in ev[:12]:
        print(f"  {e['date']} [{e['source']}] {e['title'][:80]}")
