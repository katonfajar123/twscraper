# Rancangan NB-Models untuk Kategorisasi Aspek Program MBG

Status: **rancangan awal, belum ada model yang dilatih**  
Tanggal kajian: **7 September 2026**  
Dataset acuan: `../output/MBG_Dataset_DirectReplies_20260907_0825.csv`

## 1. Keputusan desain utama

Model utama akan mengklasifikasikan komentar ke tepat satu dari tiga kategori
aspek berikut:

1. `Mutu_Gizi`
2. `Tata_Kelola`
3. `Distribusi`

Ketiga kelas tersebut adalah **kategori aspek**, bukan polaritas sentimen.
Apabila penelitian juga memerlukan `Positif`, `Netral`, dan `Negatif`, polaritas
harus dibuat sebagai label/model terpisah. Mencampurkan aspek dan polaritas ke
satu target akan menghasilkan definisi label yang tidak konsisten.

Rekomendasi model awal adalah **Complement Naive Bayes (CNB)** dengan fitur
TF-IDF kata dan karakter. Multinomial Naive Bayes (MNB) tetap wajib diuji sebagai
baseline. Model tidak boleh disebut akurat hanya dari angka accuracy; kelulusan
ditentukan oleh macro-F1, recall setiap kelas, evaluasi antarroots, dan audit
manual terhadap error.

## 2. Tujuan dan batasan

### 2.1 Tujuan

- Mengategorikan direct reply MBG ke satu kategori aspek utama.
- Mempertahankan teks mentah dan relasi reply-root untuk audit.
- Menghasilkan model Naive Bayes yang ringan, cepat, dapat dijelaskan, dan dapat
  direproduksi.
- Menghindari evaluasi yang terlalu optimistis akibat duplikat, pseudo-label,
  atau kebocoran root yang sama ke train dan test.
- Menyediakan status `NEEDS_REVIEW` ketika keyakinan prediksi terlalu rendah,
  tanpa menciptakan kategori bisnis keempat.

### 2.2 Bukan tujuan fase awal

- Model tidak akan dilatih langsung dari label keyword otomatis.
- Akurasi 90% tidak dijanjikan sebelum ground truth dan holdout test tersedia.
- Subkategori sembilan kelas belum menjadi target model pertama.
- Polaritas sentimen tidak akan diturunkan dari kategori aspek.
- Username, jumlah likes, retweet, dan view tidak digunakan sebagai fitur teks.

## 3. Profil dataset yang tersedia

Audit dataset canonical saat rancangan ini dibuat:

| Metrik | Nilai |
|---|---:|
| Baris total unik | 20.000 |
| Root tweet | 2.306 |
| Direct reply | 17.694 |
| Nested reply | 0 |
| Root yang memiliki direct reply pada dataset | 191 |
| Duplikat `Tweet_ID` | 0 |
| Baris dengan kontrak relasi direct yang salah | 0 |

Unit utama pelatihan adalah **17.694 direct reply**. Teks root dipakai sebagai
konteks, bukan sebagai sampel reply tambahan.

Audit sinyal kamus awal pada direct reply, yang hanya berguna untuk sampling dan
bukan ground truth:

| Temuan aturan sederhana | Jumlah |
|---|---:|
| Memuat sinyal `Mutu_Gizi` | 2.328 |
| Memuat sinyal `Tata_Kelola` | 1.394 |
| Memuat sinyal `Distribusi` | 168 |
| Mengenai tepat satu kamus kategori | 3.160 |
| Mengenai lebih dari satu kategori | 360 |
| Tidak mengenai kamus kategori | 14.174 |

Implikasinya: pelabelan berdasarkan keyword saja akan sangat bias, terutama
terhadap `Distribusi`, dan gagal memahami balasan pendek seperti “setuju”,
“parah”, atau “harus dievaluasi”. Konteks root dan anotasi manusia wajib dipakai.

## 4. Taksonomi label

### 4.1 `Mutu_Gizi`

Fokus: isi makanan dan konsekuensinya bagi kecukupan gizi, mutu sensori, serta
keamanan konsumsi.

Subkategori anotasi:

- `Kecukupan_Porsi_dan_Nutrisi`: porsi, kalori, protein, karbohidrat, sayur,
  keseimbangan gizi, rasa kenyang, kesesuaian kebutuhan penerima.
