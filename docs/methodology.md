# Methodology

How the data is gathered, what each derived variable means, and the limits to keep in mind. Update this whenever a method changes.

## 1. Research questions

1. **Origin and diffusion.** When and where does the slogan first appear on each observable platform, and in what order do platforms, countries and languages pick it up?
2. **News framing across the political spectrum.** Which outlets cover it, how do they frame it (meme, police infiltration, racism, Islam, violence…), and does framing vary with outlet leaning and country?
3. **Social propagation.** Who amplifies it, how concentrated is attention, how do posts cascade, and which links travel with it?
4. **Meaning drift.** Does use shift from in-group mockery, to a protest slogan, to an international curiosity, to a political insult?

## 2. Matching the slogan

The phrase is written many ways (comma or none, ’ or ', accents or none, "c'est" dropped, hashtag form), and foreign coverage often **translates** it: in English *"Bismillah / In the name of God, it's (the) darkness"*, in Arabic *"بسم الله، إنه الظلام"* or *"بسم الله، إنها الظلمات"*. All variants live in [`config/queries.yaml`](../config/queries.yaml):

- **Search queries** are deliberately broad (e.g. `bismillah ténèbres`), plus English and Arabic translations for Google News and Bluesky.
- **Matching**: after collection a post is kept if its text contains both `bismil…` and `ténèbre…` (accent-insensitive), or a full translated rendering (`keyword_match`). The stricter `phrase_exact` flag marks the full slogan in sequence, in French or translation (regex `match_regex`, which makes "c'est" optional). The same regex drives the headline/body flags, context windows and masking.

## 3. Sources and sampling

| Source | Sampling logic | What it represents |
|---|---|---|
| Google News RSS | search per edition (23 country × language pairs, incl. Arabic, Indonesian, Portuguese, Dutch, Bengali); ≤100 results per query, sliced by date if capped | Google's *ranked* selection, not a census. It is biased toward outlets Google indexes and ranks well |
| GDELT DOC 2.0 | keyword queries; daily volume first, then articles per active day (6-h slices if the 250 cap is hit). Responses are cached per request so collection can resume across runs. **GDELT searches the English machine translation of non-English articles**, so French-keyword queries only match English articles quoting the slogan; the English query `bismillah darkness` reaches translated coverage | GDELT's monitored universe of online news in 65 languages. Its broadest view of non-Western and non-English media |
| Bluesky | public search by day; full windows split recursively (unauthenticated search refuses cursors) | close to all public posts containing the search terms |
| Mastodon | public hashtag timelines on 5 instances | **only hashtagged posts** visible to those instances, so it undercounts |
| Lemmy | public search on 5 federated instances (incl. francophone jlai.lu), posts and comments | the federated Reddit alternative; small, tech-leaning |
| Reddit (Arctic Shift) | full-text post and comment search swept across listed subreddits (Arctic Shift no longer allows site-wide text search); site-wide search for posts linking to any of our news articles, whose subreddits then get the same sweep; full threads under every post found | listed + discovered subreddits only. Subreddits where nobody shared one of our articles and that aren't on the list are missed |
| Wikipedia | langlinks from the English article; pageviews (users only); revision history | public curiosity, and the order in which language communities documented it |

The **study window** starts 15 Sept 2026 (before the Créteil blockades). Timestamps are UTC in raw data. `date` columns are in **Europe/Paris** time.

## 4. Outlet coding (`config/outlets.csv`)

Each news domain is matched to an outlet by longest domain suffix (`fr.euronews.com` → `euronews.com`).

| Column | Values |
|---|---|
| `country` | ISO-2 country of the outlet's base, not of its audience |
| `media_type` | national daily, regional daily, TV news, public broadcaster, digital native, wire, magazine, party outlet, community media, platform… |
| `leaning` | 7-point: `far-left`, `left`, `center-left`, `center`, `center-right`, `right`, `far-right`; `n/a` = wires, state media, platforms, satire; blank = **uncoded** |
| `ownership_type` | private, public, state (foreign state-funded), cooperative, independent, party-affiliated |
| `owner_group` | parent group where well documented (e.g. Bolloré, LVMH, Dassault). Ownership concentration matters in French media |

> ⚠️ **The leaning codes are a first draft** made to get the pipeline running. Before any inference they need a documented, inter-coder-checked procedure. Suggested references: Le Monde diplomatique / Acrimed's *Médias français : qui possède quoi* (ownership); Arcom pluralism reports; academic studies of French media positioning (e.g. Cagé et al.); AllSides / Media Bias Fact Check for English-language outlets (use with caution). Record disagreements in `notes`. Codes for outlets whose positioning is debated (CNews, JDD, Marianne) are flagged there.

**Blocs** for small-sample comparisons: left bloc = far-left + left + center-left; right bloc = center-right + right + far-right; centre; and n/a-or-uncoded.

## 5. Text measures

### Context windows (`fetch-articles`)
Google News links are decoded to publisher URLs, and pages are downloaded and cleaned with trafilatura. For each mention of the slogan we keep ±300 characters (`first_context`, `all_contexts`). This is the unit for framing and context sentiment: it captures *how the slogan is used*, not the article's general topic.

### Framing (notebook § 3c)
Keyword dictionaries (in the notebook, `FRAMES`) applied to headline + context window, multi-label. These are **transparent and crude**: high recall, imperfect precision, and French/English-centric. They are meant to direct qualitative reading and to seed a proper codebook, with hand-coding of a sample and agreement statistics.

### Sentiment
`cardiffnlp/twitter-xlm-roberta-base-sentiment` (XLM-R fine-tuned on tweets in 8 languages including French, English, Arabic, Italian, German and Spanish). Score = P(positive) − P(negative) ∈ [-1, 1].

### Toxicity
`citizenlab/distilbert-base-multilingual-cased-toxicity` (multilingual, Jigsaw-trained). Output is P(toxic).

### The slogan-masking rule (important)
The slogan itself moves both models. On its own it scores **P(positive) = 0.88** and **P(toxic) = 0.20**. Probing shows the toxicity comes from *"c'est les ténèbres"* (0.22), not *"Bismillah"* (0.08). So the identity-term bias we worried about is not the main driver, but the slogan's own words still dominate short posts. All primary scores are therefore computed on text with the slogan replaced by `«slogan»` (`text_masked`, `title_masked`, `context_masked`), so they describe **what is said around the slogan**. Raw-text sentiment is kept as `sent_score_raw`. Masking flips mean Bluesky sentiment from +0.19 (raw) to −0.18 (masked).

Model scores need validation against a hand-coded sample (suggested: 200 posts and 50 article contexts, stratified by language) before they are reported.

### Topic modelling
BERTopic with `paraphrase-multilingual-MiniLM-L12-v2` embeddings, UMAP with a fixed seed, HDBSCAN (`min_topic_size=12`). Input = social posts with the slogan masked and links removed, keeping posts with ≥4 remaining words and dropping exact duplicates (972 of 1,268). Without de-duplication, copy-pasted shares form one dense cluster and HDBSCAN lumps everything else into a single topic. Topic labels are c-TF-IDF keywords with French and English stop words and the slogan's own words removed. Topics are **exploratory**: check stability across seeds and `min_topic_size` before interpreting.

## 6. Known gaps and biases

- **The origin platforms are missing.** The slogan was born on Snapchat and spread mostly on TikTok, Instagram and X, none of which we can search freely. Options: TikTok Research API (academic application), Meta Content Library (via ICPSR/SOMAR), X API (paid), Junkipedia, or manual collection of seed posts. Our "first appearances" are **first appearances on observable platforms**.
- **Bluesky, Mastodon and Lemmy skew left, educated and francophone-urban** compared with the general public. Their sentiment and framing are not "public opinion".
- **Google News is a ranked sample.** Querying 23 editions brings in non-French outlets (58% of articles), but coverage of small, far-right and non-Western outlets is still thin. GDELT should broaden this once collected.
- **Paywalls and bot-blocking**: 17 of 203 articles (e.g. Le Parisien, Libération, Ouest-France, NYT) could not be fetched. Their framing is coded from headlines only, and they are kept as on-topic because they can't be ruled out.
- **Off-topic news**: Google News also returns items that never mention the slogan. `news_scored.on_topic` is true when the headline mentions the slogan or "bismillah" in some form (`mention_regex`), or the fetched body contains the slogan itself (`match_regex`); 13 of 203 are excluded. Body mentions of a bare "bismillah" don't count, since in Arabic and Persian texts it is often just a religious formula. Translations the regex doesn't know (e.g. one Arabic article's *"الظلام يعم المكان"*) can be lost.
- **Translations vary by outlet** (see § 2), so keyword tracking across languages is incomplete. Add new renderings to `match_regex` as they turn up.
- **Google News timestamps** are often day-level (shown as 07:00 UTC), so ordering within a day is unreliable.
- **Search results drift.** Platforms delete posts and re-rank results, so collection runs at different times differ. Archive raw snapshots.

## 7. Ethics

Public posts only; no logins or private groups. Usernames stay in local data and are not published except for public figures and institutional accounts. Quotes from private individuals in outputs should be paraphrased. Article texts are kept locally for analysis and not redistributed.
