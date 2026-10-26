"""Bluesky collector (public AppView, no login needed).

Endpoints: https://docs.bsky.app/docs/api/app-bsky-feed-search-posts

Unauthenticated search serves only the first page of results (cursors get
HTTP 403), so we search in time windows and split any window that comes
back full. Then:
  * look up author profiles (follower counts, for reach/influence), and
  * for the most-shared posts, pull quote posts and the list of reposters
    to sketch how those posts cascaded.

Outputs (data/raw/bluesky/):
  posts_*.jsonl     full post views as returned by the API (+ `query`)
  authors_*.jsonl   profile views for every author seen
  cascades_*.jsonl  {uri, quotes: [...], reposted_by: [...]} for top posts
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from tqdm import tqdm

from ..common import get_with_retry, load_config, log, raw_path, session, write_jsonl

API = "https://api.bsky.app/xrpc"
PAUSE = 0.3
TOP_N_CASCADES = 40
MIN_WINDOW = timedelta(minutes=5)


def _get(s, method: str, **params) -> dict:
    r = get_with_retry(s, f"{API}/{method}", params=params, backoff=5)
    time.sleep(PAUSE)
    return r.json()


def _paginate(s, method: str, key: str, max_items: int = 10_000, **params) -> list[dict]:
    out, cursor = [], None
    while len(out) < max_items:
        try:
            data = _get(s, method, limit=100, cursor=cursor, **params)
        except Exception as e:
            log.warning("  %s stopped after %d items: %s", method, len(out), e)
            break
        out += data.get(key, [])
        cursor = data.get("cursor")
        if not cursor or not data.get(key):
            break
    return out


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _search_window(s, q: str, t0: datetime, t1: datetime) -> list[dict]:
    """Search [t0, t1). Unauthenticated search refuses cursors (HTTP 403), so
    when a window comes back full we split it in half instead of paging."""
    posts = _get(s, "app.bsky.feed.searchPosts", q=q, sort="latest", limit=100,
                 since=_iso(t0), until=_iso(t1)).get("posts", [])
    if len(posts) < 100 or t1 - t0 <= MIN_WINDOW:
        if len(posts) >= 100:
            log.warning("  window %s–%s still full; some posts missed", _iso(t0), _iso(t1))
        return posts
    mid = t0 + (t1 - t0) / 2
    return _search_window(s, q, t0, mid) + _search_window(s, q, mid, t1)


def collect() -> None:
    cfg = load_config()
    start, end = cfg["study_window"]["start"], cfg["study_window"]["end"]
    s = session()

    posts: dict[str, dict] = {}
    days = [datetime.combine(start + timedelta(days=i), datetime.min.time())
            for i in range((end - start).days + 1)]
    for q in cfg["bluesky"]["queries"]:
        for d in tqdm(days, desc=f"Bluesky {q[:25]}"):
            batch = _search_window(s, q, d, d + timedelta(days=1))
            for p in batch:
                rec = posts.setdefault(p["uri"], {**p, "queries": []})
                rec["queries"].append(q)
    log.info("Bluesky: %d unique posts", len(posts))

    dids = sorted({p["author"]["did"] for p in posts.values()})
    authors = []
    for i in tqdm(range(0, len(dids), 25), desc="Bluesky profiles"):
        authors += _get(s, "app.bsky.actor.getProfiles", actors=dids[i : i + 25]).get(
            "profiles", []
        )

    top = sorted(
        posts.values(),
        key=lambda p: p.get("repostCount", 0) + p.get("quoteCount", 0),
        reverse=True,
    )[:TOP_N_CASCADES]
    cascades = []
    for p in tqdm(top, desc="Bluesky cascades"):
        cascades.append(
            {
                "uri": p["uri"],
                "quotes": _paginate(s, "app.bsky.feed.getQuotes", "posts", uri=p["uri"]),
                "reposted_by": _paginate(
                    s, "app.bsky.feed.getRepostedBy", "repostedBy", uri=p["uri"]
                ),
            }
        )

    write_jsonl(posts.values(), raw_path("bluesky", "posts"))
    write_jsonl(authors, raw_path("bluesky", "authors"))
    write_jsonl(cascades, raw_path("bluesky", "cascades"))
    log.info("Bluesky: %d authors, %d cascades", len(authors), len(cascades))
