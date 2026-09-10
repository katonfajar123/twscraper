# Panduan Anotasi ABSA MBG untuk IndoBERT

Versi: **1.0**

Panduan ini melengkapi `NB-Models/LABELING_GUIDE.md` untuk kebutuhan ABSA.
Anotator memberi dua label independen pada setiap direct reply:

1. `Kategori_Utama`: domain/aspek MBG.
2. `Sentimen`: polaritas terhadap domain/aspek tersebut.

## 1. Urutan anotasi

1. Baca `Teks_Komentar`.
2. Baca `Teks_Root` bila tersedia.
3. Tentukan `Kategori_Utama`: `Mutu_Gizi`, `Tata_Kelola`, atau `Distribusi`.
4. Tentukan `Sentimen`: `Positif`, `Netral`, atau `Negatif`.
5. Isi `Subkategori_Primer` bila skema anotasi memerlukannya.
6. Pilih `Annotation_Status=UNCLEAR` bila aspek tidak dapat diputuskan dengan
   konteks yang ada.

## 2. Aturan aspek

Gunakan definisi aspek dan subkategori dari `NB-Models/LABELING_GUIDE.md`.
Aspek adalah objek pembicaraan, bukan nada atau dukungan.

Contoh:

| Komentar | Kategori_Utama | Sentimen |
|---|---|---|
| "Porsinya cukup dan anak-anak suka." | `Mutu_Gizi` | `Positif` |
| "Dapurnya harus diaudit, rawan main anggaran." | `Tata_Kelola` | `Negatif` |
| "Pengiriman hari ini tepat waktu." | `Distribusi` | `Positif` |
| "Kapan sekolah pelosok mulai dapat?" | `Distribusi` | `Netral` |

Contoh di atas hanya ilustrasi, bukan data training.

## 3. Aturan sentimen

### `Positif`

Gunakan ketika komentar menunjukkan dukungan, kepuasan, apresiasi, atau
penilaian baik terhadap aspek yang dibahas.

### `Netral`

Gunakan ketika komentar bersifat informatif, bertanya, mengutip fakta tanpa
penilaian kuat, atau sikapnya tidak dapat diputuskan walaupun aspek jelas.

### `Negatif`

Gunakan ketika komentar berisi kritik, keluhan, kekhawatiran, kekecewaan,
sindiran negatif, atau penilaian buruk terhadap aspek yang dibahas.

## 4. Sarkasme

Sarkasme diberi label menurut makna pragmatis yang paling masuk akal dari
gabungan reply dan root. Jangan menilai dari emoji atau satu kata saja. Jika
sarkasme terlalu ambigu, gunakan `UNCLEAR` untuk status anotasi.

## 5. Larangan

- Jangan mengisi label dari keyword atau strata sampling.
- Jangan menggunakan prediksi IndoBERT sebagai ground truth.
- Jangan mengubah teks mentah agar label lebih mudah.
- Jangan mencampur `Kategori_Utama` dengan `Sentimen`.