- `Variasi_dan_Rasa_Menu`: variasi menu, rasa, tekstur, pilihan lauk, menu
  monoton, penerimaan makanan oleh siswa.
- `Keamanan_Konsumsi`: basi, busuk, keracunan, kontaminasi, higiene, sanitasi,
  kedaluwarsa, kelayakan makanan untuk dikonsumsi.

Contoh ilustratif:

- “Porsinya terlalu sedikit untuk anak SMP.” → `Mutu_Gizi`
- “Menunya enak tetapi lauknya itu-itu saja.” → `Mutu_Gizi`
- “Makanannya berbau dan beberapa siswa keracunan.” → `Mutu_Gizi`

### 4.2 `Tata_Kelola`

Fokus: aktor, aturan, pembiayaan, pengawasan, dan respons organisasi yang
menyelenggarakan MBG.

Subkategori anotasi:

- `Standardisasi_Vendor_dan_Dapur`: kelayakan SPPG/dapur, seleksi mitra,
  kepatuhan SOP, kapasitas pekerja, sertifikasi, pengawasan vendor.
- `Transparansi_dan_Efisiensi_Anggaran`: sumber dan penggunaan dana, biaya per
  porsi, mark-up, korupsi, audit, akuntabilitas, efisiensi belanja.
- `Responsivitas_Aduan`: kanal pengaduan, tindak lanjut insiden, respons BGN,
  sekolah, vendor atau pemerintah, penyelesaian keluhan.

Contoh ilustratif:

- “Dapur mitra seperti ini kok bisa lolos verifikasi?” → `Tata_Kelola`
- “Rincian anggaran per porsi harus dibuka.” → `Tata_Kelola`
- “Sudah dilaporkan berkali-kali tetapi belum ditindaklanjuti.” → `Tata_Kelola`

### 4.3 `Distribusi`

Fokus: pemindahan, jangkauan, ketepatan penyerahan, dan kondisi paket ketika
makanan dibagikan.

Subkategori anotasi:

- `Ketepatan_Waktu_Logistik`: keterlambatan, jadwal pengiriman, rantai pasok,
  waktu masak-ke-konsumsi, makanan tidak datang.
- `Pemerataan_Jangkauan_3T`: cakupan wilayah, desa/pelosok/perbatasan, daerah
  tertinggal, penerima atau sekolah yang belum terjangkau.
- `Kondisi_Fisik_dan_Pembagian`: kemasan bocor/rusak/tumpah, pembagian tidak
  tertib, jumlah paket saat serah terima, wadah distribusi.

Contoh ilustratif:

- “Datangnya sudah lewat jam makan siang.” → `Distribusi`
- “Sekolah di daerah perbatasan belum kebagian.” → `Distribusi`
- “Kotaknya bocor saat dibagikan.” → `Distribusi`

Semua contoh di atas bersifat ilustratif, bukan data sintetis untuk pelatihan.

## 5. Aturan konflik dan ambiguitas

Anotator memilih kategori dari **sasaran utama keluhan atau penilaian**, bukan
dari satu kata yang kebetulan muncul.

| Kasus tumpang tindih | Label utama | Label sekunder opsional |
|---|---|---|
| Makanan basi karena terlambat dikirim; fokus pada bahaya dimakan | `Mutu_Gizi` | `Distribusi` |
| Makanan basi karena terlambat dikirim; fokus pada jadwal kurir | `Distribusi` | `Mutu_Gizi` |
| Dapur kotor dan tidak bersertifikat; fokus keamanan makanan | `Mutu_Gizi` | `Tata_Kelola` |
| Dapur kotor dan tidak bersertifikat; fokus kelalaian verifikasi mitra | `Tata_Kelola` | `Mutu_Gizi` |
| Anggaran membuat porsi kecil; fokus pemborosan/biaya | `Tata_Kelola` | `Mutu_Gizi` |
| Anggaran membuat porsi kecil; fokus kecukupan makan | `Mutu_Gizi` | `Tata_Kelola` |

Aturan tambahan:

1. Baca `Teks_Komentar` bersama teks root yang dirujuk.
2. Jika satu komentar benar-benar membahas dua aspek, pilih aspek yang memuat
   klaim utama; simpan aspek lain di `Kategori_Sekunder` untuk audit.
