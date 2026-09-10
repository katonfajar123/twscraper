from __future__ import annotations

from dataclasses import dataclass

ASPECT_LABELS = ("Mutu_Gizi", "Tata_Kelola", "Distribusi")
SENTIMENT_LABELS = ("Positif", "Netral", "Negatif")
ANNOTATION_STATUSES = ("LABELED", "UNCLEAR", "ADJUDICATED")
PREDICTION_STATUSES = ("ACCEPTED", "NEEDS_REVIEW")

SUBCATEGORIES_BY_ASPECT = {
    "Mutu_Gizi": (
        "Kecukupan_Porsi_dan_Nutrisi",
        "Variasi_dan_Rasa_Menu",
        "Keamanan_Konsumsi",
    ),
    "Tata_Kelola": (
        "Standardisasi_Vendor_dan_Dapur",
        "Transparansi_dan_Efisiensi_Anggaran",
        "Responsivitas_Aduan",
    ),
    "Distribusi": (
        "Ketepatan_Waktu_Logistik",
        "Pemerataan_Jangkauan_3T",
        "Kondisi_Fisik_dan_Pembagian",
    ),
}

ID_COLUMNS = ("Tweet_ID", "Root_Tweet_ID", "Conversation_ID", "In_Reply_To_Tweet_ID")
REQUIRED_SOURCE_COLUMNS = ("Tweet_ID", "Root_Tweet_ID", "Teks_Komentar")
TRAINING_COLUMNS = REQUIRED_SOURCE_COLUMNS + ("Kategori_Utama", "Sentimen")


@dataclass(frozen=True)
class ABSALabel:
    aspect: str
    sentiment: str
    subcategory: str | None = None


def validate_aspect(label: str) -> str:
    if label not in ASPECT_LABELS:
        raise ValueError(f"Invalid aspect label: {label!r}")
    return label


def validate_sentiment(label: str) -> str:
    if label not in SENTIMENT_LABELS:
        raise ValueError(f"Invalid sentiment label: {label!r}")
    return label


def validate_subcategory(aspect: str, subcategory: str) -> str:
    validate_aspect(aspect)
    if subcategory not in SUBCATEGORIES_BY_ASPECT[aspect]:
        raise ValueError(f"Invalid subcategory {subcategory!r} for aspect {aspect!r}")
    return subcategory


def validate_absa_label(label: ABSALabel) -> ABSALabel:
    validate_aspect(label.aspect)
    validate_sentiment(label.sentiment)
    if label.subcategory:
        validate_subcategory(label.aspect, label.subcategory)
    return label
