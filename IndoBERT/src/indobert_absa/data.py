from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from .schema import (
    ASPECT_LABELS,
    ID_COLUMNS,
    REQUIRED_SOURCE_COLUMNS,
    SENTIMENT_LABELS,
    TRAINING_COLUMNS,
)
from .text import build_pair_text


def load_csv(path: str | Path) -> pd.DataFrame:
    dtype = {column: "string" for column in ID_COLUMNS}
    return pd.read_csv(path, encoding="utf-8-sig", dtype=dtype)


def ensure_required_columns(df: pd.DataFrame, columns: tuple[str, ...] = REQUIRED_SOURCE_COLUMNS) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def prepare_model_inputs(
    df: pd.DataFrame,
    comment_column: str = "Teks_Komentar",
    root_column: str = "Teks_Root",
    output_column: str = "Input_Text",
) -> pd.DataFrame:
    ensure_required_columns(df, ("Tweet_ID", "Root_Tweet_ID", comment_column))
    out = df.copy()
    if root_column not in out.columns:
        out[root_column] = ""
    out[output_column] = [
        build_pair_text(comment, root)
        for comment, root in zip(out[comment_column], out[root_column])
    ]
    return out


def validate_training_frame(df: pd.DataFrame) -> dict:
    ensure_required_columns(df, TRAINING_COLUMNS)
    duplicate_count = int(df["Tweet_ID"].duplicated().sum())
    invalid_aspects = sorted(set(df["Kategori_Utama"].dropna()) - set(ASPECT_LABELS))
    invalid_sentiments = sorted(set(df["Sentimen"].dropna()) - set(SENTIMENT_LABELS))
    empty_text_count = int(df["Teks_Komentar"].fillna("").eq("").sum())
    root_count = int(df["Root_Tweet_ID"].nunique())
    return {
        "rows": int(len(df)),
        "unique_tweet_ids": int(df["Tweet_ID"].nunique()),
        "duplicate_tweet_ids": duplicate_count,
        "root_count": root_count,
        "invalid_aspects": invalid_aspects,
        "invalid_sentiments": invalid_sentiments,
        "empty_text_count": empty_text_count,
        "is_valid": (
            duplicate_count == 0
            and not invalid_aspects
            and not invalid_sentiments
            and empty_text_count == 0
        ),
    }


def export_predictions(df: pd.DataFrame, path: str | Path) -> None:
    out = df.copy()
    for column in ID_COLUMNS:
        if column in out.columns:
            out[column] = out[column].astype("string")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_ALL)
