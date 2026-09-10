# Model Card: MBG IndoBERT ABSA

**STATUS**: MODEL BELUM DILATIH

## Model Details

- **Model Name**: MBG IndoBERT ABSA
- **Base Architecture**: IndoBERT / Transformer encoder
- **Target Task**: Aspect-Based Sentiment Analysis for MBG Twitter/X replies
- **Aspect Labels**: `Mutu_Gizi`, `Tata_Kelola`, `Distribusi`
- **Sentiment Labels**: `Positif`, `Netral`, `Negatif`

## Training Data

- **Status**: Not yet available as finalized human-adjudicated ground truth.
- **Required Unit**: Direct reply with optional root tweet context.
- **Required Split**: Root-grouped train/validation/test split.

## Metrics

- Aspect macro-F1: TBD
- Aspect recall per class: TBD
- Sentiment macro-F1: TBD
- Balanced accuracy: TBD
- Root leakage audit: TBD

## Intended Use

Membantu analisis komentar publik terkait MBG dengan memisahkan domain/aspek
operasional dan polaritas sentimen.

## Limitations

- Belum ada klaim akurasi sampai fine-tuning, holdout evaluation, dan audit
  manual selesai.
- Sarkasme, konteks gambar, tautan berita, dan quote tweet eksternal masih dapat
  menyebabkan salah klasifikasi.
- Model tidak boleh dipakai sebagai satu-satunya dasar keputusan kebijakan tanpa
  review manusia.

## Version History

- `0.1.0`: Scaffold awal IndoBERT ABSA.
