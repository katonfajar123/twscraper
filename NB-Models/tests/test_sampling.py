"""Tests for sampling module."""
import pytest
import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.sampling import assign_candidate_stratum, sample_pilot, create_pilot_csv


@pytest.fixture
def large_fixture():
    """Fixture with enough rows to sample from."""
    rows = []
    # Create 10 roots
    for i in range(10):
        root_id = str(1000 + i)
        rows.append({
            'Tweet_ID': root_id,
            'Root_Tweet_ID': root_id,
            'Conversation_ID': root_id,
            'In_Reply_To_Tweet_ID': '',
            'Teks_Komentar': f'Root tweet {i}',
            'Hierarki_Komentar': 'Root_Tweet',
            'Sumber_Akuisisi': 'KEYWORD_SEARCH',
        })
        # Create 50 replies per root with varied text
        texts = [
            'porsi kurang nutrisi',    # Mutu_Gizi signal
            'vendor tidak layak',      # Tata_Kelola signal
            'terlambat datang',        # Distribusi signal
            'porsi vendor gabungan',   # Overlap
            'bagus sekali programnya', # No_Signal
        ]
        for j in range(50):
            reply_id = str(2000 + i * 100 + j)
            rows.append({
                'Tweet_ID': reply_id,
                'Root_Tweet_ID': root_id,
                'Conversation_ID': root_id,
                'In_Reply_To_Tweet_ID': root_id,
                'Teks_Komentar': texts[j % len(texts)],
                'Hierarki_Komentar': 'Direct_Reply',
                'Sumber_Akuisisi': 'DIRECT_REPLY',
            })
    return pd.DataFrame(rows)


@pytest.fixture
def sample_rules():
    return {
        'Mutu_Gizi': ['porsi', 'nutrisi', 'gizi'],
        'Tata_Kelola': ['vendor', 'dapur', 'anggaran'],
        'Distribusi': ['terlambat', 'kirim', 'logistik'],
    }


class TestStratumAssignment:
    def test_single_match(self, large_fixture, sample_rules):
        df = assign_candidate_stratum(large_fixture, sample_rules)
        mutu = df[df['Sampling_Stratum'] == 'Mutu_Gizi_Signal']
        assert len(mutu) > 0

    def test_overlap_match(self, large_fixture, sample_rules):
        df = assign_candidate_stratum(large_fixture, sample_rules)
        overlap = df[df['Sampling_Stratum'] == 'Overlap']
        assert len(overlap) > 0

    def test_no_signal(self, large_fixture, sample_rules):
        df = assign_candidate_stratum(large_fixture, sample_rules)
        no_signal = df[df['Sampling_Stratum'] == 'No_Signal']
        assert len(no_signal) > 0


class TestPilotSampling:
    def test_pilot_size(self, large_fixture, sample_rules):
        df = assign_candidate_stratum(large_fixture, sample_rules)
        pilot = sample_pilot(df, {'max_samples_per_root': 5}, total=50)
        assert len(pilot) == 50

    def test_no_duplicates(self, large_fixture, sample_rules):
        df = assign_candidate_stratum(large_fixture, sample_rules)
        pilot = sample_pilot(df, {'max_samples_per_root': 5}, total=50)
        assert pilot['Tweet_ID'].nunique() == len(pilot)

    def test_max_per_root(self, large_fixture, sample_rules):
        df = assign_candidate_stratum(large_fixture, sample_rules)
        pilot = sample_pilot(df, {'max_samples_per_root': 3}, total=50)
        root_counts = pilot['Root_Tweet_ID'].value_counts()
        assert root_counts.max() <= 3

    def test_labels_empty(self, large_fixture, sample_rules, tmp_path):
        df = assign_candidate_stratum(large_fixture, sample_rules)
        pilot = sample_pilot(df, {'max_samples_per_root': 5}, total=50)
        create_pilot_csv(pilot, tmp_path / 'pilot.csv')
        result = pd.read_csv(tmp_path / 'pilot.csv', encoding='utf-8-sig', dtype=str)
        for col in ['Kategori_Utama', 'Subkategori_Primer']:
            if col in result.columns:
                assert (result[col].fillna('') == '').all(), f"{col} should be empty"

    def test_deterministic(self, large_fixture, sample_rules):
        df = assign_candidate_stratum(large_fixture, sample_rules)
        p1 = sample_pilot(df, {'max_samples_per_root': 5}, seed=42, total=50)
        p2 = sample_pilot(df, {'max_samples_per_root': 5}, seed=42, total=50)
        assert p1['Tweet_ID'].tolist() == p2['Tweet_ID'].tolist()

    def test_backfill_respects_global_cap(self, large_fixture, sample_rules):
        df = assign_candidate_stratum(large_fixture, sample_rules)
        # Four strata missing: backfill must account for earlier selections.
        df['Sampling_Stratum'] = 'No_Signal'
        pilot = sample_pilot(df, {'max_samples_per_root': 3}, total=50)
        assert len(pilot) == 30
        assert pilot['Root_Tweet_ID'].value_counts().max() == 3

    def test_reject_duplicate_ids(self, large_fixture, sample_rules):
        df = assign_candidate_stratum(large_fixture, sample_rules)
        df = pd.concat([df, df.iloc[[20]]], ignore_index=True)
        with pytest.raises(ValueError, match='Duplicate'):
            sample_pilot(df, {}, total=50)

    def test_export_is_blind_and_never_overwrites(self, large_fixture, sample_rules, tmp_path):
        df = assign_candidate_stratum(large_fixture, sample_rules)
        pilot = sample_pilot(df, {}, total=50)
        pilot['Kategori_Utama'] = 'Mutu_Gizi'
        output = tmp_path / 'pilot.csv'
        create_pilot_csv(pilot, output)
        before = output.read_bytes()
        assert before.startswith(b'\xef\xbb\xbf')
        result = pd.read_csv(output, dtype=str, keep_default_na=False)
        assert result['Kategori_Utama'].eq('').all()
        assert 'Sampling_Stratum' not in result
        assert 'Sampling_Reason' not in result
        with pytest.raises(FileExistsError):
            create_pilot_csv(pilot, output)
        assert output.read_bytes() == before

    def test_small_total_and_nonunique_index(self, large_fixture, sample_rules):
        df = assign_candidate_stratum(large_fixture, sample_rules)
        df.index = [0] * len(df)
        pilot = sample_pilot(df, {}, total=2)
        assert len(pilot) == pilot['Tweet_ID'].nunique() == 2
