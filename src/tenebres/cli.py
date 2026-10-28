"""Command-line entry point.

    uv run tenebres collect all            # every source
    uv run tenebres collect gdelt bluesky  # just some
    uv run tenebres process                # raw -> data/processed tables
    uv run tenebres enrich                 # sentiment/toxicity (needs --extra nlp)
    uv run tenebres fetch-articles         # article text + slogan context
"""

from __future__ import annotations

import argparse
import importlib
import logging

SOURCES = ["gdelt", "google_news", "bluesky", "reddit", "mastodon", "lemmy", "wikipedia"]


def main() -> None:
    parser = argparse.ArgumentParser(prog="tenebres", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="download raw data from one or more sources")
    c.add_argument("sources", nargs="+", choices=SOURCES + ["all"])

    sub.add_parser("process", help="clean, filter and merge raw data into tables")
    sub.add_parser("fetch-articles", help="download article text and extract slogan context")
    sub.add_parser("enrich", help="add sentiment and toxicity scores (needs --extra nlp)")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    for noisy in ("httpx", "trafilatura", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if args.cmd == "collect":
        sources = SOURCES if "all" in args.sources else args.sources
        for src in sources:
            mod = importlib.import_module(f"tenebres.collect.{src}")
            try:
                mod.collect()
            except Exception:
                logging.exception("collector %s failed; continuing with the rest", src)
    elif args.cmd == "process":
        from tenebres.process import run
        run()
    elif args.cmd == "fetch-articles":
        from tenebres.enrich.articles import run
        run()
    elif args.cmd == "enrich":
        from tenebres.enrich.nlp import run
        run()


if __name__ == "__main__":
    main()
