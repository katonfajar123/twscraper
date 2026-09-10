"""Offline regression tests for pilot integrity and source durability."""
import csv
import json
from pathlib import Path

import pytest
import yaml

from src.pilot import prepare_pilot, read_csv


@pytest.fixture
def pilot_inputs(tmp_path, sample_dataset):
    base = tmp_path / 'model'
    (base / 'config').mkdir(parents=True)
    (base / 'LABELING_GUIDE.md').write_text('Test guide', encoding='utf-8')
    (base / 'config/rules.yaml').write_text('Mutu_Gizi: [porsi]', encoding='utf-8')
    config = {'aspect_candidate_rules_file': 'config/rules.yaml', 'random_seed': 42,
              'pilot_size': 4, 'max_samples_per_root': 2, 'label_guide_version': '1.0',
              'target_subcategories': {'Mutu_Gizi': ['Keamanan_Konsumsi']}}
    config_path = base / 'config/project_config.yaml'
    config_path.write_text(yaml.safe_dump(config), encoding='utf-8')
    frame = sample_dataset.copy()
    frame.loc[0, 'Teks_Komentar'] = 'NA'
    frame.loc[3, 'Teks_Komentar'] = '=1+1, "kutip"\nUnicode: 🍱'
    source = tmp_path / 'source.csv'
    frame.to_csv(source, index=False, encoding='utf-8-sig', quoting=csv.QUOTE_ALL)
    checkpoint = tmp_path / 'checkpoint.json'
    checkpoint.write_text(json.dumps({'seen_ids': frame['Tweet_ID'].tolist()}))
    return source, checkpoint, config_path


def test_prepare_preserves_raw_data_and_is_reproducible(pilot_inputs, tmp_path):
    source, checkpoint, config = pilot_inputs
    before = [source.read_bytes(), checkpoint.read_bytes()]
    first = prepare_pilot(source, checkpoint, config, tmp_path / 'run1')
    second = prepare_pilot(source, checkpoint, config, tmp_path / 'run2')
    assert first['pilot_csv_sha256'] == second['pilot_csv_sha256']
    assert first['max_samples_per_root'] <= 2
    assert first['pilot_rows'] == first['unique_ids'] == 4
    assert first['human_labels_completed'] == 0
    assert before == [source.read_bytes(), checkpoint.read_bytes()]
    assert read_csv(source).loc[0, 'Teks_Komentar'] == 'NA'
    blind = json.loads((tmp_path / 'run1/workbook_input.json').read_text(encoding='utf-8'))
    assert all(set(r) == {'Tweet_ID', 'Root_Tweet_ID', 'Teks_Root', 'Teks_Komentar'} for r in blind['rows'])
    with pytest.raises(FileExistsError):
        prepare_pilot(source, checkpoint, config, tmp_path / 'run1')


def test_checkpoint_mismatch_fails_before_export(pilot_inputs, tmp_path):
    source, checkpoint, config = pilot_inputs
    checkpoint.write_text('{"seen_ids": []}')
    with pytest.raises(ValueError, match='checkpoint'):
        prepare_pilot(source, checkpoint, config, tmp_path / 'run')
    assert not (tmp_path / 'run').exists()


def test_insufficient_capacity_fails_before_export(pilot_inputs, tmp_path):
    source, checkpoint, config = pilot_inputs
    content = yaml.safe_load(config.read_text())
    content['pilot_size'] = 300
    config.write_text(yaml.safe_dump(content))
    with pytest.raises(ValueError, match='samples available'):
        prepare_pilot(source, checkpoint, config, tmp_path / 'run')
    assert not (tmp_path / 'run').exists()
