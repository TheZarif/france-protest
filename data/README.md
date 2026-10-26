# Data

Nothing in this folder except this README is committed to git.

| Folder | Contents | Made by |
|---|---|---|
| `raw/<source>/` | API responses exactly as received, one JSONL file per run, named `<name>_<UTC timestamp>.jsonl` | `tenebres collect` |
| `interim/` | downloaded article text (`article_text.parquet`), cached so reruns only fetch new articles | `tenebres fetch-articles` |
| `processed/` | analysis tables as `.parquet` (code) and `.csv` (spreadsheets) | `tenebres process`, `fetch-articles`, `enrich` |

Column definitions are in [`docs/data_dictionary.md`](../docs/data_dictionary.md).

## Why it isn't in git

- **Personal data.** Social posts carry usernames and display names. Keep them on the team drive, and quote individuals in publications only if they are public figures or have consented. Otherwise paraphrase.
- **Terms of use.** Google News RSS is licensed for personal, non-commercial use, and article texts are copyrighted. Both are used here for academic analysis only and must not be redistributed.
- **Reproducibility.** Everything can be rebuilt with `uv run tenebres collect all`. Note, though, that platforms delete posts and search results shift over time, so **archive the raw snapshots** used for any published figure.
