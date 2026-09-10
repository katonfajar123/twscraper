# Panduan Operasional Anotasi Aspek MBG

Versi: **1.0**  
Berlaku mulai: **7 September 2026**  
Unit anotasi: **satu direct reply dengan konteks root tweet**

## 1. Tujuan panduan

Panduan ini dipakai oleh dua anotator manusia untuk membuat ground truth
kategorisasi aspek komentar Program Makan Bergizi Gratis (MBG). Setiap komentar
yang dapat diputuskan memperoleh tepat satu `Kategori_Utama` dan satu
`Subkategori_Primer`.

Tiga label utama adalah aspek pembicaraan, bukan sikap atau polaritas. Komentar
positif, netral, dan negatif dapat masuk kategori aspek yang sama.

## 2. Urutan kerja annotator

Untuk setiap baris:

1. Baca `Teks_Komentar` sampai selesai.
2. Baca `Teks_Root` untuk memahami rujukan, terutama pada balasan pendek,
   pronomina, elipsis, ironi, atau kalimat seperti “setuju” dan “parah”.
3. Tentukan sasaran utama klaim: isi/keamanan makanan, penyelenggara/anggaran,
   atau proses pengiriman/pembagian.
4. Pilih satu `Kategori_Utama`.
5. Pilih satu `Subkategori_Primer` yang berada di bawah kategori tersebut.
6. Isi `Kategori_Sekunder` hanya jika dua aspek benar-benar substansial.
7. Pilih `Annotation_Status=LABELED` bila keputusan cukup jelas.
8. Pilih `Annotation_Status=UNCLEAR` bila makna tetap tidak dapat dipastikan
   setelah konteks root dibaca. Kosongkan kategori dan subkategori.
9. Tulis `Alasan_Singkat` untuk kasus overlap, sarkasme, atau `UNCLEAR`.

Jangan melihat lembar atau hasil annotator lain sebelum tahap adjudikasi.

## 3. Pertanyaan keputusan cepat

Gunakan urutan berikut, bukan pencocokan satu keyword:

1. Apakah inti komentar menilai **apa yang dimakan** atau dampaknya bagi
   penerima? Pilih `Mutu_Gizi`.
2. Jika tidak, apakah inti komentar menilai **siapa yang mengelola, aturan,
   dana, pengawasan, atau tindak lanjut**? Pilih `Tata_Kelola`.
3. Jika tidak, apakah inti komentar menilai **kapan, ke mana, atau dalam kondisi
   apa paket sampai dan dibagikan**? Pilih `Distribusi`.
4. Jika dua jawaban sama kuat, pilih klaim yang paling ditegaskan sebagai label
   utama dan simpan aspek lain sebagai sekunder.
5. Jika tidak ada keputusan yang dapat dipertanggungjawabkan, pilih `UNCLEAR`.

## 4. Definisi label utama dan subkategori

### 4.1 `Mutu_Gizi`

Gunakan ketika fokus komentar adalah isi makanan, kecukupan konsumsi, kualitas
sensori, atau keamanan pangan bagi penerima.

#### `Kecukupan_Porsi_dan_Nutrisi`

Termasuk:

- porsi terlalu sedikit/banyak;
- kenyang atau tidak kenyang;
- protein, kalori, karbohidrat, sayur, buah, dan keseimbangan gizi;
- kesesuaian menu dengan usia atau kebutuhan penerima;
- kandungan gizi dan manfaat nutrisi.

Tidak termasuk:

- harga atau anggaran per porsi sebagai fokus utama → `Tata_Kelola`;
- jumlah paket yang kurang saat pembagian → `Distribusi`.

#### `Variasi_dan_Rasa_Menu`

Termasuk:

- rasa enak/hambar/asin/manis;
- menu monoton atau bervariasi;
- tekstur, aroma non-busuk, pilihan lauk, dan penerimaan siswa;
- penampilan atau komposisi menu sebagai pengalaman makan.

Tidak termasuk:

- aroma busuk, makanan basi, atau risiko sakit → `Keamanan_Konsumsi`;
- kemasan rusak saat pengiriman → `Distribusi`.

#### `Keamanan_Konsumsi`

Termasuk:

- basi, busuk, berjamur, kedaluwarsa;
- keracunan, mual, diare, kontaminasi;
- higiene, sanitasi, suhu aman, benda asing;
- makanan layak atau tidak layak dikonsumsi.

Fokus pada bahaya yang diterima konsumen tetap `Mutu_Gizi`, walaupun penyebab
yang disebut adalah dapur atau keterlambatan.

### 4.2 `Tata_Kelola`

Gunakan ketika fokus komentar adalah aktor penyelenggara, standar, aturan,
pengawasan, pembiayaan, akuntabilitas, atau respons organisasi.

#### `Standardisasi_Vendor_dan_Dapur`

Termasuk:

- seleksi dan kelayakan vendor/SPPG/dapur;
- kepatuhan SOP, sertifikasi, inspeksi, kapasitas pekerja;
- pengawasan mitra dan kualitas proses produksi;
- pertanyaan mengapa penyedia tertentu dapat lolos verifikasi.

