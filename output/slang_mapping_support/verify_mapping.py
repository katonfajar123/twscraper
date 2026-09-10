"""Local-only checks of the mapping artifact and CSV preservation contract."""

import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

import build_mapping as mapping


class MappingChecks(unittest.TestCase):
    def test_fixture_encoding_quoting_and_duplicate_rejection(self):
        fixture = [
            {"slang": "yg", "kata_baku": "yang", "frekuensi": 2},
            {"slang": "yoi", "kata_baku": "iya, betul", "frekuensi": 1},
            {"slang": "makasih", "kata_baku": "terima\nkasih", "frekuensi": 1},
        ]
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=mapping.FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(fixture)
        payload = buffer.getvalue().encode("utf-8-sig")
        path = mapping.HERE / "fixture_mapping.csv"
        if path.exists():
            self.assertEqual(path.read_bytes(), payload)
        else:
            path.write_bytes(payload)
        frequencies = {r["slang"]: r["frekuensi"] for r in fixture}
        parsed = mapping.verify_csv(path, frequencies, 3)
        self.assertEqual(parsed[1]["kata_baku"], "iya, betul")
        self.assertEqual(parsed[2]["kata_baku"], "terima\nkasih")
        with tempfile.TemporaryDirectory() as directory:
            duplicate = Path(directory) / "duplicate.csv"
            with duplicate.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=mapping.FIELDS)
                writer.writeheader()
                writer.writerows(fixture + [fixture[0]])
            with self.assertRaises(AssertionError):
                mapping.verify_csv(duplicate, frequencies, 4)

    def test_output_occurrences_and_schema(self):
        rows, frequencies = mapping.corpus()
        self.assertEqual(len(rows), 20000)
        actual = mapping.verify_csv(mapping.DESTINATION, frequencies, 2000)
        lookup = {r["slang"]: r["kata_baku"] for r in actual}
        for slang, expected in {
            "yg": "yang", "ga": "tidak", "gk": "tidak", "gpp": "tidak apa-apa",
            "mknn": "makanan", "sulteng": "sulawesi tengah", "nggo": "memakai",
            "anak2": "anak-anak", "makasih": "terima kasih",
        }.items():
            self.assertEqual(lookup[slang], expected)
        for protected in ("mbg", "bgn", "sppg", "sma", "smp", "dah", "tf", "diubah"):
            self.assertNotIn(protected, lookup)
        for value in lookup.values():
            for token in mapping.TOKEN.findall(value):
                self.assertNotIn(token, lookup, f"Target still contains a replaceable word: {value}")

    def test_inputs_and_checkpoints_remain_unchanged(self):
        report = json.loads((mapping.HERE / "validation.json").read_text(encoding="utf-8"))
        self.assertEqual(mapping.fingerprint(), report["input_sha256"])

    def test_rebuild_matches_delivered_mapping_without_writing(self):
        _, frequencies = mapping.corpus()
        paths = {
            "indocollex": mapping.HERE / "indocollex.tsv",
            "salsabila": mapping.HERE / "salsabila.csv",
        }
        candidates, _ = mapping.candidates(frequencies, paths)
        expected = mapping.select_mapping(candidates)
        actual = mapping.verify_csv(mapping.DESTINATION, frequencies, 2000)
        self.assertEqual(actual, [{key: str(row[key]) for key in mapping.FIELDS} for row in expected])


if __name__ == "__main__":
    unittest.main(verbosity=2)
