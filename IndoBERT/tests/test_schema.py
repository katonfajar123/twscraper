import unittest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from indobert_absa.schema import (
    ABSALabel,
    ASPECT_LABELS,
    SENTIMENT_LABELS,
    validate_absa_label,
    validate_subcategory,
)


class SchemaTests(unittest.TestCase):
    def test_schema_contains_project_labels(self):
        self.assertEqual(ASPECT_LABELS, ("Mutu_Gizi", "Tata_Kelola", "Distribusi"))
        self.assertEqual(SENTIMENT_LABELS, ("Positif", "Netral", "Negatif"))

    def test_validates_absa_label_pair(self):
        label = ABSALabel(
            aspect="Mutu_Gizi",
            sentiment="Negatif",
            subcategory="Keamanan_Konsumsi",
        )
        self.assertEqual(validate_absa_label(label), label)

    def test_rejects_cross_aspect_subcategory(self):
        with self.assertRaises(ValueError):
            validate_subcategory("Distribusi", "Keamanan_Konsumsi")

if __name__ == "__main__":
    unittest.main()
