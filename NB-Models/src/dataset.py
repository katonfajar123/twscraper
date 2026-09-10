import pandas as pd
import json
import logging
import hashlib
from pathlib import Path
from typing import Optional
import csv
import yaml

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def load_dataset(csv_path: Path) -> pd.DataFrame:
    logging.info(f"Loading dataset from {csv_path}")
    df = pd.read_csv(
        csv_path, 
        encoding='utf-8-sig',
        dtype={
            'Tweet_ID': str,
            'Root_Tweet_ID': str,
            'Conversation_ID': str,
            'In_Reply_To_Tweet_ID': str
        }
    )
    for col in ['Tweet_ID', 'Root_Tweet_ID', 'Conversation_ID', 'In_Reply_To_Tweet_ID']:
        df[col] = df[col].fillna('')
    logging.info(f"Loaded {len(df)} rows.")
    return df

def audit_dataset(df: pd.DataFrame) -> dict:
    total_rows = len(df)
    unique_tweet_ids = df['Tweet_ID'].nunique()
    tweet_id_counts = df['Tweet_ID'].value_counts()
    duplicate_tweet_ids = tweet_id_counts[tweet_id_counts > 1].index.tolist()
    duplicate_mask = df['Tweet_ID'].duplicated(keep=False)
    duplicate_tweet_ids = df.loc[duplicate_mask, 'Tweet_ID'].unique().tolist()
    
    root_count = (df['Hierarki_Komentar'] == 'Root_Tweet').sum()
    direct_reply_count = (df['Hierarki_Komentar'] == 'Direct_Reply').sum()
    nested_reply_count = (df['Hierarki_Komentar'] == 'Nested_Reply').sum()
    root_count = int((df['Hierarki_Komentar'] == 'Root_Tweet').sum())
    direct_reply_count = int((df['Hierarki_Komentar'] == 'Direct_Reply').sum())
    nested_reply_count = int((df['Hierarki_Komentar'] == 'Nested_Reply').sum())
    
    replies = df[df['Hierarki_Komentar'] == 'Direct_Reply']
    replies = df.loc[df['Hierarki_Komentar'] == 'Direct_Reply'].copy()
    roots_with_direct_replies = replies['Root_Tweet_ID'].nunique()
    
    roots = df[df['Hierarki_Komentar'] == 'Root_Tweet']
    root_relationship_validation = (
        (roots['Tweet_ID'] == roots['Root_Tweet_ID']) & 
        (roots['Tweet_ID'] == roots['Conversation_ID']) & 
        (roots['In_Reply_To_Tweet_ID'] == '')
    ).all()
    
    direct_reply_validation = (
        (replies['In_Reply_To_Tweet_ID'] == replies['Root_Tweet_ID']) & 
        (replies['Conversation_ID'] == replies['Root_Tweet_ID'])
    ).all()
    
    orphan_replies = replies[~replies['Root_Tweet_ID'].isin(roots['Tweet_ID'])].shape[0]
    
    missing_text = df[df['Teks_Komentar'].isna() | (df['Teks_Komentar'] == '')].shape[0]
    
    reply_counts = replies['Root_Tweet_ID'].value_counts()
    reply_per_root_stats = {
        'min': float(reply_counts.min()) if not reply_counts.empty else 0,
        'max': float(reply_counts.max()) if not reply_counts.empty else 0,
        'mean': float(reply_counts.mean()) if not reply_counts.empty else 0,
        'median': float(reply_counts.median()) if not reply_counts.empty else 0,
        'std': float(reply_counts.std()) if not reply_counts.empty else 0,
        'percentiles': {
            '25': float(reply_counts.quantile(0.25)) if not reply_counts.empty else 0,
            '50': float(reply_counts.quantile(0.50)) if not reply_counts.empty else 0,
            '75': float(reply_counts.quantile(0.75)) if not reply_counts.empty else 0,
            '90': float(reply_counts.quantile(0.90)) if not reply_counts.empty else 0,
            '95': float(reply_counts.quantile(0.95)) if not reply_counts.empty else 0,
            '99': float(reply_counts.quantile(0.99)) if not reply_counts.empty else 0,
        }
    }
    
    high_reply_roots = reply_counts[reply_counts >= 200].to_dict()
    
    language_distribution = df['Bahasa'].value_counts().to_dict()
    source_distribution = df['Sumber_Akuisisi'].value_counts().to_dict()
    hierarchy_distribution = df['Hierarki_Komentar'].value_counts().to_dict()
    
    # Hash calculation - just returning a placeholder if we don't have file path here, 
    # but let's assume we don't calculate file hash inside this function directly 
    # unless we pass path. The prompt says file_hash of source file. We'll set it in main.
    
    return {
        'total_rows': total_rows,
        'unique_tweet_ids': unique_tweet_ids,
        'duplicate_tweet_ids': {
            'count': len(duplicate_tweet_ids),
            'list': duplicate_tweet_ids
        },
        'root_count': int(root_count),
        'direct_reply_count': int(direct_reply_count),
        'nested_reply_count': int(nested_reply_count),
        'roots_with_direct_replies': int(roots_with_direct_replies),
        'root_relationship_validation': bool(root_relationship_validation),
        'direct_reply_validation': bool(direct_reply_validation),
        'orphan_replies_count': int(orphan_replies),
        'missing_text_count': int(missing_text),
        'reply_per_root_stats': reply_per_root_stats,
        'high_reply_roots': high_reply_roots,
        'language_distribution': language_distribution,
        'source_distribution': source_distribution,
        'hierarchy_distribution': hierarchy_distribution
    }

