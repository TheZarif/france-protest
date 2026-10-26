# Data dictionary

Tables in `data/processed/`, each as `.parquet` and `.csv`. Built by `uv run tenebres process` unless noted otherwise.

## `news_articles`: one row per unique news article

Google News and GDELT results are merged. Two rows with the same domain and the same normalised title count as one article.

| Column | Meaning |
|---|---|
| `date` | publication date, Europe/Paris |
| `published_at` | publication time, UTC (Google News is often day-level: 07:00) |
| `title` | headline (publisher suffix removed) |
| `outlet`, `domain` | outlet name and web domain |
| `country` | outlet country (ISO-2), from outlet coding → GDELT source country → domain TLD; `unknown` if none apply |
| `language` | article language (GDELT), or the edition language it was found in (Google News) |
| `leaning` | political leaning from `config/outlets.csv` (see methodology §4); `n/a` = non-partisan or wire; `uncoded` = not yet in the table |
| `media_type`, `ownership_type`, `owner_group` | from `config/outlets.csv` |
| `found_in` | `gdelt`, `google_news`, or both (`;`-separated) |
| `gn_editions` | Google News editions that returned it, e.g. `FR:fr;BE:fr` (how widely Google surfaced it) |
| `title_has_phrase` | headline contains the slogan |
| `url` | GDELT URL, or Google News redirect URL (resolved in `news_context.resolved_url`) |

## `news_context`: article text measures (`tenebres fetch-articles`)

| Column | Meaning |
|---|---|
| `url` | join key to `news_articles.url` |
| `resolved_url` | publisher URL after decoding Google redirects |
| `text_chars` | length of extracted main text |
| `body_has_phrase` | body contains the slogan |
| `n_mentions` | number of mentions |
| `first_context`, `all_contexts` | ±300-character windows around each mention (`|||`-separated) |

## `news_scored`: `news_articles` + `news_context` + model scores (`tenebres enrich`)

| Column | Meaning |
|---|---|
| `title_masked`, `context_masked` | text with the slogan replaced by `«slogan»` (model input) |
| `title_sent_*`, `ctx_sent_*` | `negative`/`neutral`/`positive` probabilities, `score` = pos − neg, `label` = argmax |

## `social_posts`: one row per post or comment mentioning the slogan

Covers Bluesky, Reddit and Mastodon. A row is kept if it contains both "bismil…" and "ténèbre…" (accent-insensitive) and was posted after the study-window start.

| Column | Meaning |
|---|---|
| `platform` | `bluesky`, `reddit`, `mastodon` |
| `date`, `created_at` | Europe/Paris date; UTC timestamp |
| `author`, `author_name` | handle / display name (**personal data: do not publish**) |
| `author_followers` | follower count at collection time (Bluesky, Mastodon) |
| `community` | subreddit (Reddit), home instance (Mastodon) |
| `lang` | language tags declared by the post (Bluesky, Mastodon) |
| `text` | post text (Reddit posts: title + body) |
| `phrase_exact` | full slogan in sequence (vs. both keywords anywhere) |
| `likes`, `reposts`, `replies`, `quotes` | counts at collection time (Reddit: `likes` = score) |
| `engagement` | sum of the four |
| `is_reply`, `parent_id` | reply flag and parent post id |
| `quoted_id` | URI of the quoted post (Bluesky quote posts) |
| `link_domain` | domain of an attached external link |
| `post_id`, `url` | platform id; public URL |

## `social_posts_scored` (`tenebres enrich`)

`social_posts` plus:

| Column | Meaning |
|---|---|
| `text_masked` | text with the slogan replaced by `«slogan»` |
| `sent_negative`, `sent_neutral`, `sent_positive`, `sent_score`, `sent_label` | sentiment of the masked text |
| `sent_score_raw` | sentiment score on the raw text (for comparison) |
| `tox_toxic`, `tox_not_toxic` | toxicity probabilities of the masked text |

## `social_topics` (written by notebook 01)

`post_id`, `platform`, `date`, `topic` (BERTopic id, −1 = outlier), `Name` (keyword label).

## `bluesky_edges`: diffusion of the 40 most-shared Bluesky posts

| Column | Meaning |
|---|---|
| `type` | `quote` or `repost` |
| `source` | quoting post URI (quote) or reposting account DID (repost) |
| `source_author` | handle of the quoting or reposting account |
| `target` | URI of the original post (join to `social_posts.post_id`) |
| `created_at` | quote time (reposts have no timestamp in the public API) |

## `gdelt_timelines`

| Column | Meaning |
|---|---|
| `query` | GDELT query string |
| `mode` | `timelinevolraw` (article counts), `timelinetone` (average tone), `timelinesourcecountry`, `timelinelang` |
| `series` | series name (e.g. a country or language) |
| `date` | `YYYYMMDDTHHMMSSZ` |
| `value`, `norm` | value; total monitored articles that period (for normalising) |

## `wiki_pageviews`, `wiki_revisions`

| Table | Columns |
|---|---|
| `wiki_pageviews` | `lang`, `title`, `date` (YYYYMMDD), `views` (human users, all access methods) |
| `wiki_revisions` | `lang`, `title`, `timestamp`, `user`, `size`, `comment`: full edit history; the first row per language is the article's creation |
