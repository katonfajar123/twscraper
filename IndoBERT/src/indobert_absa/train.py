from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from .data import prepare_model_inputs, validate_training_frame
from .schema import ASPECT_LABELS, SENTIMENT_LABELS


@dataclass(frozen=True)
class TrainingConfig:
    base_model_name: str = "indobenchmark/indobert-base-p1"
    text_column: str = "Input_Text"
    aspect_column: str = "Kategori_Utama"
    sentiment_column: str = "Sentimen"
    group_column: str = "Root_Tweet_ID"
    seed: int = 42
    validation_size: float = 0.15
    test_size: float = 0.15


def check_training_readiness(df: pd.DataFrame) -> dict:
    audit = validate_training_frame(df)
    audit["has_human_labels"] = audit["is_valid"] and audit["rows"] > 0
    return audit


def make_label_maps(labels: tuple[str, ...]) -> tuple[dict[str, int], dict[int, str]]:
    label2id = {label: index for index, label in enumerate(labels)}
    id2label = {index: label for label, index in label2id.items()}
    return label2id, id2label


def split_by_root(df: pd.DataFrame, config: TrainingConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if config.group_column not in df.columns:
        raise ValueError(f"Missing group column: {config.group_column}")

    temp_size = config.validation_size + config.test_size
    train_splitter = GroupShuffleSplit(n_splits=1, test_size=temp_size, random_state=config.seed)
    train_idx, temp_idx = next(train_splitter.split(df, groups=df[config.group_column]))
    train_df = df.iloc[train_idx].copy()
    temp_df = df.iloc[temp_idx].copy()

    relative_test_size = config.test_size / temp_size
    val_splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=relative_test_size,
        random_state=config.seed,
    )
    val_idx, test_idx = next(val_splitter.split(temp_df, groups=temp_df[config.group_column]))
    return train_df, temp_df.iloc[val_idx].copy(), temp_df.iloc[test_idx].copy()


def prepare_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    ready = check_training_readiness(df)
    if not ready["is_valid"]:
        raise ValueError(f"Training frame is not valid: {ready}")
    return prepare_model_inputs(df)


ASPECT_LABEL2ID, ASPECT_ID2LABEL = make_label_maps(ASPECT_LABELS)
SENTIMENT_LABEL2ID, SENTIMENT_ID2LABEL = make_label_maps(SENTIMENT_LABELS)
