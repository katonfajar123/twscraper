from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
