# Rancangan IndoBERT / Transformer untuk ABSA MBG

Status: **rancangan implementasi awal, belum ada model yang dilatih**

## 1. Keputusan desain

Pipeline IndoBERT dipakai untuk membaca konteks kalimat penuh pada komentar
Twitter/X berbahasa Indonesia terkait MBG. Targetnya adalah ABSA, sehingga model
tidak hanya menghasilkan polaritas `Positif` atau `Negatif`, tetapi juga domain
operasional yang sedang dinilai.

Sumbu output:

1. `Kategori_Utama`: `Mutu_Gizi`, `Tata_Kelola`, `Distribusi`.
2. `Sentimen`: `Positif`, `Netral`, `Negatif`.

Kedua sumbu ini harus dipisahkan pada data, model, evaluasi, dan laporan.

## 2. Unit klasifikasi

Unit klasifikasi adalah satu direct reply. `Teks_Root` dipakai sebagai konteks
tambahan ketika tersedia, terutama untuk reply pendek seperti "setuju",
"parah", atau komentar sarkastik yang bergantung pada root tweet.

Format input Transformer yang disarankan:

```text
[CLS] Teks_Root [SEP] Teks_Komentar [SEP]
```

Jika `Teks_Root` tidak tersedia, model memakai `Teks_Komentar` saja.

## 3. Strategi model

Tahap awal yang aman:

1. Validasi dataset berlabel manusia.
2. Split berbasis `Root_Tweet_ID`.
3. Fine-tune IndoBERT untuk `Kategori_Utama`.
4. Fine-tune model terpisah untuk `Sentimen`, atau gunakan multi-head model bila
   kebutuhan implementasinya sudah jelas.
5. Jalankan evaluasi terpisah untuk aspek, sentimen, dan kombinasi aspek x
   sentimen.

Model dasar yang dapat diuji:

- `indobenchmark/indobert-base-p1`
- `indobenchmark/indobert-base-p2`
- model IndoBERT lain yang dipilih eksplisit dan dicatat versinya

Pemilihan model final harus berdasarkan validation set dan final holdout, bukan
popularitas model.

## 4. Label dan subkategori

`Kategori_Utama` mengikuti taksonomi proyek:

- `Mutu_Gizi`
- `Tata_Kelola`
- `Distribusi`

Subkategori tetap dipakai untuk anotasi rinci dan analisis error. Model tahap
pertama tidak wajib memprediksi subkategori, tetapi schema menyiapkan kolomnya.

`Sentimen` berarti sikap terhadap aspek yang dibahas:

- `Positif`: dukungan, kepuasan, apresiasi, atau penilaian baik.
- `Netral`: informatif, bertanya, tidak cukup jelas pro/kontra, atau campuran
  yang tidak dominan.
- `Negatif`: kritik, keluhan, kekecewaan, kekhawatiran, atau penilaian buruk.

## 5. Pencegahan leakage

- Split wajib berdasarkan `Root_Tweet_ID`.
- Satu root tidak boleh ada di train dan validation/test sekaligus.
- Tokenizer, threshold, calibration, dan hyperparameter dipilih tanpa melihat
  final test.
- Near-duplicate lintas root harus diaudit sebelum eksperimen final.
- Metadata seperti username, likes, retweet, dan candidate keyword tidak menjadi
  fitur model.

## 6. Output inferensi

Kolom minimum hasil prediksi:

| Kolom | Isi |
|---|---|
| `Tweet_ID` | ID string |
| `Root_Tweet_ID` | ID root string |
| `Teks_Komentar` | Teks mentah |
| `Kategori_Utama` | Prediksi aspek |
| `Sentimen` | Prediksi polaritas |
| `Confidence` | Skor top prediction aspek |
| `Sentiment_Confidence` | Skor top prediction sentimen bila ada |
| `Prediction_Status` | `ACCEPTED` atau `NEEDS_REVIEW` |
| `Model_Version` | Versi artefak |
| `Predicted_At` | Timestamp inferensi |

CSV harus memakai `utf-8-sig` dan quoting aman.

## 7. Gerbang evaluasi

Model belum boleh disebut akurat atau siap produksi sebelum:

- macro-F1 aspek minimal 0.85;
- recall setiap aspek minimal 0.80;
- balanced accuracy aspek minimal 0.85;
- macro-F1 sentimen minimal 0.85 bila model sentimen dipakai;
- overlap root antar-split nol;
- Cohen's kappa anotasi manusia minimal 0.80;
- model card dan audit error selesai.

Jika syarat gagal, laporkan metrik apa adanya dan perbaiki data, anotasi, atau
setup eksperimen.
