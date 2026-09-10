from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from .data import prepare_model_inputs
from .schema import ASPECT_LABELS, SENTIMENT_LABELS


@dataclass(frozen=True)
class PredictorConfig:
    aspect_model_path: str | Path
    sentiment_model_path: str | Path | None = None
    model_version: str = "indobert-absa-0.1.0"
    max_length: int = 192
    confidence_threshold: float = 0.60


class IndoBERTABSAPredictor:
    def __init__(self, config: PredictorConfig):
        self.config = config
        self.tokenizer = None
        self.aspect_model = None
        self.sentiment_model = None

    def load(self) -> None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(self.config.aspect_model_path)
        self.aspect_model = AutoModelForSequenceClassification.from_pretrained(
            self.config.aspect_model_path
        )
        if self.config.sentiment_model_path:
            self.sentiment_model = AutoModelForSequenceClassification.from_pretrained(
                self.config.sentiment_model_path
            )

    def _predict_one(self, text: str, model, labels: tuple[str, ...]) -> tuple[str, float]:
        import torch

        if self.tokenizer is None:
            raise ValueError("Tokenizer is not loaded")
        encoded = self.tokenizer(
            text,
            truncation=True,
            max_length=self.config.max_length,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = model(**encoded).logits
            probs = torch.softmax(logits, dim=-1)[0]
        index = int(torch.argmax(probs).item())
        label = labels[index] if index < len(labels) else str(index)
        return label, float(probs[index].item())

    def predict_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.aspect_model is None:
            raise ValueError("Aspect model is not loaded")

        out = prepare_model_inputs(df)
        aspects: list[str] = []
        aspect_confidences: list[float] = []
        sentiments: list[str] = []
        sentiment_confidences: list[float | None] = []
        statuses: list[str] = []

        for text in out["Input_Text"].tolist():
            aspect, aspect_confidence = self._predict_one(text, self.aspect_model, ASPECT_LABELS)
            aspects.append(aspect)
            aspect_confidences.append(aspect_confidence)

            if self.sentiment_model is not None:
                sentiment, sentiment_confidence = self._predict_one(
                    text, self.sentiment_model, SENTIMENT_LABELS
                )
                sentiments.append(sentiment)
                sentiment_confidences.append(sentiment_confidence)
            else:
                sentiments.append("")
                sentiment_confidences.append(None)

            statuses.append(
                "ACCEPTED"
                if aspect_confidence >= self.config.confidence_threshold
                else "NEEDS_REVIEW"
            )

        out["Kategori_Utama"] = aspects
        out["Sentimen"] = sentiments
        out["Confidence"] = aspect_confidences
        out["Sentiment_Confidence"] = sentiment_confidences
        out["Prediction_Status"] = statuses
        out["Model_Version"] = self.config.model_version
        out["Predicted_At"] = datetime.now().isoformat(timespec="seconds")
        return out
