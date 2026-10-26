"""Sentiment and toxicity scores with multilingual transformer models.

Requires the optional NLP dependencies:  uv sync --extra nlp

Models (downloaded from Hugging Face on first run, ~1.5 GB total):
  sentiment  cardiffnlp/twitter-xlm-roberta-base-sentiment
             trained on tweets in 8 languages incl. French, English, Arabic,
             Italian, German, Spanish -> negative / neutral / positive
  toxicity   citizenlab/distilbert-base-multilingual-cased-toxicity
             multilingual (JIGSAW-based) -> toxic / not_toxic

The slogan itself moves both models (bare slogan: P(positive)=0.88,
P(toxic)=0.20 - the toxicity comes from "ténèbres", not "Bismillah"). So we
score text with the slogan replaced by a neutral placeholder: the scores
then describe what people say *around* the slogan. Raw-text sentiment is
kept as `sent_score_raw` for comparison. See docs/methodology.md.

Outputs (data/processed/):
  social_posts_scored   social_posts + sentiment/toxicity columns
  news_scored           news_articles + sentiment of title and of the
                        slogan's context window (if fetch-articles was run)
"""

from __future__ import annotations

import pandas as pd

from ..common import PROCESSED, load_config, log, mask_slogan

SENTIMENT_MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
TOXICITY_MODEL = "citizenlab/distilbert-base-multilingual-cased-toxicity"
# The Cardiff repo ships only a SentencePiece file, which transformers>=5 can't
# convert; it was fine-tuned from xlm-roberta-base and shares its tokenizer.
TOKENIZERS = {SENTIMENT_MODEL: "FacebookAI/xlm-roberta-base"}


def _pipeline(task: str, model: str):
    import torch
    from transformers import pipeline

    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    return pipeline(task, model=model, tokenizer=TOKENIZERS.get(model, model), device=device, truncation=True,
                    max_length=512, top_k=None)


def _score(pipe, texts: list[str], prefix: str) -> pd.DataFrame:
    texts = [t if isinstance(t, str) and t.strip() else " " for t in texts]
    out = pipe(texts, batch_size=32)
    rows = [{f"{prefix}_{d['label'].lower()}": d["score"] for d in res} for res in out]
    return pd.DataFrame(rows)


def _add_sentiment(df: pd.DataFrame, col: str, pipe, prefix: str = "sent") -> pd.DataFrame:
    scores = _score(pipe, df[col].tolist(), prefix)
    df = pd.concat([df.reset_index(drop=True), scores], axis=1)
    # Single number in [-1, 1] for plotting: P(positive) - P(negative).
    df[f"{prefix}_score"] = df[f"{prefix}_positive"] - df[f"{prefix}_negative"]
    df[f"{prefix}_label"] = scores.idxmax(axis=1).str.removeprefix(f"{prefix}_")
    return df


def run() -> None:
    sent = _pipeline("text-classification", SENTIMENT_MODEL)
    tox = _pipeline("text-classification", TOXICITY_MODEL)

    cfg = load_config()
    social = pd.read_parquet(PROCESSED / "social_posts.parquet")
    log.info("scoring %d social posts", len(social))
    social["text_masked"] = social["text"].map(lambda t: mask_slogan(t, cfg))
    social["sent_score_raw"] = _add_sentiment(social[["text"]], "text", sent)["sent_score"]
    social = _add_sentiment(social, "text_masked", sent)
    social = pd.concat([social, _score(tox, social["text_masked"].tolist(), "tox")], axis=1)
    social.to_parquet(PROCESSED / "social_posts_scored.parquet", index=False)
    social.to_csv(PROCESSED / "social_posts_scored.csv", index=False)

    news = pd.read_parquet(PROCESSED / "news_articles.parquet")
    ctx_path = PROCESSED / "news_context.parquet"
    if ctx_path.exists():
        news = news.merge(pd.read_parquet(ctx_path), on="url", how="left")
    log.info("scoring %d news articles", len(news))
    news["title_masked"] = news["title"].map(lambda t: mask_slogan(t, cfg))
    news = _add_sentiment(news, "title_masked", sent, "title_sent")
    if "first_context" in news:
        news["context_masked"] = news["first_context"].fillna("").map(lambda t: mask_slogan(t, cfg))
        news = _add_sentiment(news, "context_masked", sent, "ctx_sent")
        news.loc[news["first_context"].fillna("") == "", news.columns.str.startswith("ctx_sent")] = None
    news.to_parquet(PROCESSED / "news_scored.parquet", index=False)
    news.to_csv(PROCESSED / "news_scored.csv", index=False)
    log.info("done")
