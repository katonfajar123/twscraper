from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mbg_gui.main_window import MainWindow


class GuiSmokeTests(unittest.TestCase):
    def test_window_builds_and_scraper_arguments_include_manual_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            window = MainWindow()
            window.withdraw()  # Offscreen / headless
            window.method_combo.setCurrentIndex(1)  # Index 1 is direct reply mode
            window.seed_edit.setPlainText("https://x.com/example/status/1900000000000000001")
            window.output_edit.setText(str(root / "output.csv"))
            window.checkpoint_edit.setText(str(root / "checkpoint.json"))
            window.stop_file = root / "stop.flag"
            arguments = window._scraper_arguments()
            self.assertGreaterEqual(window.tabs.count(), 6)
            self.assertIn("--seed-id", arguments)
            self.assertIn("1900000000000000001", arguments)
            self.assertIn("--stop-file", arguments)
            window.close()

    def test_keyword_mode_uses_editable_gui_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            window = MainWindow()
            window.withdraw()
            window.method_combo.setCurrentIndex(2)  # Index 2 is keyword-only mode
            window.keyword_edit.setPlainText(
                '("MBG" OR "makan bergizi") AND sekolah\nmbg basi'
            )
            window.output_edit.setText(str(root / "keyword.csv"))
            window.checkpoint_edit.setText(str(root / "checkpoint.json"))
            arguments = window._scraper_arguments()
            keyword_values = [
                arguments[index + 1]
                for index, value in enumerate(arguments)
                if value == "--keyword"
            ]
            self.assertEqual(
                keyword_values,
                ['("MBG" OR "makan bergizi") AND sekolah', "mbg basi"],
            )
            window.close()

    def test_keyword_table_deduplicates_and_numbers_rows(self):
        window = MainWindow()
        window.withdraw()
        window.keyword_edit.setPlainText("MBG\nmbg\nmbg basi")
        rows = [
            window.keyword_tree.item(item, "values")
            for item in window.keyword_tree.get_children()
        ]
        self.assertEqual(rows, [("1", "MBG"), ("2", "mbg basi")])
        self.assertEqual(window.keyword_edit.toPlainText(), "MBG\nmbg basi")
        window.close()

    def test_checkpoint_bound_output_is_used_for_resume_and_mismatch_is_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "checkpoint.json"
            bound_output = root / "resume.csv"
            checkpoint.write_text(
                json.dumps(
                    {
                        "seen_ids": ["1900000000000000001"],
                        "done_queries": [],
                        "step2_queue": {},
                        "root_status": {},
                        "output_file": str(bound_output),
                    }
                ),
                encoding="utf-8",
            )

            window = MainWindow()
            window.withdraw()
            self.assertEqual(window._default_scrape_output_path(checkpoint), bound_output)

            window.method_combo.setCurrentIndex(2)
            window.keyword_edit.setPlainText("MBG")
            window.output_edit.setText(str(root / "different.csv"))
            window.checkpoint_edit.setText(str(checkpoint))
            with self.assertRaisesRegex(ValueError, "Checkpoint aktif sudah terikat"):
                window._scraper_arguments()

            window.output_edit.setText(str(bound_output))
            arguments = window._scraper_arguments()
            self.assertIn(str(bound_output), arguments)
            window.close()


if __name__ == "__main__":
    unittest.main()
