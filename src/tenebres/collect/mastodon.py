"""Mastodon / fediverse collector (public hashtag timelines, no login).

Full-text search needs an account on most instances, but hashtag timelines
are public. Each instance sees posts from the accounts it federates with, so
we query a handful of large general and French-speaking instances and
deduplicate on the post's global `uri`.

Output (data/raw/mastodon/posts_*.jsonl): status objects + `instance`, `tag`.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from urllib.parse import quote

from tqdm import tqdm

from ..common import get_with_retry, load_config, log, raw_path, session, write_jsonl

PAUSE = 1.0


def collect() -> None:
    cfg = load_config()
    mcfg = cfg["mastodon"]
    since = datetime.combine(cfg["study_window"]["start"], datetime.min.time(), timezone.utc)
    s = session()
    posts: dict[str, dict] = {}

    for inst in tqdm(mcfg["instances"], desc="Mastodon instances"):
        for tag in mcfg["hashtags"]:
            url = f"https://{inst}/api/v1/timelines/tag/{quote(tag)}"
            max_id = None
            while True:
                try:
                    r = get_with_retry(s, url, params={"limit": 40, "max_id": max_id}, tries=3)
                except Exception as e:
                    log.warning("  %s #%s failed: %s", inst, tag, e)
                    break
                time.sleep(PAUSE)
                batch = r.json()
                if not batch:
                    break
                for st in batch:
                    posts.setdefault(st["uri"], {**st, "instance": inst, "tag": tag})
                oldest = datetime.fromisoformat(batch[-1]["created_at"].replace("Z", "+00:00"))
                if oldest < since:
                    break
                max_id = batch[-1]["id"]

    n = write_jsonl(posts.values(), raw_path("mastodon", "posts"))
    log.info("Mastodon: %d unique statuses (pre-filter)", n)
