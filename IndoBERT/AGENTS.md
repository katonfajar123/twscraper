# AGENTS.md - IndoBERT

## Scope

Instruksi ini berlaku untuk seluruh isi `IndoBERT/` dan melengkapi
`../AGENTS.md`. Folder ini adalah jalur baru untuk eksperimen Transformer/IndoBERT
dan tidak menggantikan atau menghapus `../NB-Models/`.

## Mission

Bangun pipeline IndoBERT untuk Aspect-Based Sentiment Analysis (ABSA) komentar
Twitter/X berbahasa Indonesia terkait Program Makan Bergizi Gratis (MBG).
Output utama harus memisahkan:

1. `Kategori_Utama`: domain/aspek operasional MBG.
2. `Sentimen`: polaritas sikap terhadap aspek tersebut.

`Kategori_Utama` tetap tepat tiga kelas:

- `Mutu_Gizi`
- `Tata_Kelola`
- `Distribusi`

`Sentimen` adalah sumbu terpisah, default:

- `Positif`
- `Netral`
- `Negatif`

Jangan menyamakan kategori aspek dengan polaritas sentimen.

## Ground Truth and Leakage

- Label final wajib berasal dari anotasi manusia, bukan keyword, lexicon, teacher
  model, engagement, username, atau metadata scraper.
- Jika memakai pseudo-label untuk eksperimen awal, nama file, kolom, dan laporan
  wajib jelas menyebut `pseudo`; hasilnya tidak boleh disebut ground truth.
- Split train, validation, dan test wajib berbasis `Root_Tweet_ID`.
- Satu root tidak boleh muncul di lebih dari satu split.
- `Teks_Root` boleh dipakai sebagai konteks input model, tetapi tidak boleh
  membuat root yang sama bocor lintas split.

## ABSA Contract

- Unit klasifikasi adalah direct reply.
- `Teks_Komentar` mentah wajib dipertahankan.
- Model boleh menerima pasangan `[root context, reply text]`.
- Output inferensi minimal memuat `Tweet_ID`, `Root_Tweet_ID`,
  `Teks_Komentar`, `Kategori_Utama`, `Sentimen`, `Confidence`,
  `Prediction_Status`, `Model_Version`, dan `Predicted_At`.
- Jika model sentimen belum tersedia, isi `Sentimen` boleh dikosongkan dan
  status model harus menyatakan komponen polaritas belum dilatih.

## Evaluation Gates

Model belum boleh disebut siap produksi sebelum final holdout yang belum dipakai
tuning memenuhi:

- macro-F1 aspek minimal 0.85;
- recall setiap aspek minimal 0.80;
- macro-F1 sentimen minimal 0.85 bila head sentimen diaktifkan;
- balanced accuracy minimal 0.85;
- overlap root antar-split sama dengan nol;
- Cohen's kappa anotasi manusia minimal 0.80 untuk aspek dan sentimen;
- audit manual error dan model card selesai.

## Implementation

- Gunakan Python 3.10 atau lebih baru.
- Impor berat seperti `torch` dan `transformers` harus lazy import di fungsi atau
  class yang benar-benar memakainya.
- Test otomatis tidak boleh mengunduh model atau melakukan scraping live.
- Artefak model besar tidak disimpan diam-diam di repository; gunakan `artifacts/`
  dan versi eksplisit bila diperlukan.

## Documentation

- Perubahan di folder ini wajib dicatat pada `../CHANGELOG.md`.
- Dokumentasi tidak boleh mengklaim model sudah dilatih bila artefak dan metrik
  belum tersedia.
