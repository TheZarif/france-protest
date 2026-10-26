# Initial EDA: « Bismillah c'est les ténèbres »

*First pass, data collected 26 Oct 2026. Notebook: [`notebooks/01_initial_eda.ipynb`](../notebooks/01_initial_eda.ipynb). Methods and caveats: [`docs/methodology.md`](../docs/methodology.md).*

> **Status:** news comes from Google News only (132 articles, 22 countries). **GDELT and Reddit are not in yet**: GDELT was rate-limiting our IP and the Arctic Shift Reddit archive was down. Social data covers Bluesky (1,091 posts) and Mastodon (118 posts), but not the origin platforms (Snapchat, TikTok, Instagram, X). Outlet leaning codes are a draft. Treat everything below as hypotheses to test.

## Data at a glance

| Source | Rows | Window |
|---|---|---|
| News articles (Google News, 13 editions) | 132 unique; 114 with full text, 103 of those mention the slogan in the body | 6–26 Oct |
| Bluesky posts | 1,091 (+ 3,687 repost/quote edges for the top 40 posts) | 5–26 Oct |
| Mastodon posts (hashtag timelines) | 118 | 6–26 Oct |
| Wikipedia | 5 language editions, 264 revisions, daily pageviews | 14–25 Oct |

## 1. Where it started: social media first, news a day later

![attention over time](figures/01_attention_indexed.png)

- **Earliest observable use: Bluesky, 5 Oct 07:21 UTC**, as a parody of an imagined police officer's voice. By that evening a post linking it to police infiltration of lycéen Snapchat groups had become one of the most-engaged posts in the dataset.
- **First news article: 6 Oct (*Nice-Matin*)**, an explainer on lycéen in-jokes. Coverage stayed sparse until **12–13 Oct**, when a burst of French explainers appeared (20 Minutes, regional EBRA titles, franceinfo, France 24).
- **Three attention phases:**
  1. *In-group meme* (5–10 Oct): Bluesky's first peak on 7 Oct (91 posts), before the press notices.
  2. *Domestic explainer wave* (12–17 Oct): news, the Greta Thunberg moment (13 Oct), Wikipedia articles (14 Oct). French Wikipedia pageviews peak at about 33k/day on 17 Oct, the day of the riots.
  3. *International wave* (19–22 Oct): news peaks on **21 Oct** (28 articles), on the same day as Bluesky's overall high (92 posts). English Wikipedia peaks on 19 Oct (3.6k/day).

## 2. How it travelled across countries and languages

![news by country](figures/03_news_country_timeline.png)

- **France → francophone media → English-language media → Italy → the global South.** Belgium (La DH, 10 Oct) and Switzerland (Watson, 12 Oct) followed quickly. **Turkey's state agency Anadolu covered it on 10 Oct** in its French-language service, and Turkish-language outlets followed from 19 Oct. English-language news only arrived on 15–16 Oct (newsfire.gr, Middle East Eye); the NYT published on 20 Oct. Italian coverage started on 18 Oct, right after the slogan was chanted in Bologna and Milan. Indian, Bangladeshi, Iraqi-Kurdish and Qatari outlets joined from 18 to 26 Oct.
- **58% of articles are from non-French outlets.** The slogan became an international curiosity: "what does this mean?" explainers dominate abroad.
- **Social conversation internationalised too.** The share of French-language posts fell from 89% (week of 5 Oct) to 58% (week of 19 Oct).

![language mix](figures/02_social_language.png)

- **Wikipedia documented it in an unusual set of languages**: English and French (14 Oct, created 15 minutes apart), then **Basque, Persian and Indonesian** (19–21 Oct). Persian and Indonesian suggest uptake in Muslim-majority online spaces; that's worth following up.

## 3. Coverage across the political spectrum

![leaning](figures/04_news_leaning.png)

- **French coverage is dominated by centrist and regional outlets** (36 of 56 French articles), mostly syndicated explainers. Partisan outlets covered it much less: left bloc 6 (Libération, Le Monde, HuffPost, NPA), right bloc 4 (Le Figaro, Le Point), and **far-right 4** (Valeurs actuelles, JDD, Boulevard Voltaire, Reinformation.tv).
- **Framing differs by bloc** (keyword-dictionary pass on headline + slogan context; small n, so directional only):

| frame (% of articles) | left bloc (n=18) | centre (n=57) | right bloc (n=13) |
|---|---|---|---|
| explainer "what does it mean?" | 33 | **56** | 15 |
| police infiltration | 28 | **58** | 23 |
| racism / stereotype | **11** | 5 | 0 |
| Islam / religion | 6 | 12 | **23** |
| violence / riots | 11 | 0 | **15** |
| spread abroad | **28** | 11 | 0 |

  Right-leaning outlets talk about the slogan through **Islam and violence** and almost never mention the racism critique. Left outlets emphasise **racism and international solidarity**. Centrist outlets mostly *explain* it, through the police-infiltration origin story. This is the most promising thread for the framing analysis, but it needs GDELT's wider outlet coverage and proper hand-coding.