3. Jika maksud tidak dapat ditentukan walaupun konteks root dibaca, beri status
   anotasi internal `UNCLEAR`, jangan memaksa salah satu kelas.
4. `UNCLEAR` tidak menjadi output kategori final. Sampel tersebut dipakai untuk
   memperbaiki panduan atau menjadi kasus `NEEDS_REVIEW` saat inferensi.
5. Sarkasme tidak boleh ditentukan hanya dari emoji atau satu kata.

## 6. Skema anotasi yang direncanakan

Kolom minimal ground truth:

| Kolom | Fungsi |
|---|---|
| `Tweet_ID` | Kunci unik; string |
| `Root_Tweet_ID` | Grup percakapan; string |
| `Teks_Root` | Konteks pertanyaan/topik |
| `Teks_Komentar` | Teks mentah yang diklasifikasikan |
| `Kategori_Utama` | Salah satu dari tiga kelas |
| `Subkategori_Primer` | Salah satu dari sembilan subkategori |
| `Kategori_Sekunder` | Opsional untuk kasus tumpang tindih |
| `Annotation_Status` | `LABELED`, `UNCLEAR`, atau `ADJUDICATED` |
| `Annotator_1`, `Annotator_2` | Label independen, bukan identitas pribadi |
| `Adjudicated_Label` | Keputusan akhir saat tidak sepakat |
| `Label_Guide_Version` | Versi aturan anotasi |

Rencana volume:

1. Pilot 300 sampel, ditargetkan sekitar 100 per kelas melalui stratified
   candidate sampling.
2. Dua anotator memberi label secara independen tanpa melihat prediksi model.
3. Revisi panduan sampai Cohen's kappa minimal 0,80 pada label utama.
4. Dataset berlabel awal minimal 3.600 sampel adjudicated, dengan sasaran minimal
   1.000 sampel valid per kelas jika data nyata memungkinkan.
5. Tambahkan kasus sulit melalui active error sampling, bukan hanya sampel yang
   mengandung keyword mudah.

Keyword boleh dipakai untuk menemukan calon sampel kelas langka, tetapi tidak
boleh otomatis dijadikan label akhir.

## 7. Representasi teks dan preprocessing

Dua versi teks selalu dipertahankan:

- `Teks_Komentar`: mentah, tidak ditimpa.
- `Teks_Model`: hasil transformasi deterministik dan berversi.

Urutan eksperimen preprocessing:

1. Unicode normalization dan lowercase.
2. URL → token `URL`; mention → token `USER`.
3. Pertahankan negasi: `tidak`, `bukan`, `belum`, `jangan`, `kurang`, `tanpa`.
4. Pertahankan istilah domain: `MBG`, `SPPG`, `BGN`, `3T`, `SLHS`, `HACCP`.
5. Emoji penting dikonversi menjadi token atau dipertahankan lewat character
   n-gram; jangan langsung dibuang.
6. Normalisasi slang hanya melalui kamus berversi dan dapat diaudit.
7. Bandingkan stemming Sastrawi vs tanpa stemming. Stemming tidak otomatis
   dianggap lebih baik untuk teks pendek dan singkatan.

Fitur kandidat:

- TF-IDF word n-gram `(1, 2)` untuk istilah dan frasa.
- TF-IDF character n-gram `(3, 5)` untuk typo, slang, dan variasi ejaan.
- `min_df`, `max_df`, `sublinear_tf`, dan `max_features` dipilih hanya di data
  training melalui cross-validation.
- Fitur reply dan fitur root dibuat sebagai cabang terpisah. Bobot konteks root
  diuji lebih kecil agar teks root yang berulang tidak mendominasi reply.

## 8. Pencegahan data leakage

Ini adalah persyaratan paling penting untuk klaim akurasi.

1. Split wajib berdasarkan `Root_Tweet_ID`, bukan acak per baris.
2. Root yang muncul di train tidak boleh muncul di validation atau test.
3. Vectorizer, seleksi fitur, resampling, dan kalibrasi hanya di-fit pada train
   fold.
4. Holdout test tidak boleh dipakai memilih alpha, kamus slang, threshold, atau
   aturan label.
