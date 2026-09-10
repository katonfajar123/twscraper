"""Tests for dataset audit and annotation template."""
import pytest
import pandas as pd
import csv
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.dataset import (
    audit_dataset,
    validate_dataset_contract,
    create_annotation_template,
    get_direct_replies,
    get_roots,
    load_dataset,
)


class TestDuplicateDetection:
    def test_duplicate_detected(self, sample_dataset_with_duplicates):
        audit = audit_dataset(sample_dataset_with_duplicates)
        assert audit['duplicate_tweet_ids']['count'] > 0

    def test_no_duplicates(self, sample_dataset):
        audit = audit_dataset(sample_dataset)
        assert audit['duplicate_tweet_ids']['count'] == 0


class TestRootReplyRelationship:
    def test_valid_relationships(self, sample_dataset):
        audit = audit_dataset(sample_dataset)
        assert audit['root_relationship_validation'] is True
        assert audit['direct_reply_validation'] is True

    def test_orphan_reply_detected(self, sample_dataset_with_orphan):
        audit = audit_dataset(sample_dataset_with_orphan)
        assert audit['orphan_replies_count'] > 0


class TestIDsAreStrings:
    def test_id_columns_string_dtype(self, sample_dataset):
        for col in ['Tweet_ID', 'Root_Tweet_ID', 'Conversation_ID', 'In_Reply_To_Tweet_ID']:
            assert sample_dataset[col].dtype == object, f"{col} should be string/object dtype"

    def test_ids_not_numeric(self, sample_dataset):
        """IDs must not be silently coerced to numeric."""
        for col in ['Tweet_ID', 'Root_Tweet_ID']:
            for val in sample_dataset[col]:
                if val:
                    assert isinstance(val, str), f"{col} value {val} should be str"


class TestMissingText:
    def test_missing_text_count(self, sample_dataset):
        audit = audit_dataset(sample_dataset)
        assert audit['missing_text_count'] == 0

    def test_missing_text_detected(self, sample_dataset):
        df = sample_dataset.copy()
        df.loc[3, 'Teks_Komentar'] = ''
        audit = audit_dataset(df)
        assert audit['missing_text_count'] > 0


class TestAuditReport:
    def test_audit_returns_expected_keys(self, sample_dataset):
        audit = audit_dataset(sample_dataset)
        expected_keys = [
            'total_rows', 'unique_tweet_ids', 'duplicate_tweet_ids',
            'root_count', 'direct_reply_count', 'nested_reply_count',
            'roots_with_direct_replies', 'root_relationship_validation',
            'direct_reply_validation', 'orphan_replies_count',
            'missing_text_count', 'reply_per_root_stats',
            'high_reply_roots', 'language_distribution',
            'source_distribution', 'hierarchy_distribution',
        ]
        for key in expected_keys:
            assert key in audit, f"Missing key: {key}"

    def test_audit_counts(self, sample_dataset):
        audit = audit_dataset(sample_dataset)
        assert audit['total_rows'] == 8
        assert audit['root_count'] == 3
        assert audit['direct_reply_count'] == 5
        assert audit['nested_reply_count'] == 0


class TestValidateContract:
    def test_clean_dataset_passes(self, sample_dataset):
        audit = audit_dataset(sample_dataset)
        errors = validate_dataset_contract(audit)
        assert len(errors) == 0

    def test_duplicates_fail(self, sample_dataset_with_duplicates):
        audit = audit_dataset(sample_dataset_with_duplicates)
        errors = validate_dataset_contract(audit)
        assert any('duplicate' in e.lower() for e in errors)

    def test_orphans_fail(self, sample_dataset_with_orphan):
        audit = audit_dataset(sample_dataset_with_orphan)
        errors = validate_dataset_contract(audit)
        assert any('orphan' in e.lower() for e in errors)


class TestAnnotationTemplate:
    def test_template_columns(self, sample_dataset, tmp_path):
        output = tmp_path / 'template.csv'
        result = create_annotation_template(sample_dataset, output)
        expected_cols = [
            'Tweet_ID', 'Root_Tweet_ID', 'Teks_Root', 'Teks_Komentar',
            'Kategori_Utama', 'Subkategori_Primer', 'Kategori_Sekunder',
            'Annotation_Status', 'Annotator_1', 'Annotator_2',
            'Adjudicated_Label', 'Label_Guide_Version',
        ]
        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_labels_empty(self, sample_dataset, tmp_path):
        output = tmp_path / 'template.csv'
        result = create_annotation_template(sample_dataset, output)
        label_cols = ['Kategori_Utama', 'Subkategori_Primer', 'Kategori_Sekunder']
        for col in label_cols:
            assert (result[col] == '').all(), f"{col} should be empty"

    def test_preserves_raw_text(self, sample_dataset, tmp_path):
        output = tmp_path / 'template.csv'
        result = create_annotation_template(sample_dataset, output)
        replies = sample_dataset[sample_dataset['Hierarki_Komentar'] == 'Direct_Reply']
        for _, row in replies.iterrows():
            matched = result[result['Tweet_ID'] == row['Tweet_ID']]
            assert not matched.empty
            assert matched.iloc[0]['Teks_Komentar'] == row['Teks_Komentar']

    def test_only_direct_replies(self, sample_dataset, tmp_path):
        output = tmp_path / 'template.csv'
        result = create_annotation_template(sample_dataset, output)
        # Should only contain direct replies, not roots
        assert len(result) == 5  # 5 direct replies in fixture

    def test_encoding_utf8sig(self, sample_dataset, tmp_path):
        output = tmp_path / 'template.csv'
        create_annotation_template(sample_dataset, output)
        with open(output, 'rb') as f:
            bom = f.read(3)
        assert bom == b'\xef\xbb\xbf', "File should start with UTF-8 BOM"
