"""Turn raw API dumps into tidy analysis tables in data/processed/.

Each table is written as both .parquet (for code) and .csv (for spreadsheets).
See docs/data_dictionary.md for column definitions.

  news_articles      one row per unique news article (GDELT + Google News),
                     joined to the outlet coding in config/outlets.csv
  social_posts       one row per post/comment (Bluesky, Reddit, Mastodon)
                     that mentions the slogan
  bluesky_edges      quote and repost edges for the most-shared Bluesky posts
  gdelt_timelines    GDELT daily volume / tone / country / language series
  wiki_pageviews     daily Wikipedia pageviews per language edition
  wiki_revisions     Wikipedia edit history per language edition
"""

from __future__ import annotations

import re
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import pandas as pd

from .common import CONFIG_DIR, PROCESSED, latest_raw, load_config, log, phrase_matcher, read_jsonl, strip_accents

TLD_COUNTRY = {
    "fr": "FR", "be": "BE", "ch": "CH", "ca": "CA", "it": "IT", "de": "DE", "es": "ES",
    "uk": "GB", "ma": "MA", "dz": "DZ", "tn": "TN", "sn": "SN", "tr": "TR", "nl": "NL",
    "pt": "PT", "at": "AT", "lu": "LU", "ie": "IE", "pl": "PL", "se": "SE", "dk": "DK",
    "no": "NO", "fi": "FI", "gr": "GR", "ro": "RO", "in": "IN", "pk": "PK", "bd": "BD",
    "il": "IL", "qa": "QA", "ae": "AE", "sa": "SA", "eg": "EG", "lb": "LB", "ci": "CI",
    "cm": "CM", "ml": "ML", "bf": "BF", "re": "FR", "mq": "FR", "gp": "FR", "nc": "FR",
    "pf": "FR", "br": "BR", "ar": "AR", "mx": "MX", "au": "AU", "nz": "NZ", "jp": "JP",
    "ru": "RU", "ua": "UA",
}
# GDELT reports source country as an English name.
GDELT_COUNTRY = {
    "France": "FR", "Belgium": "BE", "Switzerland": "CH", "Canada": "CA", "Italy": "IT",
    "Germany": "DE", "Spain": "ES", "United Kingdom": "GB", "United States": "US",
    "Morocco": "MA", "Algeria": "DZ", "Tunisia": "TN", "Senegal": "SN", "Turkey": "TR",
    "Netherlands": "NL", "Portugal": "PT", "Austria": "AT", "Luxembourg": "LU",
    "Ireland": "IE", "India": "IN", "Pakistan": "PK", "Bangladesh": "BD", "Israel": "IL",
    "Qatar": "QA", "United Arab Emirates": "AE", "Saudi Arabia": "SA", "Egypt": "EG",
    "Lebanon": "LB", "Russia": "RU", "Australia": "AU", "Ivory Coast": "CI",
    "Cameroon": "CM", "Poland": "PL", "Sweden": "SE", "Greece": "GR", "Romania": "RO",
}
LEANING_ORDER = ["far-left", "left", "center-left", "center", "center-right", "right", "far-right"]


def _save(df: pd.DataFrame, name: str) -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED / f"{name}.parquet", index=False)
    df.to_csv(PROCESSED / f"{name}.csv", index=False)
    log.info("wrote %s (%d rows)", name, len(df))


def _latest(source: str, name: str) -> list[dict]:
    files = latest_raw(source, name)
    if not files:
        log.warning("no raw data for %s/%s yet", source, name)
        return []
    return read_jsonl(files[-1])


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url if "//" in url else f"//{url}").hostname or ""
    return host.removeprefix("www.").lower() or None


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", strip_accents(str(t)).lower()).strip()


# --------------------------------------------------------------------- news

def load_outlets() -> pd.DataFrame:
    return pd.read_csv(CONFIG_DIR / "outlets.csv", dtype=str, keep_default_na=False)