5. Near-duplicate lintas root harus dikelompokkan atau dihapus sebelum split.
6. `Keyword_Matched`, username, engagement, dan label aturan tidak menjadi fitur.
7. Teks root yang sama tidak boleh membuat salinan fitur identik bocor ke test.

Split awal yang disarankan:

- 70% root untuk train.
- 15% root untuk validation.
- 15% root untuk final test.
- Tambahan temporal holdout dari root paling baru untuk menguji domain drift.

## 9. Kandidat dan eksperimen model

Urutan eksperimen yang wajib:

| ID | Model | Tujuan |
|---|---|---|
| E0 | Dummy most-frequent/stratified | Batas bawah wajib |
| E1 | Aturan keyword | Mengukur kelemahan weak labeling |
| E2 | Bernoulli NB + binary n-gram | Baseline fitur hadir/tidak hadir |
| E3 | Multinomial NB + TF-IDF | Baseline NB utama |
| E4 | Complement NB + TF-IDF | Kandidat utama untuk kelas tidak seimbang |
| E5 | CNB word + char TF-IDF | Kandidat robust terhadap slang/typo |
| E6 | CNB reply + weighted root context | Kandidat final berbasis konteks |
| Audit | Linear SVC | Pembanding ceiling, bukan pengganti wajib NB |

Grid alpha awal: `0.01, 0.03, 0.1, 0.3, 0.5, 1.0, 2.0`.

SMOTE tidak menjadi default pada matriks TF-IDF sparse. Bila diuji, SMOTE hanya
dijalankan di dalam training fold dan dibandingkan dengan CNB, class-aware
sampling, serta penyesuaian prior. Vector sintetis tidak boleh masuk validation
atau test.

## 10. Evaluasi dan gerbang akurasi

Metrik wajib:

- Macro precision, macro recall, dan macro F1.
- Precision, recall, F1, dan support per kelas.
- Balanced accuracy.
- Confusion matrix absolut dan ternormalisasi.
- Cohen's kappa untuk anotasi manusia.
- Skor per root dan macro-average antarroots agar root viral tidak mendominasi.
- Interval kepercayaan bootstrap 95% pada holdout test.

Gerbang kandidat produksi awal:

- Macro-F1 final test ≥ 0,85.
- Recall setiap kelas ≥ 0,80.
- Balanced accuracy ≥ 0,85.
- Selisih macro-F1 validation dan test ≤ 0,05.
- Tidak ada overlap `Root_Tweet_ID` antar split.
- Audit manual minimal 100 error selesai dan dikategorikan penyebabnya.
- Model card, seed, versi dataset, hash data berlabel, dan parameter tersimpan.

Angka tersebut adalah **kriteria penerimaan**, bukan klaim bahwa model saat ini
sudah mencapainya. Jika gagal, model tidak boleh diberi label “akurat”.

## 11. Confidence dan abstention

Probabilitas Naive Bayes dapat terlalu yakin karena asumsi independensi fitur.
Karena itu:

1. Uji kalibrasi probabilitas pada validation set yang terpisah berdasarkan root.
2. Pilih threshold confidence dan margin top-1 vs top-2 dari validation, bukan
   dari test.
3. Prediksi di bawah threshold tetap menyimpan top prediction, tetapi
   `Prediction_Status=NEEDS_REVIEW`.
4. Laporan agregat utama hanya memakai `ACCEPTED`, atau menampilkan coverage dan
   performa accepted/review secara terpisah.

Output bisnis tetap tiga kelas; `NEEDS_REVIEW` adalah status kualitas, bukan
kategori keempat.

## 12. Kontrak output inferensi

Kolom minimum hasil model:

| Kolom | Isi |
|---|---|
| `Tweet_ID` | ID string sumber |
| `Root_Tweet_ID` | ID string konteks |
| `Teks_Komentar` | Teks mentah |
| `Kategori_Utama` | Tiga kelas aspek |
| `Subkategori_Primer` | Jika model tahap dua tersedia |
| `Confidence` | Skor terkalibrasi atau skor keputusan terdokumentasi |
| `Prediction_Status` | `ACCEPTED` atau `NEEDS_REVIEW` |
| `Model_Version` | Versi artefak |
| `Label_Guide_Version` | Versi definisi label |
| `Predicted_At` | Timestamp inferensi |