def validate_dataset_contract(audit: dict) -> list[str]:
    errors = []
    if audit['duplicate_tweet_ids']['count'] > 0:
        errors.append("Dataset contains duplicate Tweet_IDs.")
    if audit['nested_reply_count'] > 0:
        errors.append("Dataset contains nested replies.")
    if audit['orphan_replies_count'] > 0:
        errors.append("Dataset contains orphan replies.")
    if not audit['direct_reply_validation']:
        errors.append("Invalid direct reply relationships found.")
    if not audit['root_relationship_validation']:
        errors.append("Invalid root relationships found.")
    if audit['missing_text_count'] > 0:
        errors.append("Dataset contains missing text.")
    return errors

def print_audit_report(audit: dict) -> None:
    print("=== DATASET AUDIT REPORT ===")
    print(f"Total Rows: {audit['total_rows']}")
    print(f"Unique Tweet IDs: {audit['unique_tweet_ids']}")
    print(f"Duplicates: {audit['duplicate_tweet_ids']['count']}")
    print(f"Roots: {audit['root_count']}")
    print(f"Direct Replies: {audit['direct_reply_count']}")
    print(f"Nested Replies: {audit['nested_reply_count']}")
    print(f"Roots with Replies: {audit['roots_with_direct_replies']}")
    print(f"Root Validation Passed: {audit['root_relationship_validation']}")
    print(f"Direct Reply Validation Passed: {audit['direct_reply_validation']}")
    print(f"Orphan Replies: {audit['orphan_replies_count']}")
    print(f"Missing Text Rows: {audit['missing_text_count']}")
    print(f"High Reply Roots (>=200): {len(audit['high_reply_roots'])}")
    print("============================")

def save_audit_report(audit: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(audit, f, indent=2)
    logging.info(f"Audit report saved to {output_path}")

def get_direct_replies(df: pd.DataFrame) -> pd.DataFrame:
    return df[df['Hierarki_Komentar'] == 'Direct_Reply'].copy()
    mask = df['Hierarki_Komentar'] == 'Direct_Reply'
    return pd.DataFrame(df.loc[mask].copy())

def get_roots(df: pd.DataFrame) -> pd.DataFrame:
    return df[df['Hierarki_Komentar'] == 'Root_Tweet'].copy()
    mask = df['Hierarki_Komentar'] == 'Root_Tweet'
    return pd.DataFrame(df.loc[mask].copy())

def create_annotation_template(df: pd.DataFrame, output_path: Path) -> pd.DataFrame:
    replies = get_direct_replies(df)
    roots = get_roots(df)
    roots_subset = roots[['Tweet_ID', 'Teks_Komentar']].rename(columns={'Tweet_ID': 'Root_Tweet_ID', 'Teks_Komentar': 'Teks_Root'})
    roots_cols = ['Tweet_ID', 'Teks_Komentar']
    roots_subset = pd.DataFrame(roots.loc[:, roots_cols].copy())
    roots_subset.rename(columns={'Tweet_ID': 'Root_Tweet_ID', 'Teks_Komentar': 'Teks_Root'}, inplace=True)
    merged = pd.merge(replies, roots_subset, on='Root_Tweet_ID', how='left')
    
    cols = ['Kategori_Utama', 'Subkategori_Primer', 'Kategori_Sekunder', 
            'Annotation_Status', 'Annotator_1', 'Annotator_2', 
            'Adjudicated_Label', 'Label_Guide_Version']
    for c in cols:
        merged[c] = ''
        
    out_cols = ['Tweet_ID', 'Root_Tweet_ID', 'Teks_Root', 'Teks_Komentar', 
                'Kategori_Utama', 'Subkategori_Primer', 'Kategori_Sekunder', 
                'Annotation_Status', 'Annotator_1', 'Annotator_2', 
                'Adjudicated_Label', 'Label_Guide_Version']
    
    final_df = merged[out_cols]
    final_df = pd.DataFrame(merged.loc[:, out_cols].copy())
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(output_path, index=False, encoding='utf-8-sig', quoting=csv.QUOTE_ALL)
    logging.info(f"Annotation template saved to {output_path}")
    try:
        final_df.to_csv(output_path, index=False, encoding='utf-8-sig', quoting=csv.QUOTE_ALL)
        logging.info(f"Annotation template saved to {output_path}")
    except PermissionError:
        logging.warning(f"File {output_path} is locked by another program. Skipping file overwrite as it already exists.")
    return final_df

if __name__ == '__main__':
    base_dir = Path(__file__).resolve().parent.parent
    config_path = base_dir / 'config' / 'project_config.yaml'
    
    config = {'dataset_path': base_dir.parent / 'output' / 'MBG_Dataset_DirectReplies_20260907_0825.csv'}
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config.update(yaml.safe_load(f) or {})
            
    csv_path = (base_dir / config['dataset_path']).resolve()
    if not csv_path.exists():
        logging.error(f"Dataset not found at {csv_path}")
        raise SystemExit(1)
    
    df = load_dataset(csv_path)
    audit = audit_dataset(df)
    
    with open(csv_path, 'rb') as f:
        audit['file_hash'] = hashlib.sha256(f.read()).hexdigest()
        
    print_audit_report(audit)
    
    errors = validate_dataset_contract(audit)
    if errors:
        for err in errors:
            logging.error(err)
        raise SystemExit(f"Dataset contract validation FAILED with {len(errors)} error(s)")
    else:
        logging.info("Dataset contract validation passed.")
        
    report_path = base_dir / 'reports' / 'dataset_audit.json'
    save_audit_report(audit, report_path)
    
    template_path = base_dir / 'data' / 'annotation_template.csv'
    create_annotation_template(df, template_path)

