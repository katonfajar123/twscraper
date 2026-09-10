"""Integration tests for NB-Models pipeline."""
import pytest
import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REAL_CSV = Path(__file__).resolve().parent.parent.parent / 'output' / 'MBG_Dataset_DirectReplies_20260907_0825.csv'


@pytest.mark.skipif(not REAL_CSV.exists(), reason="Real dataset not available")
class TestRealDatasetAudit:
    def test_full_audit(self):
        from src.dataset import load_dataset, audit_dataset, validate_dataset_contract
        df = load_dataset(REAL_CSV)
        audit = audit_dataset(df)
        errors = validate_dataset_contract(audit)
        assert len(errors) == 0, f"Contract errors: {errors}"
        assert audit['total_rows'] == 20000
        assert audit['root_count'] == 2306
        assert audit['direct_reply_count'] == 17694
        assert audit['nested_reply_count'] == 0
        assert audit['duplicate_tweet_ids']['count'] == 0

    def test_ids_are_strings_in_real_data(self):
        from src.dataset import load_dataset
        df = load_dataset(REAL_CSV)
        for col in ['Tweet_ID', 'Root_Tweet_ID', 'Conversation_ID', 'In_Reply_To_Tweet_ID']:
            assert df[col].dtype == object, f"{col} should be string"


class TestAnnotationJoinPreservesIDs:
    def test_join_keeps_ids_as_strings(self, sample_dataset, tmp_path):
        from src.dataset import create_annotation_template
        output = tmp_path / 'template.csv'
        result = create_annotation_template(sample_dataset, output)
        assert result['Tweet_ID'].dtype == object
        assert result['Root_Tweet_ID'].dtype == object


class TestCSVOutputUTF8SIG:
    def test_output_has_bom(self, sample_dataset, tmp_path):
        from src.dataset import create_annotation_template
        output = tmp_path / 'template.csv'
        create_annotation_template(sample_dataset, output)
        with open(output, 'rb') as f:
            assert f.read(3) == b'\xef\xbb\xbf'


class TestTrainingFailsWithoutGroundTruth:
    def test_check_returns_false(self, sample_unlabeled_dataset):
        from src.train import check_ground_truth
        assert check_ground_truth(sample_unlabeled_dataset) is False
