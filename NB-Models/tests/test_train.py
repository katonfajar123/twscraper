"""Tests for training framework."""
import pytest
import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.train import (
    check_ground_truth,
    build_experiment_registry,
    build_pipeline,
    VALID_CATEGORIES,
    RootGroupSplitter,
)


class TestGroundTruthCheck:
    def test_fails_when_column_missing(self, sample_unlabeled_dataset):
        assert check_ground_truth(sample_unlabeled_dataset) is False

    def test_fails_when_column_empty(self, sample_dataset):
        df = sample_dataset.copy()
        df['Kategori_Utama'] = ''
        assert check_ground_truth(df) is False

    def test_passes_with_valid_labels(self, sample_labeled_dataset):
        assert check_ground_truth(sample_labeled_dataset) is True

    def test_fails_with_invalid_labels(self, sample_dataset):
        df = sample_dataset.copy()
        df['Kategori_Utama'] = 'InvalidCategory'
        assert check_ground_truth(df) is False


class TestExperimentRegistry:
    def test_all_experiments_defined(self):
        registry = build_experiment_registry()
        expected = ['E0', 'E1', 'E2', 'E3', 'E4', 'E5', 'E6', 'Audit']
        for exp_id in expected:
            assert exp_id in registry, f"Missing experiment: {exp_id}"

    def test_has_descriptions(self):
        registry = build_experiment_registry()
        for exp_id, exp in registry.items():
            assert 'description' in exp, f"{exp_id} missing description"


class TestPipelineBuilds:
    @pytest.mark.parametrize('exp_id', ['E0', 'E2', 'E3', 'E4', 'E5', 'Audit'])
    def test_pipeline_constructs(self, exp_id):
        """Each experiment pipeline can be constructed without error."""
        pipeline = build_pipeline(exp_id, alpha=1.0, config={})
        assert pipeline is not None

    def test_unknown_experiment_raises(self):
        with pytest.raises(ValueError):
            build_pipeline('UNKNOWN', alpha=1.0, config={})


class TestRootGroupSplitter:
    def test_splitter_creates_folds(self, sample_labeled_dataset):
        splitter = RootGroupSplitter(n_splits=2)
        groups = sample_labeled_dataset['Root_Tweet_ID']
        X = sample_labeled_dataset[['Teks_Komentar']]
        y = sample_labeled_dataset['Kategori_Utama']
        folds = list(splitter.split(X, y, groups))
        assert len(folds) == 2

    def test_splitter_requires_groups(self, sample_labeled_dataset):
        splitter = RootGroupSplitter(n_splits=2)
        X = sample_labeled_dataset[['Teks_Komentar']]
        with pytest.raises(ValueError):
            list(splitter.split(X))
