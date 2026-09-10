from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from mbg_gui.data_pipeline import (
    PipelineError,
    PreprocessOptions,
    audit_csv,
    preprocess_csv,
    read_mapping,
    write_mapping,
)


FIELDS = [
    "Tweet_ID",
    "Root_Tweet_ID",
    "Conversation_ID",
    "In_Reply_To_Tweet_ID",
    "Waktu_Posting",
    "Username",
    "Teks_Komentar",
    "Jumlah_Likes",
    "Jumlah_Retweet",
    "Sumber_Akuisisi",
    "Hierarki_Komentar",
    "Bahasa",
]


def write_dataset(path: Path, ids: tuple[str, str] = ("1900000000000000001", "1900000000000000002")) -> None:
    root, reply = ids
    rows = [
        {
            "Tweet_ID": root,
            "Root_Tweet_ID": root,
            "Conversation_ID": root,
            "In_Reply_To_Tweet_ID": "",
            "Waktu_Posting": "2026-09-09T10:00:00+07:00",
            "Username": "akun_root",
            "Teks_Komentar": "Program MBG untuk sekolah",
            "Jumlah_Likes": "1",
            "Jumlah_Retweet": "0",
            "Sumber_Akuisisi": "KEYWORD_SEARCH",
            "Hierarki_Komentar": "Root_Tweet",
            "Bahasa": "in",
        },
        {
            "Tweet_ID": reply,
            "Root_Tweet_ID": root,
            "Conversation_ID": root,
            "In_Reply_To_Tweet_ID": root,
            "Waktu_Posting": "2026-09-09T10:01:00+07:00",
            "Username": "akun_reply",
            "Teks_Komentar": "@bgn mbg gak enak https://t.co/a 🍚\nmasih panas",
            "Jumlah_Likes": "2",
            "Jumlah_Retweet": "0",
            "Sumber_Akuisisi": "REPLY_TWEET_ID",
            "Hierarki_Komentar": "Direct_Reply",
            "Bahasa": "in",
        },
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


class GuiPipelineTests(unittest.TestCase):
    def test_audit_preserves_long_ids_and_compares_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset.csv"
            checkpoint = root / "checkpoint.json"
            write_dataset(dataset)
            checkpoint.write_text(
                json.dumps({"seen_ids": ["1900000000000000001", "1900000000000000002"]}),
                encoding="utf-8",
            )
            result = audit_csv(dataset, checkpoint)
            self.assertTrue(result["contract_ok"])
            self.assertEqual(result["total_rows"], 2)
            self.assertEqual(result["unique_tweet_ids"], 2)
            self.assertTrue(result["utf8_bom"])
            self.assertEqual(result["checkpoint"]["csv_only"], 0)
            self.assertEqual(result["checkpoint"]["checkpoint_only"], 0)

    def test_preprocess_creates_new_quoted_bom_csv_and_keeps_raw(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset.csv"
            mapping = root / "mapping.csv"
            output = root / "processed.csv"
            write_dataset(dataset)
            write_mapping(
                mapping,
                [{"slang": "gak", "kata_baku": "tidak", "frekuensi": "1"}],
            )
            result = preprocess_csv(
                dataset,
                output,
                mapping_path=mapping,
                options=PreprocessOptions(),
            )
            self.assertEqual(result["rows"], 2)
            self.assertTrue(output.read_bytes().startswith(b"\xef\xbb\xbf"))
            with output.open("r", newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(
                rows[1]["Teks_Komentar"],
                "@bgn mbg gak enak https://t.co/a 🍚\nmasih panas",
            )
            self.assertEqual(
                rows[1]["Content_Cleansing"],
                "user mbg gak enak url 🍚 masih panas",
            )
            self.assertEqual(
                rows[1]["Content_Normalisasi"],
                "user mbg tidak enak url 🍚 masih panas",
            )
            self.assertEqual(rows[1]["Tweet_ID"], "1900000000000000002")

    def test_preprocess_rejects_scientific_ids_and_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "damaged.csv"
            output = root / "processed.csv"
            write_dataset(dataset, ids=("2.09436E+18", "2.09437E+18"))
            audit = audit_csv(dataset)
            self.assertEqual(audit["scientific_notation_ids"], 2)
            with self.assertRaisesRegex(PipelineError, "notasi ilmiah"):
                preprocess_csv(
                    dataset,
                    output,
                    options=PreprocessOptions(normalize_slang=False),
                )
            self.assertFalse(output.exists())

    def test_mapping_validation_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            mapping = Path(directory) / "mapping.csv"
            with self.assertRaisesRegex(PipelineError, "duplikat"):
                write_mapping(
                    mapping,
                    [
                        {"slang": "gak", "kata_baku": "tidak", "frekuensi": "1"},
                        {"slang": "GAK", "kata_baku": "bukan", "frekuensi": "1"},
                    ],
                )
            self.assertFalse(mapping.exists())

    def test_mapping_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            mapping = Path(directory) / "mapping.csv"
            write_mapping(
                mapping,
                [{"slang": "yoi", "kata_baku": "iya, betul", "frekuensi": "3"}],
            )
            self.assertEqual(
                read_mapping(mapping),
                [{"slang": "yoi", "kata_baku": "iya, betul", "frekuensi": "3"}],
            )


if __name__ == "__main__":
    unittest.main()
