"""Prepare an auditable, blinded human-annotation pilot using local data only."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

from .dataset import audit_dataset, validate_dataset_contract
from .sampling import assign_candidate_stratum, create_pilot_csv, load_aspect_rules, sample_pilot

CORE = ['Tweet_ID', 'Root_Tweet_ID', 'Conversation_ID', 'In_Reply_To_Tweet_ID',
        'Waktu_Posting', 'Username', 'Teks_Komentar', 'Jumlah_Likes',
        'Jumlah_Retweet', 'Sumber_Akuisisi', 'Hierarki_Komentar']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    # csv.DictReader preserves both long IDs and literal strings such as NA/null.
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        if any(None in row or None in row.values() for row in rows):
            raise ValueError('Malformed CSV record')
        return pd.DataFrame(rows, columns=reader.fieldnames)


def source_audit(source, checkpoint):
    raw = source.read_bytes()
    frame = read_csv(source)
    missing = set(CORE) - set(frame.columns)
    if missing:
        raise ValueError(f'Missing core columns: {sorted(missing)}')
    audit = audit_dataset(frame)
    errors = validate_dataset_contract(audit)
    empty_core = {col: int(frame[col].str.strip().eq('').sum()) for col in CORE}
    if any(count for col, count in empty_core.items() if col != 'In_Reply_To_Tweet_ID'):
        errors.append('Empty required fields')
    if not frame['Hierarki_Komentar'].isin(['Root_Tweet', 'Direct_Reply']).all():
        errors.append('Unexpected hierarchy')
    if not frame['Tweet_ID'].str.fullmatch(r'[0-9]+').all():
        errors.append('Invalid Tweet_ID')
    cp = json.loads(checkpoint.read_text(encoding='utf-8-sig'))
    seen = {str(value) for value in cp.get('seen_ids', [])}
    ids = set(frame['Tweet_ID'])
    sync = {'file': checkpoint.name, 'sha256': digest(checkpoint), 'seen_ids': len(seen),
            'csv_only': len(ids - seen), 'checkpoint_only': len(seen - ids)}
    if ids != seen:
        errors.append('Source/checkpoint ID mismatch')
    if errors:
        raise ValueError('; '.join(errors))
    audit.update(file=source.name, sha256=hashlib.sha256(raw).hexdigest(),
                 encoding='utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8',
                 physical_lines=len(raw.splitlines()), empty_core=empty_core, checkpoint=sync)
    return frame, audit


def prepare_pilot(source, checkpoint, config_path, output_dir):
    """Create new versioned files only; never read existing labels as candidates."""
    source, checkpoint, config_path, output_dir = map(Path, (source, checkpoint, config_path, output_dir))
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    base = config_path.parent.parent
    rules_path = base / config['aspect_candidate_rules_file']
    guide_path = base / 'LABELING_GUIDE.md'
    frame, audit = source_audit(source, checkpoint)
    roots = frame[frame['Hierarki_Komentar'].eq('Root_Tweet')][['Tweet_ID', 'Teks_Komentar']]
    roots = roots.rename(columns={'Tweet_ID': 'Root_Tweet_ID', 'Teks_Komentar': 'Teks_Root'})
    replies = frame[frame['Hierarki_Komentar'].eq('Direct_Reply')]
    candidates = replies.merge(roots, on='Root_Tweet_ID', how='left', validate='many_to_one')
    if candidates['Teks_Root'].isna().any() or candidates['Teks_Root'].str.strip().eq('').any():
        raise ValueError('Root context is required for every pilot candidate')
    candidates = assign_candidate_stratum(candidates, load_aspect_rules(rules_path))
    seed, total = int(config['random_seed']), int(config['pilot_size'])
    pilot = sample_pilot(candidates, config, seed=seed, total=total)
    if len(pilot) != total:
        raise ValueError(f'Only {len(pilot)} of {total} samples available under root cap')
    # Hide selection order as well as keyword columns from the annotators.
    pilot = pilot.sample(frac=1, random_state=seed).reset_index(drop=True)
    repeats = sample_pilot(candidates, config, seed=seed, total=total)
    repeats = repeats.sample(frac=1, random_state=seed).reset_index(drop=True)
    if pilot['Tweet_ID'].tolist() != repeats['Tweet_ID'].tolist():
        raise AssertionError('Non-reproducible sampling')
    root_counts = pilot['Root_Tweet_ID'].value_counts()
    texts = candidates['Teks_Komentar'].str.normalize('NFKC').str.lower().str.replace(r'\s+', ' ', regex=True).str.strip()
    cross_root = candidates.assign(normalized=texts).groupby('normalized')['Root_Tweet_ID'].nunique()
    report = {
        'status': 'PENDING_TWO_INDEPENDENT_HUMAN_ANNOTATORS',
        'created_at': datetime.now(timezone(timedelta(hours=7))).isoformat(),
        'source_audit': audit, 'random_seed': seed,
        'label_guide_version': str(config['label_guide_version']),
        'label_guide_sha256': digest(guide_path), 'config_sha256': digest(config_path),
        'rules_sha256': digest(rules_path),
        'code_sha256': {name: digest(Path(__file__).parent / name) for name in ['pilot.py', 'sampling.py']},
        'pilot_rows': len(pilot), 'unique_ids': pilot['Tweet_ID'].nunique(),
        'unique_roots': int(root_counts.size), 'max_samples_per_root': int(root_counts.max()),
        'root_cap': int(config['max_samples_per_root']),
        'source_strata': candidates['Sampling_Stratum'].value_counts().to_dict(),
        'pilot_strata': pilot['Sampling_Stratum'].value_counts().to_dict(),
        'reproducibility_verified': True, 'human_labels_completed': 0,
        'normalized_identical_text_groups_across_roots': int((cross_root > 1).sum()),
        'near_duplicate_audit': 'Pending before train/validation/test split; no split created',
        'notes': ['Strata are candidate signals, not labels or population prevalence.',
                  'Blank parent IDs are valid for root tweets.',
                  'Canonical CSV preserves raw text; use XLSX for manual annotation.'],
    }
    # Preserve existing runs and annotations even when the command is repeated.
    if output_dir.exists():
        raise FileExistsError(f'Output directory already exists: {output_dir}')
    output_dir.mkdir(parents=True)
    pilot_path = output_dir / 'pilot_raw.csv'
    create_pilot_csv(pilot, pilot_path, str(config['label_guide_version']))
    raw_pilot = read_csv(pilot_path)
    assert raw_pilot['Tweet_ID'].tolist() == pilot['Tweet_ID'].tolist()
    assert raw_pilot['Teks_Komentar'].tolist() == pilot['Teks_Komentar'].tolist()
    assert raw_pilot['Teks_Root'].tolist() == pilot['Teks_Root'].tolist()
    report['pilot_csv_sha256'] = digest(pilot_path)
    blind = pilot[['Tweet_ID', 'Root_Tweet_ID', 'Teks_Root', 'Teks_Komentar']].to_dict(orient='records')
    (output_dir / 'workbook_input.json').write_text(json.dumps({
        'rows': blind, 'label_guide_version': str(config['label_guide_version']),
        'taxonomy': config['target_subcategories'], 'source_file': source.name,
        'source_sha256': audit['sha256'],
    }, ensure_ascii=False), encoding='utf-8')
    pilot[['Tweet_ID', 'Sampling_Stratum', 'Sampling_Reason']].to_csv(
        output_dir / 'coordinator_sampling.csv', index=False, encoding='utf-8-sig', quoting=csv.QUOTE_ALL)
    if digest(source) != audit['sha256'] or digest(checkpoint) != audit['checkpoint']['sha256']:
        raise RuntimeError('Source changed while preparing pilot')
    (output_dir / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    base = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=base / 'config/project_config.yaml')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    report = prepare_pilot(args.source, args.checkpoint, args.config, args.output_dir)
    print(json.dumps({key: report[key] for key in ['status', 'pilot_rows', 'unique_ids', 'unique_roots',
                                                    'max_samples_per_root', 'pilot_strata']}, indent=2))


if __name__ == '__main__':
    main()
