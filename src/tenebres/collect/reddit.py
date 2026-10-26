"""Reddit collector via the Arctic Shift archive (no Reddit API key needed).

Docs: https://github.com/ArthurHeitmann/arctic_shift/blob/master/api/README.md

Arctic Shift mirrors Reddit posts and comments. Post search (`query`, over
title + selftext) works site-wide; comment full-text search (`body`) needs a
subreddit, so we sweep the subreddits listed in config/queries.yaml. For
every matching post we also fetch its full comment tree, since discussion
of the slogan often happens in threads whose title doesn't contain it.

Outputs (data/raw/reddit/):
  posts_*.jsonl          matching submissions
  comments_*.jsonl       matching comments (from subreddit sweep)
  threads_*.jsonl        {post_id, comments: [...]} trees under matching posts
"""

from __future__ import annotations

import time
from datetime import timedelta

from tqdm import tqdm

from ..common import get_with_retry, load_config, log, raw_path, session, write_jsonl

API = "https://arctic-shift.photon-reddit.com/api"
PAUSE = 1.0


def _get(s, path: str, **params) -> list[dict]:
    r = get_with_retry(s, f"{API}/{path}", params=params, backoff=10, timeout=120)
    time.sleep(PAUSE)
    body = r.json()
    if body.get("error"):
        log.warning("Arctic Shift error on %s %s: %s", path, params, body["error"])
        return []
    return body.get("data") or []


def _search_all(s, path: str, after: str, before: str, **params) -> list[dict]:
    """Page through results by moving `after` forward (sorted ascending)."""
    out: list[dict] = []
    while True:
        batch = _get(s, path, after=after, before=before, sort="asc", limit=100, **params)
        out += batch
        if len(batch) < 100:
            return out
        after = str(int(batch[-1]["created_utc"]) + 1)


def collect() -> None:
    cfg = load_config()
    rcfg = cfg["reddit"]
    after = str(cfg["study_window"]["start"])
    before = str(cfg["study_window"]["end"] + timedelta(days=1))
    s = session()

    posts: dict[str, dict] = {}
    for q in rcfg["post_queries"]:
        for p in _search_all(s, "posts/search", after, before, query=q):
            posts.setdefault(p["id"], {**p, "matched_query": q})
    log.info("Reddit: %d matching posts", len(posts))

    comments: dict[str, dict] = {}
    for sub in tqdm(rcfg["comment_subreddits"], desc="Reddit comment sweep"):
        try:
            batch = _search_all(
                s, "comments/search", after, before, subreddit=sub, body=rcfg["comment_query"]
            )
        except Exception as e:  # one dead subreddit shouldn't stop the sweep
            log.warning("  r/%s failed: %s", sub, e)
            continue
        for c in batch:
            comments.setdefault(c["id"], c)
    log.info("Reddit: %d matching comments", len(comments))

    threads = []
    for pid in tqdm(posts, desc="Reddit threads"):
        tree = _get(s, "comments/tree", link_id=pid, limit=25000)
        threads.append({"post_id": pid, "comments": tree})

    write_jsonl(posts.values(), raw_path("reddit", "posts"))
    write_jsonl(comments.values(), raw_path("reddit", "comments"))
    write_jsonl(threads, raw_path("reddit", "threads"))
