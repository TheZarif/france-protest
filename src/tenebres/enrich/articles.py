"""Download news article text and extract how the slogan is used in context.

Headlines alone undercount usage: many articles mention the slogan only in
the body. For each article in news_articles we:
  1. resolve Google News redirect links to the publisher URL,
  2. download and extract the main text with trafilatura,
  3. record whether the body contains the slogan, and pull a keyword-in-
     context (KWIC) window around each mention.

Full texts stay in data/interim/ (copyrighted; for local analysis only).
Output: data/processed/news_context.{parquet,csv}
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import trafilatura
from tqdm import tqdm

from ..common import INTERIM, PROCESSED, load_config, log, strip_accents

KWIC_CHARS = 300


def _resolve(url: str) -> str:
    if "news.google.com" not in url:
        return url
    try:
        from googlenewsdecoder import gnewsdecoder

        res = gnewsdecoder(url, interval=1)
        return res.get("decoded_url") or url if res.get("success") else url
    except Exception as e:
        log.debug("decode failed %s: %s", url, e)
        return url


def _fetch(url: str) -> dict:
    resolved = _resolve(url)
    html = trafilatura.fetch_url(resolved)
    text = trafilatura.extract(html, favor_recall=True) if html else None
    return {"url": url, "resolved_url": resolved, "text": text or ""}


def _contexts(text: str, pattern: re.Pattern) -> list[str]:
    flat = strip_accents(text)
    out = []
    for m in pattern.finditer(flat):  # NFKD stripping keeps offsets aligned for Latin text
        a, b = max(0, m.start() - KWIC_CHARS), min(len(text), m.end() + KWIC_CHARS)
        out.append(re.sub(r"\s+", " ", text[a:b]).strip())
    return out


def run() -> None:
    cfg = load_config()
    news = pd.read_parquet(PROCESSED / "news_articles.parquet")
    cache_path = INTERIM / "article_text.parquet"
    cache = pd.read_parquet(cache_path) if cache_path.exists() else pd.DataFrame(columns=["url"])
    todo = [u for u in news["url"].unique() if u not in set(cache["url"])]
    log.info("fetching %d articles (%d cached)", len(todo), len(cache))

    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for r in tqdm(pool.map(_fetch, todo), total=len(todo), desc="articles"):
            results.append(r)
    cache = pd.concat([cache, pd.DataFrame(results)], ignore_index=True)
    cache = cache[cache["text"].fillna("").str.len() > 0]  # retry failures next run
    INTERIM.mkdir(parents=True, exist_ok=True)
    cache.to_parquet(cache_path, index=False)

    pattern = re.compile(strip_accents(cfg["match_regex"]), re.IGNORECASE)
    loose = re.compile(r"bismil+ah?", re.IGNORECASE)
    rows = []
    for r in cache.itertuples():
        text = r.text or ""
        ctx = _contexts(text, pattern) or _contexts(text, loose)
        rows.append(
            {
                "url": r.url,
                "resolved_url": r.resolved_url,
                "text_chars": len(text),
                "body_has_phrase": bool(pattern.search(strip_accents(text))),
                "n_mentions": len(ctx),
                "first_context": ctx[0] if ctx else "",
                "all_contexts": " ||| ".join(ctx),
            }
        )
    out = pd.DataFrame(rows)
    out.to_parquet(PROCESSED / "news_context.parquet", index=False)
    out.to_csv(PROCESSED / "news_context.csv", index=False)
    log.info("news_context: %d rows, %d with phrase in body", len(out), out["body_has_phrase"].sum())