Jika fokusnya makanan berbahaya bagi siswa, gunakan `Keamanan_Konsumsi`. Jika
fokusnya kegagalan verifikasi atau kontrol penyedia, gunakan subkategori ini.

#### `Transparansi_dan_Efisiensi_Anggaran`

Termasuk:

- penggunaan dana dan biaya per porsi;
- mark-up, korupsi, pemborosan, audit;
- transparansi kontrak dan akuntabilitas belanja;
- perbandingan biaya dengan hasil program.

Jika inti komentar adalah porsi kecil yang diterima siswa, pilih
`Kecukupan_Porsi_dan_Nutrisi`. Jika inti komentar adalah dana yang tidak wajar,
pilih subkategori ini.

#### `Responsivitas_Aduan`

Termasuk:

- kanal pengaduan dan pelaporan;
- cepat/lambatnya tindak lanjut pemerintah, BGN, sekolah, atau vendor;
- penanganan insiden dan penyelesaian keluhan;
- respons komunikasi setelah masalah terjadi.

Keluhan umum “program harus dievaluasi” tanpa aktor, proses aduan, atau objek
yang jelas dapat menjadi `UNCLEAR`.

### 4.3 `Distribusi`

Gunakan ketika fokus komentar adalah pengiriman, waktu penyerahan, cakupan
penerima, kondisi paket dalam perjalanan, atau proses pembagian.

#### `Ketepatan_Waktu_Logistik`

Termasuk:

- makanan terlambat atau tidak datang;
- jadwal pengiriman dan rantai pasok;
- jarak waktu masak hingga konsumsi;
- gangguan kendaraan atau kurir sebagai inti masalah.

Jika keterlambatan hanya menjelaskan makanan menjadi berbahaya dan fokusnya
risiko konsumsi, pilih `Keamanan_Konsumsi`.

#### `Pemerataan_Jangkauan_3T`

Termasuk:

- sekolah, desa, pulau, pelosok, perbatasan, atau daerah 3T belum terjangkau;
- pemerataan antarwilayah;
- kelompok penerima yang terlewat karena cakupan distribusi.

Pernyataan umum tentang ketidakadilan anggaran bukan subkategori ini kecuali
jelas membahas jangkauan penyaluran.

#### `Kondisi_Fisik_dan_Pembagian`

Termasuk:

- kotak/kemasan bocor, rusak, terbuka, atau tumpah dalam penyaluran;
- jumlah paket kurang saat serah terima;
- antrean, urutan, atau mekanisme pembagian;
- paket tertukar atau tidak sampai kepada penerima yang semestinya.

Jika keluhan hanya menyangkut rasa atau kualitas isi tanpa proses pembagian,
pilih `Mutu_Gizi`.

## 5. Aturan konflik

| Situasi | Kategori utama | Kategori sekunder |
|---|---|---|
| Terlambat membuat makanan basi; fokus bahaya dimakan | `Mutu_Gizi` | `Distribusi` |
| Terlambat membuat makanan basi; fokus jadwal kurir | `Distribusi` | `Mutu_Gizi` |
| Dapur kotor; fokus potensi keracunan | `Mutu_Gizi` | `Tata_Kelola` |
| Dapur kotor; fokus vendor lolos tanpa inspeksi | `Tata_Kelola` | `Mutu_Gizi` |
| Anggaran besar tetapi porsi kecil; fokus pemborosan | `Tata_Kelola` | `Mutu_Gizi` |
| Anggaran besar tetapi porsi kecil; fokus anak tidak kenyang | `Mutu_Gizi` | `Tata_Kelola` |
| Kotak bocor dan isi tercemar; fokus kondisi paket saat dibagi | `Distribusi` | `Mutu_Gizi` |
| Kotak bocor dan isi tercemar; fokus makanan tidak aman | `Mutu_Gizi` | `Distribusi` |

Label sekunder tidak wajib. Jangan mengisi label sekunder hanya karena teks root
menyinggung aspek lain; aspek tersebut harus juga menjadi bagian substansial
dari komentar.

## 6. Aturan konteks, sarkasme, dan teks pendek

- Label ditentukan dari gabungan makna reply dan root, tetapi objek penilaian
  pada reply mendapat bobot utama.
- “Setuju”, “betul”, “parah”, atau emoji saja mengikuti aspek root hanya jika
  rujukannya tunggal dan tidak ambigu.
- Jika root memuat beberapa isu dan reply tidak menunjukkan isu mana yang
  dirujuk, pilih `UNCLEAR`.
- Sarkasme diberi label berdasarkan makna pragmatis yang cukup kuat, bukan arti
  literal satu kata.
- Hashtag tidak otomatis menentukan label.
- Mention, URL, nama akun, jumlah likes, dan popularitas tidak memengaruhi label.
- Pendapat pro/kontra terhadap MBG secara umum tanpa aspek operasional yang
  dapat dipetakan diberi `UNCLEAR`.

## 7. Status anotasi

### `LABELED`

Gunakan bila kategori dan subkategori dapat dipilih dengan alasan yang masuk
akal. Wajib mengisi `Kategori_Utama` dan `Subkategori_Primer`.