def match_outlet(domain: str | None, outlets: pd.DataFrame) -> dict:
    """Longest-suffix match, so fr.euronews.com -> euronews.com and
    rmc.bfmtv.com wins over bfmtv.com."""
    if not domain:
        return {}
    by_domain = outlets.set_index("domain").to_dict("index")
    parts = domain.split(".")
    for i in range(len(parts) - 1):
        cand = ".".join(parts[i:])
        if cand in by_domain:
            return {"outlet_domain": cand, **by_domain[cand]}
    return {}


def _gdelt_articles() -> pd.DataFrame:
    rows = _latest("gdelt", "articles")
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return pd.DataFrame(
        {
            "title": df["title"],
            "url": df["url"],
            "domain": df["domain"].str.removeprefix("www."),
            "published_at": pd.to_datetime(df["seendate"], format="%Y%m%dT%H%M%SZ", utc=True),
            "language": df["language"],
            "gdelt_country": df["sourcecountry"],
            "found_in": "gdelt",
            "gn_editions": "",
        }
    )


def _google_news_articles() -> pd.DataFrame:
    rows = _latest("google_news", "articles")
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Titles come as "Headline - Publisher"; drop the publisher suffix.
    df["title"] = [
        t[: -len(f" - {s}")] if s and t.endswith(f" - {s}") else t
        for t, s in zip(df["title"], df["source_name"])
    ]
    df["published_at"] = [parsedate_to_datetime(p) for p in df["published"]]
    df["domain"] = df["source_url"].map(_domain)
    df["key"] = df["domain"].fillna("") + "|" + df["title"].map(_norm_title)
    editions = df.groupby("key")["edition"].agg(lambda e: ";".join(sorted(set(e))))
    df = df.drop_duplicates("key").set_index("key")
    df["gn_editions"] = editions
    return pd.DataFrame(
        {
            "title": df["title"],
            "url": df["link"],  # Google redirect; resolved by `fetch-articles`
            "domain": df["domain"],
            "published_at": pd.to_datetime(df["published_at"], utc=True),
            "language": df["edition"].str.split(":").str[1],
            "gdelt_country": "",
            "found_in": "google_news",
            "gn_editions": df["gn_editions"],
            "outlet_name_gn": df["source_name"],
        }
    ).reset_index(drop=True)


def build_news(cfg: dict) -> pd.DataFrame:
    matches = phrase_matcher(cfg)
    df = pd.concat([_gdelt_articles(), _google_news_articles()], ignore_index=True)
    if df.empty:
        return df

    # Merge the two sources: the same (domain, title) found by both is one article.
    df["key"] = df["domain"].fillna("") + "|" + df["title"].map(_norm_title)
    found = df.groupby("key")["found_in"].agg(lambda s: ";".join(sorted(set(s))))
    df = df.sort_values("found_in").drop_duplicates("key", keep="first")  # prefer GDELT url
    df["found_in"] = df["key"].map(found)

    outlets = load_outlets()
    coded = pd.DataFrame([match_outlet(d, outlets) for d in df["domain"]], index=df.index)
    coded = coded.reindex(columns=["outlet_domain", *outlets.columns.drop("domain")])
    df = df.join(coded.rename(columns={"language": "outlet_language"}))
    df["outlet"] = df["outlet"].fillna(df.get("outlet_name_gn")).fillna(df["domain"])
    tld = df["domain"].fillna("").str.rsplit(".", n=1).str[-1].map(TLD_COUNTRY)
    df["country"] = (
        df["country"].replace("", pd.NA)
        .fillna(df["gdelt_country"].map(GDELT_COUNTRY))
        .fillna(tld)
        .fillna("unknown")
    )
    df["leaning"] = df["leaning"].replace("", pd.NA).fillna("uncoded")
    df["title_has_phrase"] = df["title"].map(matches)
    df["date"] = df["published_at"].dt.tz_convert("Europe/Paris").dt.date

    cols = [
        "date", "published_at", "title", "outlet", "domain", "country", "language",
        "leaning", "media_type", "ownership_type", "owner_group", "found_in",
        "gn_editions", "title_has_phrase", "url",
    ]
    return df[cols].sort_values("published_at").reset_index(drop=True)


# ------------------------------------------------------------------- social