CSV hasil tetap menggunakan `utf-8-sig`, quoting yang benar, dan ID string.

## 13. Struktur folder fase implementasi

Saat implementasi dimulai, struktur yang direncanakan:

```text
NB-Models/
├── DOCUMENTATION.md
├── LABELING_GUIDE.md
├── MODEL_CARD.md
├── requirements.txt
├── data/
│   ├── annotation_template.csv
│   └── README.md
├── src/
│   ├── dataset.py
│   ├── preprocess.py
│   ├── train.py
│   ├── evaluate.py
│   └── predict.py
├── artifacts/
├── reports/
└── tests/
```

Artefak model dan salinan dataset besar tidak dibuat pada fase dokumentasi ini.

## 14. Tahapan kerja berikutnya

1. Kunci versi taksonomi dan panduan konflik.
2. Buat `annotation_template.csv` dari direct reply dengan join teks root.
3. Jalankan pilot anotasi 300 baris oleh dua anotator.
4. Ukur agreement dan perbaiki definisi label.
5. Bangun minimal 3.600 ground-truth adjudicated.
6. Bekukan root-group holdout sebelum eksperimen model.
7. Latih E0–E6, pilih model berdasarkan gerbang akurasi.
8. Audit error, confidence, domain drift, dan fairness antarroots.
9. Bekukan artefak dan tulis `MODEL_CARD.md`.
10. Inferensi penuh hanya setelah seluruh gerbang lulus.

## 15. Temuan penelitian terdahulu

Perbandingan angka antarpaper tidak boleh dilakukan tanpa melihat cara labeling,
jumlah kelas, periode, split, dan potensi leakage.

| Penelitian | Data/metode | Temuan yang dilaporkan | Implikasi untuk NB-Models |
|---|---|---|---|
| Chandra & Dewi (2026), Journal of Mathematics UNP | X/MBG, NB, TF-IDF, SMOTE, tiga polaritas | Accuracy terbaik 83,76% pada alpha 0,3 | Alpha perlu dituning; hasil polaritas tidak otomatis berlaku untuk aspek |
| Laia, Hasan, & Kuntoro (2025), Jurnal Ilmiah Informatika | 3.600 tweet; IndoBERT semi-label; NB TF-IDF; dua polaritas | Test accuracy 86,46%; 10-fold mean 86,74% | Label otomatis dapat memperbesar agreement dengan teacher; manual holdout tetap diperlukan |
| Putri & Novianto (2026), JATI | 3.457 tweet; InSet labeling; TF-IDF; NB vs Linear SVM | NB accuracy 91,73%, macro reporting tidak lengkap pada abstrak | Accuracy tinggi belum cukup jika kelas dan root tidak dipisah secara ketat |
| Manao & Mujiyono (2026), Journal of Information Systems and Informatics | 2.903 tweet; TextBlob vs IndoBERT labels; NB dan Linear SVC | Penulis mencatat keterbatasan temporal, platform tunggal, sarkasme, dan bahasa kolokial | Perlu root holdout, temporal holdout, serta manual error audit |
| Pratama (2025), skripsi UMN | Stacking NB, SVM, RF; TF-IDF; SMOTE | Stacking mencapai accuracy 92,98% pada split 90:10 | Menjadi benchmark, tetapi bukan bukti NB tunggal atau aspect model mencapai angka sama |
| Putriyekti et al. (2025), IPSSJ | 242 tweet, 133 setelah proses; manual sentiment dan lima aspek | Memisahkan polaritas dan aspek; pelabelan aspek dilakukan manual | Preseden terdekat untuk desain dua-sumbu aspect + sentiment |
| McCallum & Nigam (1998) | Lima korpus klasifikasi teks | Multinomial NB umumnya lebih baik daripada Bernoulli pada vocabulary besar | MNB wajib menjadi baseline teks |
| Rennie et al. (2003), ICML | Complement/weight-normalized NB | Perbaikan terbesar tampak pada kelas dengan data tidak seimbang | CNB layak menjadi kandidat utama untuk tiga aspek yang timpang |

### Kesenjangan penelitian yang diisi

