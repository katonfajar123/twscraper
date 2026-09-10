# IndoBERT ABSA MBG

Folder ini berisi rancangan dan scaffold pipeline IndoBERT/Transformer untuk
Aspect-Based Sentiment Analysis (ABSA) komentar Twitter/X berbahasa Indonesia
tentang Program Makan Bergizi Gratis (MBG).

Status: **scaffold awal, belum ada model yang dilatih**.

## Tujuan

- Mengklasifikasikan domain/aspek komentar MBG ke:
  `Mutu_Gizi`, `Tata_Kelola`, atau `Distribusi`.
- Mengklasifikasikan polaritas sentimen sebagai sumbu terpisah:
  `Positif`, `Netral`, atau `Negatif`.
- Memakai konteks kalimat penuh dari `Teks_Komentar` dan, bila tersedia,
  `Teks_Root`, agar lebih cocok untuk teks Twitter yang pendek, implisit, atau
  sarkastik dibanding fitur bag-of-words klasik.

## Struktur

```text
IndoBERT/
├── AGENTS.md
├── DOCUMENTATION.md
├── LABELING_GUIDE_ABSA.md
├── MODEL_CARD.md
├── requirements.txt
├── config/
│   └── label_schema.yaml
├── src/
│   └── indobert_absa/
│       ├── __init__.py
│       ├── data.py
│       ├── predict.py
│       ├── schema.py
│       ├── text.py
│       └── train.py
├── tests/
├── data/
├── reports/
└── artifacts/
```

## Catatan metodologis

ABSA di folder ini tidak mencampur domain dan polaritas. Contoh: komentar
tentang porsi makanan yang buruk adalah `Kategori_Utama=Mutu_Gizi` dan
`Sentimen=Negatif`, sedangkan komentar yang memuji distribusi tepat waktu adalah
`Kategori_Utama=Distribusi` dan `Sentimen=Positif`.

SVM polaritas biner dapat memberi `Positif/Negatif`, tetapi tidak menjawab aspek
operasional mana yang dibicarakan. Karena itu pipeline ini menyiapkan dua tugas:
aspect/domain classification dan sentiment polarity classification.

## Verifikasi cepat

```bash
python -m pytest IndoBERT/tests
```