def _bluesky() -> tuple[pd.DataFrame, pd.DataFrame]:
    posts = _latest("bluesky", "posts")
    authors = {a["did"]: a for a in _latest("bluesky", "authors")}
    rows = []
    for p in posts:
        rec, a = p["record"], p["author"]
        embed = rec.get("embed") or {}
        quoted = (embed.get("record") or {}).get("uri") or (
            (embed.get("record") or {}).get("record") or {}
        ).get("uri")
        rkey = p["uri"].rsplit("/", 1)[-1]
        prof = authors.get(a["did"], {})
        rows.append(
            {
                "platform": "bluesky",
                "post_id": p["uri"],
                "url": f"https://bsky.app/profile/{a['handle']}/post/{rkey}",
                "author": a["handle"],
                "author_name": a.get("displayName"),
                "author_followers": prof.get("followersCount"),
                "created_at": rec.get("createdAt"),
                "text": rec.get("text", ""),
                "lang": ";".join(rec.get("langs") or []),
                "likes": p.get("likeCount", 0),
                "reposts": p.get("repostCount", 0),
                "replies": p.get("replyCount", 0),
                "quotes": p.get("quoteCount", 0),
                "is_reply": "reply" in rec,
                "parent_id": (rec.get("reply") or {}).get("parent", {}).get("uri"),
                "quoted_id": quoted,
                "community": None,
                "link_domain": _domain((embed.get("external") or {}).get("uri")),
            }
        )
    edges = []
    for c in _latest("bluesky", "cascades"):
        for q in c["quotes"]:
            edges.append({"type": "quote", "source": q["uri"], "source_author": q["author"]["handle"],
                          "target": c["uri"], "created_at": q["record"].get("createdAt")})
        for r in c["reposted_by"]:
            edges.append({"type": "repost", "source": r["did"], "source_author": r["handle"],
                          "target": c["uri"], "created_at": None})
    return pd.DataFrame(rows), pd.DataFrame(edges)


def _reddit() -> pd.DataFrame:
    rows = []
    for p in _latest("reddit", "posts"):
        rows.append({
            "platform": "reddit", "post_id": f"t3_{p['id']}",
            "url": f"https://www.reddit.com{p.get('permalink', '')}",
            "author": p.get("author"), "created_at": p.get("created_utc"),
            "text": f"{p.get('title', '')}\n\n{p.get('selftext', '')}".strip(),
            "likes": p.get("score"), "replies": p.get("num_comments"),
            "is_reply": False, "community": p.get("subreddit"),
            "link_domain": _domain(p.get("url")) if not p.get("is_self") else None,
        })
    comments = {c["id"]: c for c in _latest("reddit", "comments")}

    def walk(nodes):
        for n in nodes:
            d = n.get("data", n)
            if n.get("kind") == "more" or "body" not in d:
                continue
            comments.setdefault(d["id"], d)
            replies = d.get("replies")
            if isinstance(replies, dict):
                walk(replies.get("data", {}).get("children", []))
            elif isinstance(replies, list):
                walk(replies)

    for t in _latest("reddit", "threads"):
        walk(t["comments"])
    for c in comments.values():
        rows.append({
            "platform": "reddit", "post_id": f"t1_{c['id']}",
            "url": f"https://www.reddit.com{c.get('permalink', '')}",
            "author": c.get("author"), "created_at": c.get("created_utc"),
            "text": c.get("body", ""), "likes": c.get("score"),
            "is_reply": True, "parent_id": c.get("parent_id"), "community": c.get("subreddit"),
        })
    return pd.DataFrame(rows)


def _mastodon() -> pd.DataFrame:
    rows = []
    for s in _latest("mastodon", "posts"):
        text = re.sub(r"<[^>]+>", " ", s.get("content", ""))
        rows.append({
            "platform": "mastodon", "post_id": s["uri"], "url": s.get("url") or s["uri"],
            "author": s["account"]["acct"], "author_name": s["account"].get("display_name"),
            "author_followers": s["account"].get("followers_count"),
            "created_at": s["created_at"], "text": re.sub(r"\s+", " ", text).strip(),
            "lang": s.get("language"), "likes": s.get("favourites_count"),
            "reposts": s.get("reblogs_count"), "replies": s.get("replies_count"),
            "quotes": s.get("quotes_count"), "is_reply": bool(s.get("in_reply_to_id")),
            "community": s["account"]["acct"].split("@")[-1] if "@" in s["account"]["acct"] else s["instance"],
        })
    return pd.DataFrame(rows)