Literatur MBG yang ditemukan terutama memprediksi polaritas. Penelitian
multidimensional memang memisahkan aspek, tetapi memakai lima aspek umum dan
dataset kecil. Rancangan ini menguji klasifikasi **aspek operasional MBG** dengan
tiga kelas dan sembilan subkategori dari mind map proyek, memakai direct reply,
konteks root, anotasi ganda, serta root-group holdout.

## 16. Landasan domain resmi

Taksonomi proyek selaras dengan dokumen BGN yang memisahkan kebutuhan gizi,
keamanan pangan, tata kelola SPPG, pembiayaan, pengaduan, dan distribusi. Dokumen
resmi digunakan untuk memperjelas istilah anotasi, bukan untuk melabeli tweet
secara otomatis.

## 17. Referensi

1. Chandra, V. D., & Dewi, M. P. (2026). *Analisis Sentimen Terhadap Program
   Makan Bergizi Gratis Pada Media Sosial X Menggunakan Metode Naive Bayes
   Classifier*. Journal of Mathematics UNP, 11(1), 18–28.
   https://doi.org/10.24036/w6zjmv19
2. Laia, M. M., Hasan, F. N., & Kuntoro, A. Y. (2025). *Analisis Sentimen
   Program Makan Gratis pada Platform X Menggunakan Algoritma Naïve Bayes*.
   Jurnal Ilmiah Informatika, 13(2), 258–264.
   https://doi.org/10.33884/jif.v13i02.10427
3. Putri, A. A., & Novianto, D. (2026). *Analisis Sentimen Masyarakat Indonesia
   terhadap Program MBG di Media Sosial X Menggunakan Perbandingan Naive Bayes
   dan SVM*. JATI, 10(3). https://doi.org/10.36040/jati.v10i3.18441
4. Manao, M. F., & Mujiyono, S. (2026). *Sentiment Analysis of the Free
   Nutritious Meal Program on Twitter Using Naive Bayes and IndoBERT-Based
   Labeling*. Journal of Information Systems and Informatics, 8(1).
   https://doi.org/10.63158/journalisi.v8i1.1345
5. Pratama, A. W. (2025). *Analisis Sentimen Program Makan Bergizi Gratis di
   Media Sosial X dengan Stacking Naive Bayes, SVM dan RF* [Skripsi,
   Universitas Multimedia Nusantara].
   https://kc.umn.ac.id/id/eprint/40397/
6. Putriyekti, A., Sulistiawati, D., Khairani, N., & Kusuma, R. R. A. (2025).
   *Analisis Multidimensional Sentimen Masyarakat terhadap Program Makan
   Bergizi Gratis pada Media Sosial X*. Integrative Perspectives of Social and
   Science Journal, 2(1), 1004–1024.
   https://ipssj.com/index.php/ojs/article/download/142/142
7. McCallum, A., & Nigam, K. (1998). *A Comparison of Event Models for Naive
   Bayes Text Classification*. AAAI-98 Workshop on Learning for Text
   Categorization. https://aaai.org/papers/041-ws98-05-007/
8. Rennie, J. D. M., Shih, L., Teevan, J., & Karger, D. R. (2003). *Tackling
   the Poor Assumptions of Naive Bayes Text Classifiers*. ICML 2003.
   https://cdn.aaai.org/ICML/2003/ICML03-081.pdf
9. Badan Gizi Nasional. (2025). *Pedoman Sertifikasi Keamanan Pangan pada
   Satuan Pelayanan Pemenuhan Gizi*.
   https://cdn-web.bgn.go.id/juknis/01KA7MRKDF4HY0J5H008X5Z201.pdf
10. Badan Gizi Nasional. (2025–2026). *Dokumen Petunjuk Teknis BGN*.
    https://www.bgn.go.id/juknis

## 18. Definition of Done fase model

Model baru boleh dinyatakan siap ketika:

- ground truth dibuat oleh minimal dua anotator dan telah di-adjudicate;
- agreement label memenuhi batas yang ditentukan;
- semua split bebas kebocoran root dan near-duplicate;
- gerbang macro-F1, recall per kelas, balanced accuracy, dan stability terpenuhi;
- hasil dapat direproduksi dari konfigurasi, seed, dan hash data yang tersimpan;
- CSV prediksi mempertahankan teks mentah, ID string, dan encoding Excel-safe;
- keterbatasan dan failure modes ditulis jujur di model card.

