from __future__ import annotations

import tempfile
import unittest
import csv
import contextlib
import io
from pathlib import Path

import scraper


class ScraperGuiOptionTests(unittest.TestCase):
    def test_boolean_query_is_not_wrapped_as_one_phrase(self):
        query = scraper.build_search_query('(MBG OR "makan bergizi") AND sekolah')
        self.assertTrue(query.startswith('(MBG OR "makan bergizi") AND sekolah'))
        self.assertTrue(query.endswith("-filter:links -filter:media"))

    def test_keyword_config_preserves_hashtag_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "keywords.txt"
            path.write_text(
                '#MBG\n("makan bergizi" OR "mbg") AND sekolah\n',
                encoding="utf-8",
            )
            self.assertEqual(
                scraper.load_keyword_config(path),
                ["#MBG", '("makan bergizi" OR "mbg") AND sekolah'],
            )

    def test_parse_seed_ids_accepts_urls_and_deduplicates(self):
        self.assertEqual(
            scraper.parse_seed_ids(
                [
                    "1900000000000000001, https://x.com/a/status/1900000000000000002",
                    "1900000000000000001",
                ]
            ),
            ["1900000000000000001", "1900000000000000002"],
        )

    def test_parse_seed_ids_rejects_non_numeric_values(self):
        with self.assertRaisesRegex(ValueError, "tidak valid"):
            scraper.parse_seed_ids(["bukan-id"])

    def test_manual_seed_queue_does_not_fake_durable_seen_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = scraper.Checkpoint(Path(directory) / "checkpoint.json")
            added = scraper.queue_manual_seeds(checkpoint, ["1900000000000000001"])
            self.assertEqual(added, 1)
            self.assertEqual(
                checkpoint.step2_queue,
                {"1900000000000000001": "MANUAL_SEED"},
            )
            self.assertEqual(checkpoint.seen_ids, set())

    def test_resume_rejects_scientific_notation_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "damaged.csv"
            row = {field: "" for field in scraper.CSV_FIELDS}
            row.update(
                Tweet_ID="2.09436E+18",
                Root_Tweet_ID="2.09436E+18",
                Conversation_ID="2.09436E+18",
                Teks_Komentar="MBG",
                Sumber_Akuisisi=scraper.SOURCE_KEYWORD,
                Hierarki_Komentar=scraper.HIERARCHY_ROOT,
            )
            with path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=scraper.CSV_FIELDS)
                writer.writeheader()
                writer.writerow(row)
            with self.assertRaisesRegex(scraper.SchemaMismatchError, "notasi ilmiah"):
                scraper.load_durable_csv_state(path)


class GracefulStopTests(unittest.IsolatedAsyncioTestCase):
    async def test_step1_stops_before_network_call(self):
        class NoNetworkAPI:
            def search(self, *_args, **_kwargs):
                raise AssertionError("network call must not happen")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = scraper.Checkpoint(root / "checkpoint.json")
            csv_path = root / "dataset.csv"
            with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=scraper.CSV_FIELDS)
                writer.writeheader()
                with contextlib.redirect_stdout(io.StringIO()):
                    added = await scraper.step1_collect_roots(
                        api=NoNetworkAPI(),
                        limit=1,
                        lang="in",
                        writer=writer,
                        csv_file=handle,
                        checkpoint=checkpoint,
                        target=10,
                        min_replies=0,
                        delay=0,
                        batch_size=1,
                        stop_requested=lambda: True,
                    )
            self.assertEqual(added, 0)
            self.assertEqual(checkpoint.seen_ids, set())

    async def test_step2_stops_before_network_call(self):
        class NoNetworkAPI:
            def tweet_thread(self, *_args, **_kwargs):
                raise AssertionError("network call must not happen")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = scraper.Checkpoint(root / "checkpoint.json")
            checkpoint.step2_queue = {"1900000000000000001": "MANUAL_SEED"}
            csv_path = root / "dataset.csv"
            with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=scraper.CSV_FIELDS)
                writer.writeheader()
                with contextlib.redirect_stdout(io.StringIO()):
                    added = await scraper.step2_scrape_replies(
                        api=NoNetworkAPI(),
                        lang="in",
                        writer=writer,
                        csv_file=handle,
                        checkpoint=checkpoint,
                        target=10,
                        delay=0,
                        batch_size=1,
                        include_nested=False,
                        stop_requested=lambda: True,
                    )
            self.assertEqual(added, 0)
            self.assertNotIn("1900000000000000001", checkpoint.root_status)


if __name__ == "__main__":
    unittest.main()
