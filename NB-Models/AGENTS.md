# AGENTS.md — NB-Models

## Scope

Instruksi ini berlaku untuk seluruh isi `NB-Models/` dan melengkapi
`../AGENTS.md`. Jika ada konflik, aturan yang lebih ketat tentang integritas
label, evaluasi model, privasi, dan pencegahan data leakage harus diikuti.

## Mission

Bangun pipeline kategorisasi aspek komentar Program Makan Bergizi Gratis (MBG)
yang dapat diaudit dan direproduksi. Target bisnis tetap tepat tiga kategori
utama:

1. `Mutu_Gizi`
2. `Tata_Kelola`
3. `Distribusi`

Sembilan subkategori di `DOCUMENTATION.md` dan `LABELING_GUIDE.md` dipakai
untuk anotasi rinci. Kategori aspek tidak boleh dicampur dengan polaritas
sentimen (`Positif`, `Netral`, `Negatif`).

## Mandatory Context Loading

Sebelum mengubah file di folder ini:

1. Baca `../AGENTS.md`.
2. Baca seluruh `../Deskripsi & Tujuan Proyek (FSD - Twitter Scraper MBG).md`.
3. Baca bagian terbaru `../CHANGELOG.md`, terutama phase aktif di `Unreleased`.
4. Baca seluruh `DOCUMENTATION.md` dan `LABELING_GUIDE.md` jika sudah ada.
5. Baca source, konfigurasi, test, model card, dan laporan yang berkaitan dengan
   pekerjaan.
6. Jika memakai data scraper, audit CSV serta checkpoint terbaru sesuai protokol
   di `../AGENTS.md` tanpa mengubah sumbernya.
7. Periksa perubahan workspace yang sudah ada dan jangan menimpa pekerjaan
   pengguna yang tidak terkait.

Jangan membaca atau menampilkan `.env`, `accounts.txt`, token, cookie, password,
email akun, atau session database untuk pekerjaan model.

## Ground-Truth Policy

- Label final wajib berasal dari keputusan manusia, bukan keyword, lexicon,
  model teacher, engagement, username, atau metadata scraper.
- Keyword hanya boleh membentuk `Candidate_Stratum` untuk memperkaya sampel
  kelas langka. Nama strata tidak boleh disalin menjadi label anotasi.
- Kolom label pada template baru harus kosong.
- Dua anotator bekerja independen dan tidak melihat label satu sama lain sebelum
  tahap adjudikasi.
- Gunakan kode anonim seperti `A1` dan `A2`; jangan simpan identitas pribadi.
- Kasus yang belum dapat diputuskan setelah membaca konteks root diberi status
  internal `UNCLEAR`, bukan dipaksa masuk salah satu kelas.
- Perbedaan anotator wajib di-adjudicate dan alasan keputusan dicatat.
- Contoh buatan hanya boleh menjelaskan pedoman; jangan masukkan contoh buatan
  ke train, validation, atau test.
- Jangan mengklaim ground truth sebelum anotasi ganda dan adjudikasi selesai.

## Dataset Integrity

- Perlakukan `Tweet_ID` dan `Root_Tweet_ID` sebagai string.
- Unit klasifikasi adalah direct reply. `Teks_Root` hanya konteks.
- Pertahankan `Teks_Komentar` mentah; teks preprocessing disimpan di kolom lain.
- Tolak duplikat `Tweet_ID`.
- Jangan mengubah CSV atau checkpoint scraper yang sudah ada.
- Output CSV baru harus memakai `utf-8-sig` dan quoting yang aman.
- Spreadsheet anotasi harus melindungi ID panjang dari pembulatan dan teks dari
  formula injection.
- Simpan provenance minimal: nama file sumber, hash SHA-256, seed sampling,
  timestamp, versi label guide, jumlah baris, jumlah root, serta distribusi
  strata sampling.

## Sampling Rules

- Pilot awal berisi 300 direct reply unik dengan konteks root yang tersedia.
- Sampling harus deterministik dengan seed terdokumentasi.
- Batasi dominasi satu `Root_Tweet_ID` dan laporkan jumlah root unik serta jumlah
  maksimum sampel per root.
- Sertakan komentar tanpa sinyal keyword, kasus overlap, dan kandidat dari semua
  aspek. Tujuannya keragaman, bukan keseimbangan label final.
- Jangan membuang komentar sulit, pendek, sarkastik, atau ambigu hanya untuk
  menaikkan agreement.
- Annotator tidak boleh melihat `Candidate_Stratum` atau keyword pemilih saat
  memberi label.

## Taxonomy Contract

### `Mutu_Gizi`

- `Kecukupan_Porsi_dan_Nutrisi`
- `Variasi_dan_Rasa_Menu`
- `Keamanan_Konsumsi`

### `Tata_Kelola`

- `Standardisasi_Vendor_dan_Dapur`
- `Transparansi_dan_Efisiensi_Anggaran`
- `Responsivitas_Aduan`

### `Distribusi`