def _lemmy() -> pd.DataFrame:
    def host(actor_id: str) -> str:
        return urlparse(actor_id or "").netloc

    rows = []
    for v in _latest("lemmy", "posts"):
        p, c = v["post"], v["community"]
        rows.append({
            "platform": "lemmy", "post_id": p["ap_id"], "url": p["ap_id"],
            "author": f"{v['creator']['name']}@{host(v['creator']['actor_id'])}",
            "created_at": p["published"],
            "text": f"{p.get('name', '')}\n\n{p.get('body') or ''}".strip(),
            "likes": v["counts"].get("score"), "replies": v["counts"].get("comments"),
            "is_reply": False, "community": f"{c['name']}@{host(c['actor_id'])}",
            "link_domain": _domain(p.get("url")) if p.get("url") else None,
        })
    for v in _latest("lemmy", "comments"):
        cm, c = v["comment"], v["community"]
        rows.append({
            "platform": "lemmy", "post_id": cm["ap_id"], "url": cm["ap_id"],
            "author": f"{v['creator']['name']}@{host(v['creator']['actor_id'])}",
            "created_at": cm["published"], "text": cm.get("content", ""),
            "likes": v["counts"].get("score"), "replies": v["counts"].get("child_count"),
            "is_reply": True, "parent_id": v["post"]["ap_id"],
            "community": f"{c['name']}@{host(c['actor_id'])}",
        })
    return pd.DataFrame(rows)


def build_social(cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    matches = phrase_matcher(cfg)
    bsky, edges = _bluesky()
    df = pd.concat([bsky, _reddit(), _mastodon(), _lemmy()], ignore_index=True)
    if df.empty:
        return df, edges
    ts = df["created_at"]
    numeric = pd.to_numeric(ts, errors="coerce")
    df["created_at"] = pd.to_datetime(
        numeric.where(numeric.notna()), unit="s", utc=True
    ).fillna(pd.to_datetime(ts.where(numeric.isna()), utc=True, errors="coerce", format="ISO8601"))

    flat = df["text"].fillna("").map(strip_accents).str.lower()
    df["phrase_exact"] = df["text"].map(matches)
    # Both French keywords anywhere, or a full translated rendering of the slogan.
    df["keyword_match"] = (flat.str.contains("bismil") & flat.str.contains("tenebre")) | df["phrase_exact"]
    df = df[df["keyword_match"]].copy()

    window_start = pd.Timestamp(cfg["study_window"]["start"], tz="UTC")
    df = df[df["created_at"] >= window_start]
    df["date"] = df["created_at"].dt.tz_convert("Europe/Paris").dt.date
    for col in ("likes", "reposts", "replies", "quotes"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["engagement"] = df[["likes", "reposts", "replies", "quotes"]].sum(axis=1)
    cols = [
        "platform", "date", "created_at", "author", "author_name", "author_followers",
        "community", "lang", "text", "phrase_exact", "likes", "reposts", "replies",
        "quotes", "engagement", "is_reply", "parent_id", "quoted_id", "link_domain",
        "post_id", "url",
    ]
    df = df.drop_duplicates("post_id").sort_values("created_at")
    return df[cols].reset_index(drop=True), edges


# --------------------------------------------------------------- the rest

def run() -> None:
    cfg = load_config()
    _save(build_news(cfg), "news_articles")
    social, edges = build_social(cfg)
    _save(social, "social_posts")
    if not edges.empty:
        _save(edges, "bluesky_edges")
    for source, name, out in [
        ("gdelt", "timelines", "gdelt_timelines"),
        ("wikipedia", "pageviews", "wiki_pageviews"),
        ("wikipedia", "revisions", "wiki_revisions"),
    ]:
        rows = _latest(source, name)
        if rows:
            _save(pd.DataFrame(rows), out)
