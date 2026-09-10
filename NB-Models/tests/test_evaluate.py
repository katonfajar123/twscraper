"""Tests for evaluation framework."""
import pytest
import sys
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.evaluate import (
    group_split,
    verify_no_root_leakage,
    compute_metrics,
    compute_bootstrap_ci,
    check_production_gates,
    compute_annotator_agreement,
    VALID_CATEGORIES,
)


class TestGroupSplit:
    def test_no_root_overlap(self, sample_labeled_dataset):
        config = {'split_ratios': {'train': 0.70, 'validation': 0.15, 'test': 0.15}}
        train, val, test = group_split(sample_labeled_dataset, config, seed=42)
        train_roots = set(train['Root_Tweet_ID'].unique())
        val_roots = set(val['Root_Tweet_ID'].unique())
        test_roots = set(test['Root_Tweet_ID'].unique())
        assert train_roots & val_roots == set()
        assert train_roots & test_roots == set()
        assert val_roots & test_roots == set()

    def test_split_proportions(self, sample_labeled_dataset):
        config = {'split_ratios': {'train': 0.70, 'validation': 0.15, 'test': 0.15}}
        train, val, test = group_split(sample_labeled_dataset, config, seed=42)
        total = len(train) + len(val) + len(test)
        assert total == len(sample_labeled_dataset)

    def test_deterministic(self, sample_labeled_dataset):
        config = {'split_ratios': {'train': 0.70, 'validation': 0.15, 'test': 0.15}}
        t1, v1, te1 = group_split(sample_labeled_dataset, config, seed=42)
        t2, v2, te2 = group_split(sample_labeled_dataset, config, seed=42)
        assert t1['Tweet_ID'].tolist() == t2['Tweet_ID'].tolist()


class TestLeakageDetection:
    def test_no_leakage(self):
        train = pd.DataFrame({'Root_Tweet_ID': ['A', 'A', 'B'], 'Tweet_ID': ['1', '2', '3']})
        val = pd.DataFrame({'Root_Tweet_ID': ['C'], 'Tweet_ID': ['4']})
        test = pd.DataFrame({'Root_Tweet_ID': ['D'], 'Tweet_ID': ['5']})
        result = verify_no_root_leakage(train, val, test)
        assert result['leakage_found'] is False

    def test_detects_leakage(self):
        train = pd.DataFrame({'Root_Tweet_ID': ['A', 'B'], 'Tweet_ID': ['1', '2']})
        val = pd.DataFrame({'Root_Tweet_ID': ['A'], 'Tweet_ID': ['3']})  # Leaking root A
        test = pd.DataFrame({'Root_Tweet_ID': ['C'], 'Tweet_ID': ['4']})
        result = verify_no_root_leakage(train, val, test)
        assert result['leakage_found'] is True
        assert 'A' in result['train_val_leak']


class TestMetricsComputation:
    def test_perfect_predictions(self):
        y_true = ['Mutu_Gizi', 'Tata_Kelola', 'Distribusi']
        y_pred = ['Mutu_Gizi', 'Tata_Kelola', 'Distribusi']
        metrics = compute_metrics(y_true, y_pred)
        assert metrics['macro_f1'] == 1.0
        assert metrics['balanced_accuracy'] == 1.0

    def test_confusion_matrix_shape(self):
        y_true = ['Mutu_Gizi', 'Tata_Kelola', 'Distribusi']
        y_pred = ['Mutu_Gizi', 'Mutu_Gizi', 'Distribusi']
        metrics = compute_metrics(y_true, y_pred)
        assert len(metrics['confusion_matrix']) == 3
        assert len(metrics['confusion_matrix'][0]) == 3


class TestBootstrapCI:
    def test_bootstrap_uses_root_clusters(self):
        y_true = np.array(['Mutu_Gizi'] * 10 + ['Tata_Kelola'] * 10)
        y_pred = np.array(['Mutu_Gizi'] * 10 + ['Tata_Kelola'] * 10)
        root_ids = np.array(['R1'] * 5 + ['R2'] * 5 + ['R3'] * 5 + ['R4'] * 5)
        result = compute_bootstrap_ci(y_true, y_pred, root_ids, n_bootstrap=100)
        assert 'ci_lower' in result
        assert 'ci_upper' in result
        assert result['ci_lower'] <= result['ci_upper']


class TestProductionGates:
    def test_all_gates_not_evaluated_when_empty(self):
        gates = check_production_gates({}, {})
        for gate, status in gates.items():
            assert status == 'not_evaluated'

    def test_gates_fail_with_low_metrics(self):
        metrics = {
            'macro_f1': 0.50,
            'balanced_accuracy': 0.50,
            'per_class': {
                'Mutu_Gizi': {'recall': 0.30},
                'Tata_Kelola': {'recall': 0.40},
                'Distribusi': {'recall': 0.50},
            },
        }
        gates = check_production_gates(metrics, {})
        assert gates['macro_f1'] == 'fail'
        assert gates['balanced_accuracy'] == 'fail'
        assert gates['class_recall'] == 'fail'


class TestAnnotatorAgreement:
    def test_perfect_agreement(self):
        labels = ['Mutu_Gizi', 'Tata_Kelola', 'Distribusi']
        result = compute_annotator_agreement(labels, labels)
        assert result['kappa'] == 1.0
        assert result['agreement_rate'] == 1.0
