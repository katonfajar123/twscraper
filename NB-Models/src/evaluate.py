import numpy as np
import pandas as pd
import logging
import json
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from sklearn.metrics import (
    precision_recall_fscore_support,
    balanced_accuracy_score,
    confusion_matrix,
    cohen_kappa_score,
    classification_report
)
from sklearn.model_selection import GroupShuffleSplit

VALID_CATEGORIES = ['Mutu_Gizi', 'Tata_Kelola', 'Distribusi']
logger = logging.getLogger(__name__)

def group_split(df: pd.DataFrame, config: dict, seed: int) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split by Root_Tweet_ID groups:
    - train: 70%, validation: 15%, test: 15%
    - No root overlap between splits
    - Deterministic seed
    """
    if 'Root_Tweet_ID' not in df.columns:
        raise ValueError("Column 'Root_Tweet_ID' must be present in DataFrame")

    gss_test = GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=seed)
    train_idx, temp_idx = next(gss_test.split(df, groups=df['Root_Tweet_ID']))
    
    train_df = df.iloc[train_idx].copy()
    temp_df = df.iloc[temp_idx].copy()
    
    # Split temp_df into val (50%) and test (50%), meaning 15% each of the original
    gss_val = GroupShuffleSplit(n_splits=1, test_size=0.50, random_state=seed)
    val_idx, test_idx = next(gss_val.split(temp_df, groups=temp_df['Root_Tweet_ID']))
    
    val_df = temp_df.iloc[val_idx].copy()
    test_df = temp_df.iloc[test_idx].copy()
    
    return train_df, val_df, test_df

def verify_no_root_leakage(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> dict:
    """
    Check:
    - train_roots ∩ validation_roots = ∅
    - train_roots ∩ test_roots = ∅  
    - validation_roots ∩ test_roots = ∅
    Return dict with results and any leaking root IDs
    """
    train_roots = set(train_df['Root_Tweet_ID'].unique())
    val_roots = set(val_df['Root_Tweet_ID'].unique())
    test_roots = set(test_df['Root_Tweet_ID'].unique())
    
    train_val_leak = train_roots.intersection(val_roots)
    train_test_leak = train_roots.intersection(test_roots)
    val_test_leak = val_roots.intersection(test_roots)
    
    leakage_found = bool(train_val_leak or train_test_leak or val_test_leak)
    
    return {
        'leakage_found': leakage_found,
        'train_val_leak': list(train_val_leak),
        'train_test_leak': list(train_test_leak),
        'val_test_leak': list(val_test_leak)
    }

def compute_metrics(y_true: List[str], y_pred: List[str], labels: List[str] = VALID_CATEGORIES) -> dict:
    """
    Compute classification metrics.
    """
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    
    macro_precision = float(np.mean(precision))
    macro_recall = float(np.mean(recall))
    macro_f1 = float(np.mean(f1))
    balanced_acc = float(balanced_accuracy_score(y_true, y_pred))
    
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    cm_normalized = confusion_matrix(y_true, y_pred, labels=labels, normalize='true')
    
    cr_text = classification_report(y_true, y_pred, labels=labels, zero_division=0)
    
    per_class = {}
    for i, label in enumerate(labels):
        per_class[label] = {
            'precision': float(precision[i]),
            'recall': float(recall[i]),
            'f1': float(f1[i]),
            'support': int(support[i])
        }
        
    return {
        'macro_precision': macro_precision,
        'macro_recall': macro_recall,
        'macro_f1': macro_f1,
        'balanced_accuracy': balanced_acc,
        'per_class': per_class,
        'confusion_matrix': cm.tolist(),
        'confusion_matrix_normalized': cm_normalized.tolist(),
        'classification_report_text': cr_text
    }

def compute_bootstrap_ci(y_true: np.ndarray, y_pred: np.ndarray, root_ids: np.ndarray, n_bootstrap: int = 1000, seed: int = 42, confidence: float = 0.95) -> dict:
    """
    Cluster bootstrap CI using Root_Tweet_ID as cluster unit.
    """
    rng = np.random.default_rng(seed)
    unique_roots = np.unique(root_ids)
    n_roots = len(unique_roots)
    
    df = pd.DataFrame({'y_true': y_true, 'y_pred': y_pred, 'root_id': root_ids})
    
    scores = []
    for _ in range(n_bootstrap):
        sampled_roots = rng.choice(unique_roots, size=n_roots, replace=True)
        
        grouped = df.groupby('root_id')
        
        sample_dfs = []
        for r in sampled_roots:
            if r in grouped.groups:
                sample_dfs.append(grouped.get_group(r))
                
        if not sample_dfs:
            continue
            
        sample_df = pd.concat(sample_dfs)
        _, _, f1, _ = precision_recall_fscore_support(
            sample_df['y_true'], sample_df['y_pred'], labels=VALID_CATEGORIES, average='macro', zero_division=0
        )
        scores.append(f1)
        
    if not scores:
        return {}
        
    scores = np.array(scores)
    mean_score = np.mean(scores)
    std_score = np.std(scores)
    lower_percentile = (1.0 - confidence) / 2.0 * 100
    upper_percentile = (1.0 + confidence) / 2.0 * 100
    ci_lower = np.percentile(scores, lower_percentile)
    ci_upper = np.percentile(scores, upper_percentile)
    
    return {
        'mean': float(mean_score),
        'std': float(std_score),
        'ci_lower': float(ci_lower),
        'ci_upper': float(ci_upper)
    }

def compute_annotator_agreement(labels_a1: List[str], labels_a2: List[str]) -> dict:
    """
    Cohen's kappa between two annotators.
    """
    kappa = cohen_kappa_score(labels_a1, labels_a2)
    labels_a1 = np.array(labels_a1)
    labels_a2 = np.array(labels_a2)
    agreement = np.mean(labels_a1 == labels_a2)
    
    cm = confusion_matrix(labels_a1, labels_a2, labels=VALID_CATEGORIES)
    
    return {
        'kappa': float(kappa),
        'agreement_rate': float(agreement),
        'confusion_matrix': cm.tolist()
    }

def compute_per_root_metrics(y_true: np.ndarray, y_pred: np.ndarray, root_ids: np.ndarray) -> dict:
    """
    Compute metrics per root, then macro-average across roots.
    """
    df = pd.DataFrame({'y_true': y_true, 'y_pred': y_pred, 'root_id': root_ids})
    
    root_metrics = {}
    macro_f1s = []
    
    for root_id, group in df.groupby('root_id'):
        _, _, f1, _ = precision_recall_fscore_support(
            group['y_true'], group['y_pred'], labels=VALID_CATEGORIES, average='macro', zero_division=0
        )
        macro_f1s.append(f1)
        root_metrics[str(root_id)] = {'macro_f1': float(f1), 'support': len(group)}
        
    return {
        'per_root': root_metrics,
        'aggregate_macro_f1_across_roots': float(np.mean(macro_f1s)) if macro_f1s else 0.0
    }

def check_production_gates(metrics: dict, config: dict) -> dict:
    """
    Check against gates:
    - macro_f1 >= 0.85
    - each class recall >= 0.80
    - balanced_accuracy >= 0.85  
    - val_test_gap <= 0.05
    - zero root leakage
    Return dict with each gate result (pass/fail/not_evaluated)
    """
    gates = {
        'macro_f1': 'not_evaluated',
        'class_recall': 'not_evaluated',
        'balanced_accuracy': 'not_evaluated',
        'val_test_gap': 'not_evaluated',
        'zero_root_leakage': 'not_evaluated'
    }
    
    if not metrics:
        return gates
        
    macro_f1 = metrics.get('macro_f1')
    if macro_f1 is not None:
        gates['macro_f1'] = 'pass' if macro_f1 >= 0.85 else 'fail'
        
    per_class = metrics.get('per_class', {})
    if per_class:
        all_passed = True
        for label, cls_metrics in per_class.items():
            if cls_metrics['recall'] < 0.80:
                all_passed = False
                break
        gates['class_recall'] = 'pass' if all_passed else 'fail'
        
    bal_acc = metrics.get('balanced_accuracy')
    if bal_acc is not None:
        gates['balanced_accuracy'] = 'pass' if bal_acc >= 0.85 else 'fail'
        
    val_macro_f1 = metrics.get('val_macro_f1')
    test_macro_f1 = metrics.get('test_macro_f1')
    if val_macro_f1 is not None and test_macro_f1 is not None:
        gap = abs(val_macro_f1 - test_macro_f1)
        gates['val_test_gap'] = 'pass' if gap <= 0.05 else 'fail'
        
    leakage = metrics.get('leakage_found')
    if leakage is not None:
        gates['zero_root_leakage'] = 'pass' if not leakage else 'fail'
        
    return gates

def save_evaluation_report(results: dict, output_path: Path) -> None:
    """
    Save evaluation results as JSON.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
