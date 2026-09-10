"""Tests for prediction module."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.predict import AspectPredictor, VALID_CATEGORIES, export_predictions
import pandas as pd


class TestPredictionStatus:
    def test_accepted_high_confidence(self):
        config = {'confidence_threshold': 0.6, 'margin_threshold': 0.15}
        predictor = AspectPredictor(Path('dummy'), config)
        assert predictor.determine_status(0.9, 0.3) == 'ACCEPTED'

    def test_needs_review_low_confidence(self):
        config = {'confidence_threshold': 0.6, 'margin_threshold': 0.15}
        predictor = AspectPredictor(Path('dummy'), config)
        assert predictor.determine_status(0.4, 0.3) == 'NEEDS_REVIEW'

    def test_needs_review_low_margin(self):
        config = {'confidence_threshold': 0.6, 'margin_threshold': 0.15}
        predictor = AspectPredictor(Path('dummy'), config)
        assert predictor.determine_status(0.7, 0.05) == 'NEEDS_REVIEW'


class TestNeedsReviewNotCategory:
    def test_needs_review_not_in_valid_categories(self):
        assert 'NEEDS_REVIEW' not in VALID_CATEGORIES

    def test_accepted_not_in_valid_categories(self):
        assert 'ACCEPTED' not in VALID_CATEGORIES

    def test_valid_categories_are_aspects(self):
        assert set(VALID_CATEGORIES) == {'Mutu_Gizi', 'Tata_Kelola', 'Distribusi'}


class TestOutputCSV:
    def test_encoding_utf8sig(self, tmp_path):
        df = pd.DataFrame({
            'Tweet_ID': ['123456789'],
            'Teks_Komentar': ['test emoji 🍚'],
            'Kategori_Utama': ['Mutu_Gizi'],
        })
        output = tmp_path / 'predictions.csv'
        export_predictions(df, output)
        with open(output, 'rb') as f:
            bom = f.read(3)
        assert bom == b'\xef\xbb\xbf'

    def test_ids_string_in_output(self, tmp_path):
        df = pd.DataFrame({
            'Tweet_ID': ['1234567890123456789'],
            'Teks_Komentar': ['test'],
        })
        output = tmp_path / 'predictions.csv'
        export_predictions(df, output)
        loaded = pd.read_csv(output, encoding='utf-8-sig', dtype={'Tweet_ID': str})
        assert loaded['Tweet_ID'].iloc[0] == '1234567890123456789'