### `UNCLEAR`

Gunakan bila makna masih ambigu, konteks root tidak cukup, reply di luar topik,
atau tidak membahas salah satu dari tiga aspek. Kosongkan kategori utama,
subkategori, dan kategori sekunder; jelaskan penyebab singkat.

`UNCLEAR` adalah status kerja internal, bukan kelas model keempat.

### `ADJUDICATED`

Status ini hanya muncul setelah reviewer memutuskan perbedaan annotator. Hasil
adjudikasi harus memiliki kategori/subkategori final atau keputusan final
`UNCLEAR` dengan catatan.

## 8. Pemeriksaan konsistensi wajib

Pasangan valid:

| Kategori utama | Subkategori yang diizinkan |
|---|---|
| `Mutu_Gizi` | `Kecukupan_Porsi_dan_Nutrisi`; `Variasi_dan_Rasa_Menu`; `Keamanan_Konsumsi` |
| `Tata_Kelola` | `Standardisasi_Vendor_dan_Dapur`; `Transparansi_dan_Efisiensi_Anggaran`; `Responsivitas_Aduan` |
| `Distribusi` | `Ketepatan_Waktu_Logistik`; `Pemerataan_Jangkauan_3T`; `Kondisi_Fisik_dan_Pembagian` |

Sebelum menyerahkan satu batch, annotator memeriksa:

- tidak ada `LABELED` tanpa kategori atau subkategori;
- tidak ada `UNCLEAR` yang masih memiliki kategori;
- semua subkategori konsisten dengan kategori utama;
- tidak ada perubahan pada `Tweet_ID`, `Root_Tweet_ID`, `Teks_Root`, atau
  `Teks_Komentar`;
- kode annotator terisi dan tidak berisi nama/email pribadi.

## 9. Protokol pilot 300

1. Annotator A1 dan A2 menerima salinan baris yang sama.
2. Keduanya mengisi label secara independen.
3. Koordinator menghitung agreement dan Cohen's kappa pada label utama yang
   lengkap.
4. Semua perbedaan, semua `UNCLEAR`, dan sampel konflik dipelajari bersama.
5. Reviewer mengisi lembar `Adjudikasi` tanpa mengubah keputusan asli A1/A2.
6. Panduan direvisi jika pola kesalahan berasal dari definisi, bukan kelalaian.
7. Pilot dianggap cukup stabil bila Cohen's kappa label utama minimal 0,80.
8. Pilot yang sudah adjudicated boleh menjadi bagian ground truth; versi sebelum
   adjudikasi tidak boleh langsung menjadi data training.

## 10. Larangan bias dan pseudo-label

- Jangan menebak label dari strata sampling atau daftar keyword.
- Jangan melihat prediksi Naive Bayes, model lain, atau label lexicon.
- Jangan menyamakan frekuensi kelas dalam pilot dengan prevalensi populasi.
- Jangan menghapus kasus sulit untuk mempercantik kappa.
- Jangan memberi label berdasarkan siapa yang menulis komentar.
- Jangan mengubah teks agar lebih mudah diklasifikasikan.
- Jangan menggunakan contoh ilustratif dalam panduan sebagai data training.

## 11. Contoh ilustratif

Contoh berikut dibuat untuk menjelaskan keputusan dan **bukan data training**:

| Komentar ilustratif | Keputusan |
|---|---|
| “Proteinnya kurang untuk anak seusia itu.” | `Mutu_Gizi` / `Kecukupan_Porsi_dan_Nutrisi` |
| “Setiap hari lauknya sama dan rasanya hambar.” | `Mutu_Gizi` / `Variasi_dan_Rasa_Menu` |
| “Baunya sudah asam, jangan dibagikan.” | `Mutu_Gizi` / `Keamanan_Konsumsi` |
| “Vendor tanpa sertifikat kok lolos?” | `Tata_Kelola` / `Standardisasi_Vendor_dan_Dapur` |
| “Buka rincian biaya per porsinya.” | `Tata_Kelola` / `Transparansi_dan_Efisiensi_Anggaran` |
| “Sudah dilaporkan tetapi belum ditindaklanjuti.” | `Tata_Kelola` / `Responsivitas_Aduan` |
| “Datang setelah jam sekolah selesai.” | `Distribusi` / `Ketepatan_Waktu_Logistik` |
| “Sekolah di perbatasan belum terjangkau.” | `Distribusi` / `Pemerataan_Jangkauan_3T` |
| “Kotaknya tumpah saat dibagikan.” | `Distribusi` / `Kondisi_Fisik_dan_Pembagian` |
| “Mantap sekali programnya.” tanpa konteks aspek | `UNCLEAR` |

## 12. Eskalasi perubahan panduan

Annotator tidak boleh membuat aturan baru sendiri. Catat kasus yang tidak
tercakup, diskusikan setelah batch selesai, lalu revisi versi panduan secara
eksplisit. Setiap perubahan definisi harus diikuti:

- nomor versi baru;
- daftar kasus yang terpengaruh;
- keputusan apakah label lama perlu diaudit ulang;
- pembaruan dokumentasi dan changelog.
