"""Google News RSS collector.

Google News has no official API; its search RSS feed returns up to ~100 items
per query. We query several country/language "editions" (Google ranks and
filters differently per edition), and if a query looks capped we re-run it
in date slices using the `after:` / `before:` operators.

Note: the feed's terms restrict it to personal, non-commercial use. We use it
for academic research only and do not redistribute the raw feed.

Output (data/raw/google_news/articles_*.jsonl): one row per (edition, item)
with title, Google redirect link, publisher name + homepage, publish time.
"""

from __future__ import annotations

import time
from datetime import timedelta
from urllib.parse import urlencode

import feedparser
from tqdm import tqdm

from ..common import get_with_retry, load_config, log, raw_path, session, write_jsonl

FEED = "https://news.google.com/rss/search"
PAUSE = 1.5
CAPPED = 90  # treat >= this many results as "probably truncated"


def _fetch(s, q: str, country: str, lang: str) -> list[dict]:
    params = {"q": q, "hl": lang, "gl": country, "ceid": f"{country}:{lang}"}
    r = get_with_retry(s, f"{FEED}?{urlencode(params)}")
    time.sleep(PAUSE)
    feed = feedparser.parse(r.content)
    items = []
    for e in feed.entries:
        src = e.get("source", {})
        items.append(
            {
                "title": e.get("title"),
                "link": e.get("link"),
                "guid": e.get("id"),
                "published": e.get("published"),
                "source_name": src.get("title"),
                "source_url": src.get("href"),
                "edition": f"{country}:{lang}",
                "query": q,
            }
        )
    return items


def collect() -> None:
    cfg = load_config()
    gcfg = cfg["google_news"]
    start, end = cfg["study_window"]["start"], cfg["study_window"]["end"]
    s = session()
    rows: list[dict] = []

    jobs = [(q, c, l) for q in gcfg["queries"] for c, l in gcfg["editions"]]
    for q, country, lang in tqdm(jobs, desc="Google News"):
        window_q = f"{q} after:{start} before:{end + timedelta(days=1)}"
        items = _fetch(s, window_q, country, lang)
        if len(items) >= CAPPED:
            log.info("  %s %s:%s capped (%d); slicing by date", q, country, lang, len(items))
            items = []
            d = start
            while d <= end:
                d2 = d + timedelta(days=gcfg["slice_days"])
                items += _fetch(s, f"{q} after:{d} before:{d2}", country, lang)
                d = d2
        for it in items:
            it["base_query"] = q
        rows += items

    n = write_jsonl(rows, raw_path("google_news", "articles"))
    log.info("Google News: %d rows (before dedup)", n)
