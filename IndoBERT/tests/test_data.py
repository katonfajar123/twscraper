import unittest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import pandas as pd

from indobert_absa.data import prepare_model_inputs, validate_training_frame


class DataTests(unittest.TestCase):
    def test_prepare_model_inputs_preserves_raw_comment(self):
        df = pd.DataFrame(
            {
                "Tweet_ID": ["123"],
                "Root_Tweet_ID": ["10"],
                "Teks_Root": ["Ada laporan makanan telat."],
                "Teks_Komentar": ["Ya ini harus dievaluasi."],
                "Kategori_Utama": ["Distribusi"],
                "Sentimen": ["Negatif"],
            }
        )

        out = prepare_model_inputs(df)

        self.assertEqual(out.loc[0, "Teks_Komentar"], "Ya ini harus dievaluasi.")
        self.assertIn("[SEP]", out.loc[0, "Input_Text"])

    def test_validate_training_frame_detects_duplicate_and_invalid_label(self):
        df = pd.DataFrame(
            {
                "Tweet_ID": ["1", "1"],
                "Root_Tweet_ID": ["r1", "r1"],
                "Teks_Komentar": ["bagus", "buruk"],
                "Kategori_Utama": ["Mutu_Gizi", "Harga"],
                "Sentimen": ["Positif", "Negatif"],
            }
        )

        audit = validate_training_frame(df)

        self.assertEqual(audit["duplicate_tweet_ids"], 1)
        self.assertEqual(audit["invalid_aspects"], ["Harga"])
        self.assertIs(audit["is_valid"], False)

if __name__ == "__main__":
    unittest.main()
