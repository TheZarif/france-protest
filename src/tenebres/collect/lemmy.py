"""Lemmy collector (public search API, no login).

Lemmy is a federated Reddit alternative; jlai.lu is its main francophone
instance. Search on each instance covers everything it federates with, so we
query a few large instances and deduplicate on each item's global `ap_id`.

Output (data/raw/lemmy/):
  posts_*.jsonl     post views (post, creator, community, counts) + `instance`
  comments_*.jsonl  comment views (comment, post, creator, community, counts)
"""

from __future__ import annotations

import time
from datetime import datetime

from tqdm import tqdm

from ..common import get_with_retry, load_config, log, raw_path, session, write_jsonl

PAUSE = 1.0
LIMIT = 50


def _search(s, instance: str, q: str, kind: str, since: str) -> list[dict]:
    """All results of one type, newest first, back to the study-window start."""
    key = {"Posts": "posts", "Comments": "comments"}[kind]
    out: list[dict] = []
    for page in range(1, 101):
        r = get_with_retry(
            s, f"https://{instance}/api/v3/search",
            params={"q": q, "type_": kind, "sort": "New", "limit": LIMIT, "page": page},
        )
        time.sleep(PAUSE)
        batch = r.json().get(key, [])
        out += batch
        oldest = min((b[kind[:-1].lower()]["published"] for b in batch), default="")
        if len(batch) < LIMIT or oldest < since:
            break
    return out


def collect() -> None:
    cfg = load_config()
    lcfg = cfg["lemmy"]
    since = datetime.combine(cfg["study_window"]["start"], datetime.min.time()).isoformat()
    s = session()
    posts: dict[str, dict] = {}
    comments: dict[str, dict] = {}

    for instance in tqdm(lcfg["instances"], desc="Lemmy instances"):
        try:
            for q in lcfg["queries"]:
                for p in _search(s, instance, q, "Posts", since):
                    posts.setdefault(p["post"]["ap_id"], {**p, "instance": instance})
                for c in _search(s, instance, q, "Comments", since):
                    comments.setdefault(c["comment"]["ap_id"], {**c, "instance": instance})
        except Exception as e:  # one unreachable instance shouldn't stop the rest
            log.warning("  %s failed: %s", instance, e)

    write_jsonl(posts.values(), raw_path("lemmy", "posts"))
    write_jsonl(comments.values(), raw_path("lemmy", "comments"))
    log.info("Lemmy: %d posts, %d comments (before keyword filtering)", len(posts), len(comments))