- `Ketepatan_Waktu_Logistik`
- `Pemerataan_Jangkauan_3T`
- `Kondisi_Fisik_dan_Pembagian`

Setiap `Subkategori_Primer` harus konsisten dengan `Kategori_Utama`. Label
sekunder bersifat opsional dan tidak menggantikan keputusan label utama.

## Leakage Prevention

- Split train, validation, dan test wajib berdasarkan `Root_Tweet_ID`.
- Satu root tidak boleh muncul di lebih dari satu split.
- Near-duplicate lintas root harus diaudit sebelum split.
- Vectorizer, normalizer, feature selection, resampling, kalibrasi, dan tuning
  hanya di-fit pada training fold.
- Holdout test tidak boleh dipakai memilih preprocessing, alpha, threshold,
  kamus, atau aturan anotasi.
- Bekukan daftar root holdout dan hash ground truth sebelum eksperimen final.
- `Candidate_Stratum`, `Keyword_Matched`, username, engagement, dan keputusan
  aturan tidak boleh menjadi fitur model.

## Model Experiment Contract

- Jalankan dummy baseline sebelum model statistik.
- Uji Bernoulli NB, Multinomial NB, dan Complement NB.
- Kandidat utama adalah Complement NB dengan TF-IDF word dan character n-gram,
  tetapi pilihan akhir harus ditentukan oleh hasil holdout.
- Gunakan root-group cross-validation pada training set.
- SMOTE bukan default untuk TF-IDF sparse. Jika diuji, jalankan hanya di dalam
  training fold dan laporkan dampaknya per kelas.
- Semua seed, parameter, dependency, hash input, dan versi kode harus disimpan.
- Artefak model tidak boleh ditimpa diam-diam; gunakan versi baru.

## Evaluation Gates

Model belum boleh disebut akurat atau siap produksi sebelum seluruh syarat ini
terpenuhi pada final holdout yang belum pernah dipakai tuning:

- macro-F1 minimal 0,85;
- recall setiap kategori minimal 0,80;
- balanced accuracy minimal 0,85;
- gap macro-F1 validation dan test maksimal 0,05;
- overlap root antar-split sama dengan nol;
- Cohen's kappa anotasi label utama minimal 0,80;
- audit manual minimal 100 error selesai;
- interval kepercayaan bootstrap 95%, confusion matrix, performa per kelas, dan
  performa antarroots dilaporkan;
- model card dan failure modes sudah ditulis.

Jika syarat gagal, laporkan metrik apa adanya dan lanjutkan perbaikan data atau
pedoman. Jangan menurunkan gerbang tanpa persetujuan pengguna.

## Confidence and Review

- Probabilitas Naive Bayes tidak dianggap terkalibrasi secara otomatis.
- Threshold dan margin dipilih hanya dari validation set.
- Prediksi berkeyakinan rendah memakai `Prediction_Status=NEEDS_REVIEW`.
- `NEEDS_REVIEW` adalah status kualitas, bukan kategori utama keempat.
- Laporan wajib menyertakan coverage serta performa accepted vs review.

## Implementation and Testing

- Gunakan Python 3.10 atau lebih baru untuk pipeline model.
- Pisahkan modul dataset, preprocessing, training, evaluation, dan inference.
- Fungsi preprocessing harus deterministik, berversi, serta diuji.
- Test tidak boleh melakukan scraping live.
- Gunakan fixture kecil untuk schema, ID string, Unicode, multiline text,
  duplicate detection, group split, dan label-subcategory validation.
- Untuk perubahan data atau model, verifikasi minimal: jumlah baris, ID unik,
  root coverage, distribusi label/status, overlap split, hash, dan reproducibility.
- Untuk spreadsheet, verifikasi dropdown, formula, freeze pane, filter, ID string,
  tampilan lembar, dan ketiadaan formula error sebelum ekspor.

## Documentation and Changelog

- `DOCUMENTATION.md` berisi arsitektur dan landasan metodologis.
- `LABELING_GUIDE.md` menjadi aturan operasional annotator.
- `MODEL_CARD.md` dibuat untuk setiap kandidat final.
- `data/README.md` mencatat provenance dan audit sampel, bukan isi label pribadi.
- Perubahan wajib dicatat pada `../CHANGELOG.md` mengikuti format dan timestamp
  yang ditentukan root `AGENTS.md`.
- Referensi ilmiah harus memakai sumber primer atau publikasi resmi dan tidak
  boleh direkayasa.

## Definition of Done

Pekerjaan di `NB-Models/` selesai hanya jika:

- perilaku atau artefak yang diminta benar-benar tersedia;
- sumber data asli tetap utuh;
- tidak ada pseudo-label yang tersamar sebagai ground truth;
- verifikasi relevan lulus dan hasilnya dicatat;
- provenance cukup untuk mereproduksi hasil;
- tidak ada secret atau data pribadi yang tidak perlu;
- dokumentasi terkait dan `../CHANGELOG.md` telah diperbarui.
