"""Wikipedia attention signals: which language editions have an article on
the slogan, when each was created, and daily pageviews per edition.

Pageviews are a cheap proxy for public curiosity ("what does this mean?")
and the creation dates show the order in which language communities picked
the topic up.

Outputs (data/raw/wikipedia/):
  pageviews_*.jsonl   {lang, title, date, views}
  revisions_*.jsonl   {lang, title, timestamp, user, size} (full edit history)
"""

from __future__ import annotations

import time
from urllib.parse import quote

from ..common import get_with_retry, load_config, log, raw_path, session, write_jsonl

PV = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"


def _langlinks(s, lang: str, title: str) -> dict[str, str]:
    r = get_with_retry(
        s,
        f"https://{lang}.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "titles": title,
            "prop": "langlinks",
            "lllimit": "max",
            "format": "json",
        },
    )
    links = {lang: title}
    for page in r.json()["query"]["pages"].values():
        for ll in page.get("langlinks", []):
            links[ll["lang"]] = ll["*"]
    return links


def _revisions(s, lang: str, title: str) -> list[dict]:
    out, cont = [], {}
    while True:
        r = get_with_retry(
            s,
            f"https://{lang}.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": title,
                "prop": "revisions",
                "rvprop": "timestamp|user|size|comment",
                "rvlimit": "max",
                "rvdir": "newer",
                "format": "json",
                **cont,
            },
        )
        body = r.json()
        for page in body["query"]["pages"].values():
            for rev in page.get("revisions", []):
                out.append({"lang": lang, "title": title, **rev})
        if "continue" not in body:
            return out
        cont = body["continue"]


def collect() -> None:
    cfg = load_config()
    wcfg = cfg["wikipedia"]
    start = cfg["study_window"]["start"].strftime("%Y%m%d")
    end = cfg["study_window"]["end"].strftime("%Y%m%d")
    s = session()

    links = _langlinks(s, wcfg["seed_lang"], wcfg["seed_title"])
    log.info("Wikipedia editions: %s", ", ".join(sorted(links)))

    views, revs = [], []
    for lang, title in links.items():
        article = quote(title.replace(" ", "_"), safe="")
        url = f"{PV}/{lang}.wikipedia/all-access/user/{article}/daily/{start}/{end}"
        try:
            items = get_with_retry(s, url, tries=2).json().get("items", [])
        except Exception as e:  # 404 = no views recorded yet
            log.warning("  no pageviews for %s:%s (%s)", lang, title, e)
            items = []
        views += [
            {"lang": lang, "title": title, "date": it["timestamp"][:8], "views": it["views"]}
            for it in items
        ]
        revs += _revisions(s, lang, title)
        time.sleep(0.5)

    write_jsonl(views, raw_path("wikipedia", "pageviews"))
    write_jsonl(revs, raw_path("wikipedia", "revisions"))
    log.info("Wikipedia: %d pageview rows, %d revisions", len(views), len(revs))
