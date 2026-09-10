"""Sampling module for pilot annotation candidate selection.

Root-aware stratified sampling that uses keyword signals for candidate
discovery, NOT for ground truth labeling.
"""
import pandas as pd
import numpy as np
import yaml
import logging
import hashlib
import csv
import re
from pathlib import Path
from typing import Optional

from .dataset import load_dataset, audit_dataset, create_annotation_template

logger = logging.getLogger(__name__)


def load_aspect_rules(rules_path: Path) -> dict:
    """Load aspect candidate rules YAML. Returns dict with category -> keywords."""
    if not rules_path.exists():
        logger.warning(f"Rules path {rules_path} does not exist. Returning empty rules.")
        return {}
    with open(rules_path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f) or {}
    # Normalize structure: accept both flat lists and {keywords: [...]}
    rules: dict[str, list[str]] = {}
    for cat, val in raw.items():
        if cat.startswith('#') or cat.startswith('_'):
            continue
        if isinstance(val, dict):
            rules[cat] = val.get('keywords', [])
        elif isinstance(val, list):
            rules[cat] = val
    return rules


def assign_candidate_stratum(df: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """Assign sampling stratum based on keyword matching.
    
    Strata are for CANDIDATE SAMPLING ONLY, not ground truth labels.
    """
    df = df.copy()
    df['Sampling_Stratum'] = 'No_Signal'
    df['Sampling_Reason'] = 'No keyword match'

    if not rules:
        logger.warning("No aspect rules provided. All rows assigned to No_Signal.")
        return df

    # Build regex patterns per category
    patterns: dict[str, re.Pattern] = {}
    for cat, keywords in rules.items():
        if keywords:
            escaped = [re.escape(k) for k in keywords]
            patterns[cat] = re.compile(
                r'(?i)\b(?:' + '|'.join(escaped) + r')\b'
            )

    for idx in df.index:
        text = str(df.at[idx, 'Teks_Komentar'])
        matches = []
        for cat, pat in patterns.items():
            if pat.search(text):
                matches.append(cat)

        if len(matches) == 1:
            df.at[idx, 'Sampling_Stratum'] = f"{matches[0]}_Signal"
            df.at[idx, 'Sampling_Reason'] = f"Matched {matches[0]} keyword"
        elif len(matches) > 1:
            df.at[idx, 'Sampling_Stratum'] = 'Overlap'
            df.at[idx, 'Sampling_Reason'] = f"Matched multiple: {', '.join(matches)}"

    return df


def sample_pilot(
    df: pd.DataFrame,
    config: dict,
    seed: int = 20260907,
    total: int = 300,
) -> pd.DataFrame:
    """Create root-aware, stratified pilot sample.
    
    Algorithm:
    1. Process strata in rarity order (Distribusi first since rarest).
    2. Within each stratum, round-robin across roots to maximize diversity.
    3. Cap samples per root at max_samples_per_root.
    4. Backfill from remaining if total not reached.
    
    Returns DataFrame with Sampling_Stratum and Sampling_Reason columns.
    """
    rng = np.random.RandomState(seed)
    max_per_root = config.get('max_samples_per_root', 5)

    # Only sample from direct replies
    replies_mask = df['Hierarki_Komentar'] == 'Direct_Reply' if 'Hierarki_Komentar' in df.columns else pd.Series(True, index=df.index)
    eligible = df[replies_mask].copy()

    strata_order = [
        'Distribusi_Signal',
        'Tata_Kelola_Signal',
        'Mutu_Gizi_Signal',
        'Overlap',
        'No_Signal',
    ]

    # Target ~60 per stratum, adjustable
    target_per_stratum = max(total // len(strata_order), 1)

    selected_ids: set[str] = set()
    selected_rows: list[pd.DataFrame] = []

    for stratum in strata_order:
        stratum_df = eligible[
            (eligible['Sampling_Stratum'] == stratum) &
            (~eligible['Tweet_ID'].isin(selected_ids))
        ]
        if stratum_df.empty:
            continue

        target = target_per_stratum
        # Round-robin across roots
        roots = stratum_df['Root_Tweet_ID'].unique().tolist()
        rng.shuffle(roots)

        root_pools: dict[str, list[int]] = {}
        for root_id in roots:
            indices = stratum_df[stratum_df['Root_Tweet_ID'] == root_id].index.tolist()
            rng.shuffle(indices)
            root_pools[root_id] = indices

        batch_indices: list[int] = []
        root_counts: dict[str, int] = {r: 0 for r in roots}

        # Round-robin: take 1 from each root, repeat
        for _round in range(max_per_root):
            if len(batch_indices) >= target:
                break
            for root_id in roots:
                if len(batch_indices) >= target:
                    break
                if root_counts[root_id] >= max_per_root:
                    continue
                pool = root_pools[root_id]
                if pool:
                    idx = pool.pop(0)
                    batch_indices.append(idx)
                    root_counts[root_id] += 1

        if batch_indices:
            batch_df = eligible.loc[batch_indices]
            selected_ids.update(batch_df['Tweet_ID'].tolist())
            selected_rows.append(batch_df)

    # Combine and check total
    if selected_rows:
        pilot_df = pd.concat(selected_rows, ignore_index=False)
    else:
        pilot_df = pd.DataFrame(columns=eligible.columns)

    # Backfill if under target
    if len(pilot_df) < total:
        remaining = total - len(pilot_df)
        backfill_pool = eligible[~eligible['Tweet_ID'].isin(selected_ids)]
        if not backfill_pool.empty:
            # Backfill with root diversity
            backfill_roots = backfill_pool['Root_Tweet_ID'].unique().tolist()
            rng.shuffle(backfill_roots)
            backfill_indices: list[int] = []
            for root_id in backfill_roots:
                if len(backfill_indices) >= remaining:
                    break
                root_rows = backfill_pool[backfill_pool['Root_Tweet_ID'] == root_id]
                n_take = min(max_per_root, remaining - len(backfill_indices), len(root_rows))
                if n_take > 0:
                    sampled = root_rows.sample(n=n_take, random_state=seed)
                    backfill_indices.extend(sampled.index.tolist())
            if backfill_indices:
                pilot_df = pd.concat([pilot_df, eligible.loc[backfill_indices]])

    # Deduplicate
    pilot_df = pilot_df.drop_duplicates(subset='Tweet_ID')

    # Trim to exact total
    if len(pilot_df) > total:
        pilot_df = pilot_df.head(total)

    logger.info(f"Pilot sample size: {len(pilot_df)}")
    logger.info(f"Unique roots in pilot: {pilot_df['Root_Tweet_ID'].nunique()}")
    return pilot_df


def create_pilot_csv(
    pilot_df: pd.DataFrame,
    output_path: Path,
    label_guide_version: str = '1.0',
) -> None:
    """Save pilot CSV with empty annotation columns."""
    pilot_df = pilot_df.copy()

    # Add empty annotation columns (NOT filled with any values)
    annotation_cols = [
        'Kategori_Utama', 'Subkategori_Primer', 'Kategori_Sekunder',
        'Annotation_Status', 'Annotator_1', 'Annotator_2',
        'Adjudicated_Label', 'Label_Guide_Version',
    ]
    for col in annotation_cols:
        if col not in pilot_df.columns:
            pilot_df[col] = ''

    # Label_Guide_Version is metadata, not a label
    pilot_df['Label_Guide_Version'] = label_guide_version

    out_cols = [
        'Tweet_ID', 'Root_Tweet_ID',
    ]
    if 'Teks_Root' in pilot_df.columns:
        out_cols.append('Teks_Root')
    out_cols += [
        'Teks_Komentar',
        'Kategori_Utama', 'Subkategori_Primer', 'Kategori_Sekunder',
        'Annotation_Status', 'Annotator_1', 'Annotator_2',
        'Adjudicated_Label', 'Label_Guide_Version',
        'Sampling_Stratum', 'Sampling_Reason',
    ]

    available_cols = [c for c in out_cols if c in pilot_df.columns]
    final_df = pilot_df[available_cols]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(output_path, index=False, encoding='utf-8-sig', quoting=csv.QUOTE_ALL)
    logger.info(f"Pilot CSV saved to {output_path} ({len(final_df)} rows)")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    base_dir = Path(__file__).resolve().parent.parent
    config_path = base_dir / 'config' / 'project_config.yaml'

    config: dict = {'max_samples_per_root': 5, 'label_guide_version': '1.0'}
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config.update(yaml.safe_load(f) or {})

    csv_path = (base_dir / config['dataset_path']).resolve()
    if not csv_path.exists():
        logger.error(f"Dataset not found at {csv_path}")
        raise SystemExit(1)

    df = load_dataset(csv_path)

    # Load or create annotation template (which has Teks_Root joined)
    template_path = base_dir / 'data' / 'annotation_template.csv'
    if not template_path.exists():
        template_df = create_annotation_template(df, template_path)
    else:
        template_df = pd.read_csv(
            template_path, encoding='utf-8-sig', dtype=str
        ).fillna('')

    # Load aspect candidate rules
    rules_path = (base_dir / config.get('aspect_candidate_rules_file', 'config/aspect_candidate_rules.yaml')).resolve()
    rules = load_aspect_rules(rules_path)

    # Assign strata
    strata_df = assign_candidate_stratum(template_df, rules)

    # Print stratum distribution
    print("\n=== STRATUM DISTRIBUTION (Direct Replies) ===")
    print(strata_df['Sampling_Stratum'].value_counts().to_string())

    # Sample pilot
    pilot_df = sample_pilot(strata_df, config, seed=config.get('random_seed', 20260907))

    # Save pilot
    pilot_path = base_dir / 'data' / 'pilot_annotation_300.csv'
    create_pilot_csv(pilot_df, pilot_path, config.get('label_guide_version', '1.0'))

    # Print stats
    print("\n=== PILOT SAMPLING STATS ===")
    print(f"Total pilot samples: {len(pilot_df)}")
    print(f"Unique roots in pilot: {pilot_df['Root_Tweet_ID'].nunique()}")
    print(f"\nStratum Distribution:")
    print(pilot_df['Sampling_Stratum'].value_counts().to_string())
    root_counts = pilot_df['Root_Tweet_ID'].value_counts()
    print(f"\nSamples per root: min={root_counts.min()}, max={root_counts.max()}, "
          f"mean={root_counts.mean():.1f}, median={root_counts.median():.1f}")
    print(f"\nTop 10 roots by sample count:")
    print(root_counts.head(10).to_string())
    print("============================")