- **Sentiment of the slogan's context paragraph** (slogan masked) is negative everywhere, most of all in right-bloc outlets (−0.64, n=8, vs −0.29 centre). This is consistent with the framing difference, but the sample is tiny.
- **Meaning drift:** by 21–22 Oct the phrase was being used *about* politicians. Matthieu Pigasse applied it to Raphaël Glucksmann ahead of the 2027 presidential race (Libération, Le Parisien). The slogan moved from protest meme to general political insult in about two weeks.

![frames](figures/05_news_frames.png)

## 4. Social propagation

- **Attention is extremely concentrated.** On Bluesky the top 1% of posts hold 32% of all engagement and the top 10% hold 81%. The median post got 2 interactions, and 26% got none. The top 20 accounts account for 54% of engagement.
- **The early amplifiers were left-leaning French accounts and public academics** (a linguist doing live "placard analysis", a historian), not news organisations. The *New York Times* account is the only institutional account in the top 20 (20 Oct).
- **Cascades:** 1,943 distinct accounts reposted at least one of the 40 most-shared posts, and **34% of them reposted more than one**, which points to a core amplifier community. Quote posts arrived a median of 8 hours after the original (90th percentile: 44 hours), so posts kept travelling for about two days.
- **Links shared alongside the slogan:** GIFs and YouTube parodies dominate, followed by Swiss outlet heidi.news, the NYT, Libération, franceinfo, France 24 and Euronews. So social media amplified **centre and centre-left coverage**; no right-leaning outlet appears among the most-linked domains.

![engagement](figures/06_engagement_tail.png)

### What people say alongside the slogan (BERTopic, 960 posts with the slogan masked)

| topic (keywords) | posts | trend |
|---|---|---|
| **Parody of the "infiltrator voice"** (wesh, brigands, binz…) | 217 | 116 → 60 → 40 per week: dominant early, then fades |
| **International/English coverage sharing** (france, french, slogan, student) | 138 | 11 → 31 → 92 per week: rises with the international wave |
| Everyday riffing / sightings (soir, vu samedi…) | 124 | stable |
| **Speculation about the police author** (flic, policier, DNRT) | 58 | stable |
| Links and videos (YouTube, bsky) | 51 | declining |
| Student movement solidarity (lycée, étudiants) | 44 | peaks week of 12 Oct |
| Smaller topics: Snapchat infiltration story, racism, left/right politics | 15–24 each | |

The topic trends support the three-phase story: **parody → movement slogan → international news object**.

### Sentiment and toxicity: one important methods note

The slogan itself skews the models. On its own it scores 88% "positive" and 20% "toxic", and the toxicity comes from *"c'est les ténèbres"*, not from *"Bismillah"*. Scoring raw posts would make the conversation look positive (+0.19). With the slogan masked, the surrounding text is mildly negative (**−0.18 Bluesky, −0.14 Mastodon**). That fits a conversation that mocks the police. Toxicity of the surrounding text is low (Bluesky median P(toxic) = 0.01). Both still need validation on a hand-coded sample.

## 5. Open questions for the next round

1. **Fill the news gap with GDELT** (`scripts/retry_when_up.sh` is running; or collect from another network). Then redo the country and leaning analysis on a much larger, less Google-curated sample, and add GDELT tone.
2. **Reddit** (r/france, r/rance, r/moi_dlvv, r/europe…): does the French Reddit "meme" culture match Bluesky's, or skew differently?
3. **The origin platforms.** Apply for the TikTok Research API / Meta Content Library, or hand-collect seed posts, to trace the 1–5 Oct jump from Snapchat to TikTok/Instagram/X.
4. **Validate outlet leanings** with a documented source and a second coder, and code the ~30 uncoded domains.
5. **Build a framing codebook** from the dictionary pass, and hand-code all ~130 articles (feasible at this size) with two coders.
6. **Far-right and international uptake:** how did far-right outlets and accounts use the phrase after the 17 Oct riots? Was it inverted ("bismillah" as an Islam signifier)? Look also at Turkish, Persian and Indonesian coverage and the Maghreb echo (Le Point: *au Maghreb, l'écho des émeutes françaises*).
7. **Meaning drift over time:** extend the topic model with `topics_over_time`, and add a usage typology (mocking police / protest chant / explainer / political insult).
8. **Re-collect weekly** while the story is live, archiving snapshots so deleted posts and changes in search rankings are captured.
