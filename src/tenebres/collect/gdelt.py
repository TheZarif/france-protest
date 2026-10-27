"""GDELT DOC 2.0 API collector.

Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/

GDELT monitors online news in 65+ languages and covers the last 3 months via
this API. Each request returns at most 250 articles, so we first pull a daily
volume timeline, then request articles day by day (and in 6-hour slices on
days that hit the cap).

GDELT throttles by IP, so every successful response is cached as soon as it
arrives (data/interim/gdelt_cache/, one JSON file per request). A run that is
cut short by HTTP 429s keeps what it got; re-running skips cached requests and
picks up where it stopped (see common.ResponseCache for how recent windows
are refreshed).

Outputs (data/raw/gdelt/), written only once every request has succeeded:
  articles_*.jsonl   one row per article (url, title, seendate, domain,
                     language, sourcecountry, query)
  timelines_*.jsonl  daily series: volume, tone, by-country, by-language
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from tqdm import tqdm

from ..common import (
    INTERIM, ResponseCache, get_with_retry, load_config, log, raw_path, session, write_jsonl,
)

API = "https://api.gdeltproject.org/api/v2/doc/doc"
PAUSE = 6  # GDELT asks for <= 1 request / 5 s
CAP = 250
CACHE = ResponseCache(INTERIM / "gdelt_cache")


class Incomplete(RuntimeError):
    """GDELT stopped answering before every request was made."""


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S")


def _call(s, **params) -> dict:
    params.setdefault("format", "json")
    window_end = datetime.strptime(params["enddatetime"], "%Y%m%d%H%M%S")
    if (hit := CACHE.get(params, window_end)) is not None:
        return hit
    try:
        r = get_with_retry(s, API, params=params, backoff=15)
    except RuntimeError as e:
        raise Incomplete(str(e)) from e
    time.sleep(PAUSE)
    text = r.text.strip()
    if not text.startswith("{"):
        # GDELT returns plain-text errors with HTTP 200 (e.g. bad query).
        log.warning("GDELT non-JSON reply for %s: %s", params.get("query"), text[:200])
        return {}
    data = r.json()
    CACHE.put(params, data)
    return data


def _timeline(s, query: str, mode: str, start: datetime, end: datetime) -> list[dict]:
    data = _call(s, query=query, mode=mode, startdatetime=_fmt(start), enddatetime=_fmt(end))
    rows = []
    for series in data.get("timeline", []):
        for point in series.get("data", []):
            rows.append(
                {
                    "query": query,
                    "mode": mode,
                    "series": series.get("series"),
                    "date": point["date"],
                    "value": point.get("value"),
                    "norm": point.get("norm"),
                }
            )
    return rows


def _articles(s, query: str, start: datetime, end: datetime) -> list[dict]:
    data = _call(
        s,
        query=query,
        mode="artlist",
        maxrecords=CAP,
        sort="dateasc",
        startdatetime=_fmt(start),
        enddatetime=_fmt(end),
    )
    return data.get("articles", [])


def collect() -> None:
    cfg = load_config()
    start = datetime.combine(cfg["study_window"]["start"], datetime.min.time())
    end = datetime.combine(cfg["study_window"]["end"], datetime.min.time()) + timedelta(days=1)
    s = session()
    n_cached = len(CACHE)
    if n_cached:
        log.info("GDELT: resuming with %d cached responses", n_cached)

    try:
        timelines, articles = _collect(s, cfg, start, end)
    except Incomplete as e:
        n_now = len(CACHE)
        log.error(
            "GDELT stopped responding (%s). %d responses cached (%d new this run); "
            "re-run `tenebres collect gdelt` to resume.",
            e, n_now, n_now - n_cached,
        )
        return

    n_t = write_jsonl(timelines, raw_path("gdelt", "timelines"))
    n_a = write_jsonl(articles.values(), raw_path("gdelt", "articles"))
    log.info("GDELT: %d timeline points, %d unique articles", n_t, n_a)


def _collect(s, cfg: dict, start: datetime, end: datetime) -> tuple[list[dict], dict[str, dict]]:
    timelines: list[dict] = []
    articles: dict[str, dict] = {}

    for query in cfg["gdelt"]["queries"]:
        log.info("GDELT query: %s", query)
        for mode in ("timelinevolraw", "timelinetone", "timelinesourcecountry", "timelinelang"):
            timelines += _timeline(s, query, mode, start, end)

        active_days = sorted(
            {
                r["date"][:8]
                for r in timelines
                if r["query"] == query and r["mode"] == "timelinevolraw" and r["value"]
            }
        )
        log.info("  %d days with coverage", len(active_days))

        for day in tqdm(active_days, desc=f"GDELT {query[:30]}"):
            d0 = datetime.strptime(day, "%Y%m%d")
            slices = [(d0, d0 + timedelta(days=1))]
            batch = _articles(s, query, *slices[0])
            if len(batch) >= CAP:
                batch = []
                for h in range(0, 24, 6):
                    batch += _articles(
                        s, query, d0 + timedelta(hours=h), d0 + timedelta(hours=h + 6)
                    )
            for art in batch:
                rec = articles.setdefault(art["url"], {**art, "queries": []})
                rec["queries"].append(query)

    return timelines, articles
