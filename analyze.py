"""
analyze.py
----------
Baca hasil CSV dari scraper.py dan tampilkan ringkasan statistik sentimen.

Cara pakai:
  python analyze.py --input output/tweets_20241201_120000.csv
  python analyze.py --input output/tweets_20241201_120000.csv --by-group
"""

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


def load_csv(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def print_sentiment_table(rows: list[dict], title: str = "Semua Data") -> None:
    counter = Counter(r["sentiment"] for r in rows)
    total   = len(rows)
    rt      = sum(1 for r in rows if r.get("is_retweet") == "1")
    orig    = total - rt

    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")
    print(f"  Total tweet    : {total:>6,}")
    print(f"  Original       : {orig:>6,}")
    print(f"  Retweet        : {rt:>6,}")
    print(f"  ─────────────────────────")
    for label in ["positif", "negatif", "netral"]:
        n   = counter.get(label, 0)
        pct = (n / total * 100) if total > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"  {label:10s}   : {n:>5,} ({pct:5.1f}%) {bar}")

    # Top keywords
    kw_counter = Counter(r["keyword_matched"] for r in rows)
    print(f"\n  Top 5 keyword:")
    for kw, cnt in kw_counter.most_common(5):
        print(f"    {cnt:>4}x  {kw}")

    # Top users
    user_counter = Counter(r["username"] for r in rows)
    print(f"\n  Top 5 akun paling aktif:")
    for user, cnt in user_counter.most_common(5):
        print(f"    {cnt:>4}x  @{user}")


def main(input_path: str, by_group: bool) -> None:
    path = Path(input_path)
    if not path.exists():
        print(f"[ERROR] File tidak ditemukan: {input_path}")
        return

    rows = load_csv(input_path)
    if not rows:
        print("[ERROR] File CSV kosong.")
        return

    print(f"\n[FILE] {path.resolve()}")
    print_sentiment_table(rows, "RINGKASAN KESELURUHAN")

    if by_group:
        groups: dict[str, list] = defaultdict(list)
        for r in rows:
            groups[r["keyword_group"]].append(r)

        for group_name, group_rows in groups.items():
            print_sentiment_table(group_rows, f"Grup: {group_name}")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analisis sentimen dari hasil CSV scraper")
    parser.add_argument("--input",    required=True, help="Path file CSV hasil scraper")
    parser.add_argument("--by-group", action="store_true", help="Tampilkan breakdown per keyword group")
    args = parser.parse_args()

    main(args.input, args.by_group)
