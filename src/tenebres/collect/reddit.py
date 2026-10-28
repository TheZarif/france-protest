"""Reddit collector via the Arctic Shift archive (no Reddit API key needed).

Docs: https://github.com/ArthurHeitmann/arctic_shift/blob/master/api/README.md

Arctic Shift mirrors Reddit posts and comments. Full-text search (`query`
for posts, `body` for comments) only works within one subreddit, so we sweep
the subreddits listed in config/queries.yaml. To reach subreddits outside
that list we also search site-wide by URL (a prefix match) for every news
article in data/processed/, then give any newly discovered subreddit the same
text sweep. For every post found we fetch its full comment tree, since
discussion of the slogan often happens in threads whose title doesn't name it.

Arctic Shift throttles heavy users (HTTP 422 "Timeout. Maybe slow down a
bit"), so every response is cached (data/interim/reddit_cache/) and a run cut
short by throttling resumes where it stopped when re-run.

Outputs (data/raw/reddit/), written only once every request has succeeded:
  posts_*.jsonl          posts found by text sweep or URL search
                         (`matched_by`: "text:<query>" or "url")
  comments_*.jsonl       matching comments (from subreddit sweep)
  threads_*.jsonl        {post_id, comments: [...]} trees under matching posts
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

import pandas as pd
import requests
from tqdm import tqdm

from ..common import (
    INTERIM, PROCESSED, ResponseCache, get_with_retry, load_config, log, raw_path, session,
    write_jsonl,
)

API = "https://arctic-shift.photon-reddit.com/api"
PAUSE = 10.0
# Arctic Shift answers 422 "Timeout. Maybe slow down a bit" for a while after a
# heavy search. Waits: 1, 2, 4, 8, 15, 15, 15, 15 min (~75 min), then give up.
TIMEOUT_WAITS = [60, 120, 240, 480, 900, 900, 900, 900]
CHUNK = timedelta(days=7)  # comment full-text search times out on long windows
CACHE = ResponseCache(INTERIM / "reddit_cache")


class Incomplete(RuntimeError):
    """Arctic Shift stopped answering before every request was made."""


def _get(s, path: str, **params) -> list[dict]:
    window_end = datetime.fromisoformat(params["before"]) if "before" in params else None
    key = {"path": path, **params}
    if (hit := CACHE.get(key, window_end)) is not None:
        return hit
    for wait in TIMEOUT_WAITS:
        try:
            r = s.get(f"{API}/{path}", params=params, timeout=180)
        except requests.RequestException as e:
            log.warning("Arctic Shift connection error on %s (%s), waiting %ds", path, e, wait)
        else:
            if r.status_code != 422:
                break
            log.warning("Arctic Shift timeout on %s, waiting %ds", path, wait)
        time.sleep(wait)
    else:
        raise Incomplete(f"Arctic Shift kept timing out on {path}")
    if r.status_code == 429 or r.status_code >= 500:  # retry with the shared backoff rules
        try:
            r = get_with_retry(s, f"{API}/{path}", params=params, backoff=10, timeout=180)
        except RuntimeError as e:
            raise Incomplete(str(e)) from e
    time.sleep(PAUSE)
    try:
        body = r.json()
    except ValueError:
        body = {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
    if body.get("error"):  # bad parameters, unknown subreddit...: not worth retrying
        log.warning("Arctic Shift error on %s %s: %s", path, params, body["error"])
        data = []
    else:
        data = body.get("data") or []
    CACHE.put(key, data)
    return data


def _search_all(s, path: str, after: str, before: str, **params) -> list[dict]:
    """Page through results by moving `after` forward (sorted ascending)."""
    out: list[dict] = []
    while True:
        batch = _get(s, path, after=after, before=before, sort="asc", limit=100, **params)
        out += batch
        if len(batch) < 100:
            return out
        after = str(int(batch[-1]["created_utc"]) + 1)


def _chunks(after: str, before: str):
    t, end = date.fromisoformat(after), date.fromisoformat(before)
    while t < end:
        yield str(t), str(min(t + CHUNK, end))
        t += CHUNK


def _article_urls() -> list[str]:
    """Publisher URLs of the news articles collected so far (query strings dropped)."""
    urls: set[str] = set()
    for name, col in (("news_context", "resolved_url"), ("news_articles", "url")):
        path = PROCESSED / f"{name}.parquet"
        if path.exists():
            urls |= set(pd.read_parquet(path, columns=[col])[col].dropna())
    out = set()
    for u in urls:
        parts = urlsplit(u)
        if parts.netloc.endswith("news.google.com"):
            continue
        out.add(f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/"))
    return sorted(u for u in out if 14 <= len(u) <= 500)


def _sweep(s, sub: str, rcfg: dict, after: str, before: str, posts: dict, comments: dict) -> None:
    for q in rcfg["queries"]:
        for p in _search_all(s, "posts/search", after, before, subreddit=sub, query=q):
            posts.setdefault(p["id"], {**p, "matched_by": f"text:{q}"})
        for a, b in _chunks(after, before):
            for c in _search_all(s, "comments/search", a, b, subreddit=sub, body=q):
                comments.setdefault(c["id"], c)


def collect() -> None:
    cfg = load_config()
    s = session()
    n_cached = len(CACHE)
    if n_cached:
        log.info("Reddit: resuming with %d cached responses", n_cached)
    try:
        posts, comments, threads = _collect(s, cfg)
    except Incomplete as e:
        log.error(
            "Reddit stopped (%s). %d responses cached (%d new this run); "
            "re-run `tenebres collect reddit` to resume.",
            e, len(CACHE), len(CACHE) - n_cached,
        )
        return
    write_jsonl(posts.values(), raw_path("reddit", "posts"))
    write_jsonl(comments.values(), raw_path("reddit", "comments"))
    write_jsonl(threads, raw_path("reddit", "threads"))


def _collect(s, cfg: dict) -> tuple[dict, dict, list]:
    rcfg = cfg["reddit"]
    after = str(cfg["study_window"]["start"])
    before = str(cfg["study_window"]["end"] + timedelta(days=1))

    posts: dict[str, dict] = {}
    comments: dict[str, dict] = {}
    swept = {sub.lower() for sub in rcfg["subreddits"]}
    for sub in tqdm(rcfg["subreddits"], desc="Reddit subreddit sweep"):
        _sweep(s, sub, rcfg, after, before, posts, comments)
    log.info("Reddit sweep: %d posts, %d comments", len(posts), len(comments))

    urls = _article_urls()
    for u in tqdm(urls, desc="Reddit URL search"):
        for p in _get(s, "posts/search", url=u, after=after, before=before, limit=100):
            posts.setdefault(p["id"], {**p, "matched_by": "url"})
    found = sorted({p["subreddit"] for p in posts.values()}, key=str.lower)
    new_subs = [sub for sub in found if sub.lower() not in swept]
    log.info("Reddit URL search: %d article URLs, %d new subreddits", len(urls), len(new_subs))
    for sub in tqdm(new_subs, desc="Reddit sweep (discovered)"):
        _sweep(s, sub, rcfg, after, before, posts, comments)
    log.info("Reddit: %d posts, %d comments", len(posts), len(comments))

    threads = []
    for pid in tqdm(posts, desc="Reddit threads"):
        tree = _get(s, "comments/tree", link_id=pid, limit=25000)
        threads.append({"post_id": pid, "comments": tree})
    return posts, comments, threads
