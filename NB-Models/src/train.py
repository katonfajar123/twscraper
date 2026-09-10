import logging
import sys
import yaml
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional
from sklearn.dummy import DummyClassifier
from sklearn.naive_bayes import BernoulliNB, MultinomialNB, ComplementNB
from sklearn.svm import LinearSVC
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.model_selection import GroupKFold, cross_validate
from sklearn.base import BaseEstimator, TransformerMixin
import joblib

logger = logging.getLogger(__name__)

VALID_CATEGORIES = ['Mutu_Gizi', 'Tata_Kelola', 'Distribusi']

def check_ground_truth(df: pd.DataFrame, label_column: str = 'Kategori_Utama') -> bool:
    """
    Check if ground truth labels exist:
    - label_column must exist
    - Must have non-empty values
    - Values must be in VALID_CATEGORIES
    """
    if label_column not in df.columns:
        print(f"GROUND TRUTH BELUM TERSEDIA. Kolom {label_column} tidak ada. Jalankan anotasi manusia terlebih dahulu.")
        return False
        
    # Check for non-empty, non-null values
    valid_mask = df[label_column].notna() & (df[label_column] != "")
    if not valid_mask.any():
        print(f"GROUND TRUTH BELUM TERSEDIA. Kolom {label_column} kosong. Jalankan anotasi manusia terlebih dahulu.")
        return False
        
    # Check if values are in VALID_CATEGORIES
    unique_labels = df.loc[valid_mask, label_column].unique()
    invalid_labels = [label for label in unique_labels if label not in VALID_CATEGORIES and label not in ('UNCLEAR', 'NEEDS_REVIEW')]
    
    has_valid = any(label in VALID_CATEGORIES for label in unique_labels)
    if not has_valid:
        print(f"GROUND TRUTH BELUM TERSEDIA. Tidak ada label valid ({VALID_CATEGORIES}) di kolom {label_column}. Jalankan anotasi manusia terlebih dahulu.")
        return False
        
    return True

class RootGroupSplitter:
    """Splitter that ensures no root overlap between folds."""
    def __init__(self, n_splits=5):
        self.n_splits = n_splits
        self.gkf = GroupKFold(n_splits=self.n_splits)
        
    def split(self, X, y=None, groups=None):
        if groups is None:
            raise ValueError("The 'groups' parameter must not be None. Ensure Root_Tweet_ID is passed as groups.")
        return self.gkf.split(X, y, groups)
        
    def get_n_splits(self, X=None, y=None, groups=None):
        return self.n_splits

def build_experiment_registry() -> dict:
    """Return dict of experiment configs."""
    alphas = [0.01, 0.03, 0.1, 0.3, 0.5, 1.0, 2.0]
    
    registry = {
        'E0': {
            'description': 'Dummy Classifiers (most_frequent & stratified)',
            'type': 'baseline'
        },
        'E1': {
            'description': 'Keyword Baseline',
            'type': 'baseline'
        },
        'E2': {
            'description': 'BernoulliNB + CountVectorizer(binary=True)',
            'alphas': alphas,
            'type': 'nb'
        },
        'E3': {
            'description': 'MultinomialNB + TfidfVectorizer',
            'alphas': alphas,
            'type': 'nb'
        },
        'E4': {
            'description': 'ComplementNB + TfidfVectorizer',
            'alphas': alphas,
            'type': 'nb'
        },
        'E5': {
            'description': 'ComplementNB + FeatureUnion(Word+Char)',
            'alphas': alphas,
            'type': 'nb'
        },
        'E6': {
            'description': 'ComplementNB + Weighted Root Context',
            'alphas': alphas,
            'type': 'nb'
        },
        'Audit': {
            'description': 'LinearSVC + TfidfVectorizer',
            'type': 'svc'
        }
    }
    return registry

class WeightedRootContext(BaseEstimator, TransformerMixin):
    """Custom transformer that concatenates reply text with root text at reduced weight."""
    def __init__(self, root_weight: float = 0.3, root_col: str = 'Root_Text', reply_col: str = 'Teks_Model'):
        self.root_weight = root_weight
        self.root_col = root_col
        self.reply_col = reply_col
        
    def fit(self, X, y=None):
        return self
        
    def transform(self, X):
        # This assumes X is a DataFrame with reply_col and root_col
        if not isinstance(X, pd.DataFrame):
            raise ValueError("WeightedRootContext requires a pandas DataFrame.")
            
        # A simple string concatenation baseline; advanced weighting would require custom vectorization
        # e.g. return X[self.reply_col] + " " + X[self.root_col]
        # In a real TF-IDF weighting scenario, we would process them separately and sum their vectors weighted.
        pass

def build_pipeline(experiment_id: str, alpha: float, config: dict) -> Pipeline:
    """Build sklearn pipeline for given experiment."""
    if experiment_id == 'E0':
        return Pipeline([('clf', DummyClassifier(strategy='most_frequent'))])
        
    elif experiment_id == 'E2':
        return Pipeline([
            ('vect', CountVectorizer(binary=True, ngram_range=(1,2))),
            ('clf', BernoulliNB(alpha=alpha))
        ])
        
    elif experiment_id == 'E3':
        return Pipeline([
            ('vect', TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True)),
            ('clf', MultinomialNB(alpha=alpha))
        ])
        
    elif experiment_id == 'E4':
        return Pipeline([
            ('vect', TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True)),
            ('clf', ComplementNB(alpha=alpha))
        ])
        
    elif experiment_id == 'E5':
        word_char_union = FeatureUnion([
            ('word', TfidfVectorizer(ngram_range=(1,2))),
            ('char', TfidfVectorizer(analyzer='char_wb', ngram_range=(3,5)))
        ])
        return Pipeline([
            ('vect', word_char_union),
            ('clf', ComplementNB(alpha=alpha))
        ])
        
    elif experiment_id == 'E6':
        # E6 requires specific DataFrame handling before vectorization
        return Pipeline([
            ('context', WeightedRootContext()),
            ('vect', TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True)),
            ('clf', ComplementNB(alpha=alpha))
        ])
        
    elif experiment_id == 'Audit':
        return Pipeline([
            ('vect', TfidfVectorizer(ngram_range=(1,2))),
            ('clf', LinearSVC(random_state=42))
        ])
        
    raise ValueError(f"Unknown experiment_id: {experiment_id}")

def run_experiment(experiment_id: str, df: pd.DataFrame, config: dict) -> dict:
    if not check_ground_truth(df):
        sys.exit(1)
    
    # Placeholder for running experiment when ground truth is available
    return {}

def run_all_experiments(df: pd.DataFrame, config: dict) -> list[dict]:
    if not check_ground_truth(df):
        sys.exit(1)
        
    results = []
    # Placeholder for running all experiments
    return results

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 1. Load config (stubbed)
    config = {}
    
    # 2. Load dataset
    # We try to load it from the expected path, but handle it gracefully if it doesn't exist
    dataset_path = Path(r"c:\laragon\www\twscraper\output\MBG_Dataset_DirectReplies_20260907_0825.csv")
    try:
        df = pd.read_csv(dataset_path)
        logger.info(f"Loaded dataset from {dataset_path} with {len(df)} rows.")
    except Exception as e:
        logger.warning(f"Could not load dataset at {dataset_path}: {e}")
        # Create empty DataFrame to allow script to exit properly through check_ground_truth
        df = pd.DataFrame()
    
    # 3. Check ground truth - exits with message if not available
    if not check_ground_truth(df):
        sys.exit(1)
        
    # 4. Would run experiments here
    print("Running experiments...")
    results = run_all_experiments(df, config)
