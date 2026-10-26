# « Bismillah c'est les ténèbres »: tracing a protest slogan across media

How did a mocking line from a suspected police infiltrator's Snapchat message become the rallying cry of France's autumn 2026 lycée protests, and how did it travel across **news outlets** (by country and political leaning) and **social platforms**?

This repo collects the data, cleans it into analysis-ready tables, and holds the notebooks and write-ups.

**Start here:** [Initial EDA findings](reports/initial_eda.md) · [Background & timeline](docs/background.md) · [Methodology](docs/methodology.md) · [Data dictionary](docs/data_dictionary.md)

---

## Quick start

You need [uv](https://docs.astral.sh/uv/) (a Python package manager). Everything else is installed for you.

```bash
git clone <this repo> && cd france-protest
uv sync --extra notebooks              # core + Jupyter
uv sync --extra nlp --extra notebooks  # optional: also sentiment, toxicity, topic models (~2 GB)
cp .env.example .env                   # optional: add your contact email
```

Then run the pipeline. Each step reads the previous step's output:

```bash
uv run tenebres collect all     # 1. download raw data from every source   (~15 min)
uv run tenebres process         # 2. clean, filter, merge -> data/processed/
uv run tenebres fetch-articles  # 3. news article text + context around the slogan
uv run tenebres enrich          # 4. sentiment & toxicity scores (needs the nlp extra)
uv run jupyter lab notebooks/   # 5. explore
```

Collect a single source with e.g. `uv run tenebres collect bluesky`. Re-running a collector never overwrites old data: each run writes a new timestamped snapshot, and processing uses the latest one.

## Data sources

| Source | What we get | Access | Status (26 Oct 2026) |
|---|---|---|---|
| **Google News** (RSS) | headlines, outlet, date; 13 country/language editions | no key | ✅ 132 unique articles |
| **News article text** | full text + slogan context window (via trafilatura) | no key | ✅ 114 of 132 fetched (rest paywalled or bot-blocked) |
| **GDELT DOC 2.0** | global news in 65 languages, volume/tone/country timelines | no key, 1 req / 5 s | ⏳ API rate-limiting our IP; retry with `scripts/retry_when_up.sh` |
| **Bluesky** | posts, engagement, author follower counts, repost and quote cascades | no key | ✅ 1,091 matching posts, 3,687 cascade edges |
| **Mastodon** | public hashtag timelines from 5 large instances | no key | ✅ 118 matching posts |
| **Reddit** via [Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift) | posts, comments, full threads | no key | ⏳ Arctic Shift was down; retry script will collect it |
| **Wikipedia** | article creation per language, edit history, daily pageviews | no key | ✅ 5 language editions |

Not (yet) covered: **TikTok, Instagram, Snapchat, X**, where the slogan actually originated and spread most. These need research API access or paid tools; see [methodology § gaps](docs/methodology.md#known-gaps-and-biases).

## Repository layout

```
config/
  queries.yaml        search terms, variants, study window, per-source settings  ← edit me
  outlets.csv         outlet coding: country, media type, political leaning, owner ← review me
src/tenebres/
  collect/            one module per source (gdelt, google_news, bluesky, reddit, mastodon, wikipedia)
  process.py          raw -> tidy tables
  enrich/articles.py  fetch article text, extract slogan context
  enrich/nlp.py       sentiment + toxicity models
  viz.py              shared chart style and colours
  cli.py              the `tenebres` command
notebooks/
  01_initial_eda.ipynb
reports/
  initial_eda.md      findings write-up
  figures/            charts saved by the notebooks
docs/                 background, methodology, data dictionary
scripts/              helpers (e.g. retry collectors when an API is down)
data/                 NOT in git: raw/, interim/, processed/  (see data/README.md)
```

## Working together

- **Data is not committed to git.** Social posts contain usernames, and some sources' terms forbid redistribution. Share `data/processed/` through the team drive, or have each person run the pipeline (it takes about 15 minutes).
- **The outlet coding (`config/outlets.csv`) is a draft.** Leaning labels were seeded quickly and must be reviewed. Please edit them through pull requests, with a source in the `notes` column for anything contested. Uncoded domains are listed in the notebook.
- **New search terms or sources:** add them to `config/queries.yaml`, or add a module under `src/tenebres/collect/` exposing a `collect()` function, then register it in `cli.py`.
- **Notebooks:** number them (`02_...`), and keep heavy logic in `src/tenebres/` so it can be reused.

## Troubleshooting

- **GDELT returns HTTP 429** even at one request every 5 s: GDELT throttles by IP, and shared networks (university, VPN) are often blocked for hours. Run `scripts/retry_when_up.sh`, or collect from another network.
- **Arctic Shift returns 530/1033:** the service is temporarily down. Same script.
- **Bluesky returns 403 on paging:** unauthenticated search only serves first pages. The collector works around this by splitting time windows, so no action is needed.
