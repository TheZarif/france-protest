"""Shared paths, config loading, HTTP session and small helpers."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
FIGURES = ROOT / "reports" / "figures"

load_dotenv(ROOT / ".env")

log = logging.getLogger("tenebres")


def load_config() -> dict:
    with open(CONFIG_DIR / "queries.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    window = cfg["study_window"]
    window["start"] = date.fromisoformat(window["start"])
    window["end"] = date.fromisoformat(window["end"]) if window.get("end") else date.today()
    return cfg


def session() -> requests.Session:
    s = requests.Session()
    contact = os.getenv("TENEBRES_CONTACT", "research project")
    s.headers["User-Agent"] = f"tenebres-research/0.1 ({contact})"
    return s


def get_with_retry(
    s: requests.Session,
    url: str,
    params: dict | None = None,
    tries: int = 6,
    backoff: float = 10.0,
    timeout: float = 60.0,
) -> requests.Response:
    """GET with exponential backoff on 429/5xx and connection errors."""
    for attempt in range(tries):
        try:
            r = s.get(url, params=params, timeout=timeout)
        except requests.RequestException as e:
            log.warning("request error %s (attempt %d): %s", url, attempt + 1, e)
        else:
            if r.status_code < 400:
                return r
            if r.status_code not in (429, 500, 502, 503, 504, 520, 522, 530):
                r.raise_for_status()
            wait = float(r.headers.get("X-RateLimit-Reset", backoff * 2**attempt))
            log.warning("HTTP %s from %s, waiting %.0fs", r.status_code, url, wait)
            time.sleep(wait)
            continue
        time.sleep(backoff * 2**attempt)
    raise RuntimeError(f"giving up on {url} after {tries} attempts")


class ResponseCache:
    """One JSON file per API request, so a rate-limited collection can resume.

    Sources keep adding items for recent hours, so a response whose window
    ended less than `settle` before it was fetched is only reused for
    `stale_after`; responses for older windows are reused indefinitely.
    Pass window_end=None for requests with no time window (always "recent").
    """

    def __init__(self, directory: Path, settle=timedelta(hours=6), stale_after=timedelta(hours=12)):
        self.dir, self.settle, self.stale_after = directory, settle, stale_after

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def _file(self, params: dict) -> Path:
        key = json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)
        return self.dir / f"{hashlib.sha1(key.encode()).hexdigest()}.json"

    def __len__(self) -> int:
        return len(list(self.dir.glob("*.json"))) if self.dir.exists() else 0

    def get(self, params: dict, window_end: datetime | None):
        path = self._file(params)
        if not path.exists():
            return None
        entry = json.loads(path.read_text())
        fetched = datetime.fromisoformat(entry["fetched_at"])
        unsettled = window_end is None or window_end > fetched - self.settle
        if unsettled and self._now() - fetched > self.stale_after:
            return None
        return entry["response"]

    def put(self, params: dict, response) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self._file(params)
        entry = {"params": params, "fetched_at": self._now().isoformat(), "response": response}
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(entry, ensure_ascii=False, default=str))
        tmp.replace(path)


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def phrase_matcher(cfg: dict):
    """Return a function telling whether a text contains the slogan."""
    pattern = re.compile(strip_accents(cfg["match_regex"]), re.IGNORECASE)
    return lambda text: bool(text) and bool(pattern.search(strip_accents(text)))


SLOGAN_PLACEHOLDER = "«slogan»"


def mask_slogan(text: str, cfg: dict) -> str:
    """Replace every occurrence of the slogan with a neutral placeholder, so
    models score the surrounding text rather than the slogan's own words."""
    if not isinstance(text, str):
        return ""
    flat = strip_accents(text)
    pattern = re.compile(strip_accents(cfg["match_regex"]), re.IGNORECASE)
    out, last = [], 0
    for m in pattern.finditer(flat):  # accent stripping keeps offsets for Latin text
        out += [text[last : m.start()], SLOGAN_PLACEHOLDER]
        last = m.end()
    return "".join(out + [text[last:]])


def write_jsonl(records: Iterable[dict], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def raw_path(source: str, name: str) -> Path:
    """data/raw/<source>/<name>_<UTC timestamp>.jsonl, so reruns never overwrite."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return RAW / source / f"{name}_{stamp}.jsonl"


def latest_raw(source: str, name: str) -> list[Path]:
    """All raw snapshot files for a source/name, oldest first."""
    return sorted((RAW / source).glob(f"{name}_*.jsonl"))
