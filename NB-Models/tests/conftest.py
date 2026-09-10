"""Shared pytest fixtures for NB-Models tests."""
import pytest
import pandas as pd
import tempfile
from pathlib import Path


@pytest.fixture
def sample_dataset() -> pd.DataFrame:
    """Small fixture dataset with roots and direct replies."""
    data = {
        'Tweet_ID': ['100', '101', '102', '200', '201', '202', '300', '301'],
        'Root_Tweet_ID': ['100', '101', '102', '100', '100', '101', '102', '102'],
        'Conversation_ID': ['100', '101', '102', '100', '100', '101', '102', '102'],
        'In_Reply_To_Tweet_ID': ['', '', '', '100', '100', '101', '102', '102'],
        'Waktu_Posting': ['2026-01-01'] * 8,
        'Username': ['u_a', 'u_b', 'u_c', 'u_d', 'u_e', 'u_f', 'u_g', 'u_h'],
        'Teks_Komentar': [
            'Root tweet tentang MBG porsi kecil',
            'Root tweet tentang vendor tidak layak',
            'Root tweet tentang makanan terlambat datang',
            'Porsinya kurang untuk anak SMP',
            'Menunya enak tapi sedikit',
            'Vendor tanpa sertifikat kok lolos?',
            'Datangnya sudah lewat jam makan',
            'Kotaknya bocor saat dibagikan',
        ],
        'Jumlah_Likes': [10, 5, 3, 2, 1, 4, 0, 1],
        'Jumlah_Retweet': [0] * 8,
        'Sumber_Akuisisi': ['KEYWORD_SEARCH'] * 3 + ['DIRECT_REPLY'] * 5,
        'Hierarki_Komentar': [
            'Root_Tweet', 'Root_Tweet', 'Root_Tweet',
            'Direct_Reply', 'Direct_Reply', 'Direct_Reply',
            'Direct_Reply', 'Direct_Reply',
        ],
        'Display_Name': ['A'] * 8,
        'Followers_Count': [100] * 8,
        'Bahasa': ['in'] * 8,
        'Jumlah_Reply': [0] * 8,
        'Jumlah_Quote': [0] * 8,
        'Jumlah_View': [0] * 8,
        'Keyword_Matched': [''] * 8,
        'URL': [''] * 8,
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_dataset_with_duplicates(sample_dataset: pd.DataFrame) -> pd.DataFrame:
    """Dataset with a duplicate Tweet_ID."""
    dup_row = sample_dataset.iloc[[0]].copy()
    return pd.concat([sample_dataset, dup_row], ignore_index=True)


@pytest.fixture
def sample_dataset_with_orphan(sample_dataset: pd.DataFrame) -> pd.DataFrame:
    """Direct reply referencing a non-existent root."""
    df = sample_dataset.copy()
    df.loc[df['Tweet_ID'] == '200', 'Root_Tweet_ID'] = '999'
    df.loc[df['Tweet_ID'] == '200', 'Conversation_ID'] = '999'
    df.loc[df['Tweet_ID'] == '200', 'In_Reply_To_Tweet_ID'] = '999'
    return df


@pytest.fixture
def sample_labeled_dataset(sample_dataset: pd.DataFrame) -> pd.DataFrame:
    """Dataset with Kategori_Utama filled in for all rows."""
    df = sample_dataset.copy()
    labels = [
        'Mutu_Gizi', 'Tata_Kelola', 'Distribusi',
        'Mutu_Gizi', 'Mutu_Gizi', 'Tata_Kelola',
        'Distribusi', 'Distribusi',
    ]
    df['Kategori_Utama'] = labels
    return df


@pytest.fixture
def sample_unlabeled_dataset(sample_dataset: pd.DataFrame) -> pd.DataFrame:
    """Dataset without Kategori_Utama column."""
    return sample_dataset.copy()


@pytest.fixture
def tmp_csv_path(tmp_path: Path) -> Path:
    """Temporary CSV file path."""
    return tmp_path / 'test_output.csv'


@pytest.fixture
def real_dataset_path() -> Path:
    """Path to the real dataset (may not exist in CI)."""
    return Path(__file__).resolve().parent.parent.parent / 'output' / 'MBG_Dataset_DirectReplies_20260907_0825.csv'
