# Kamus Normalisasi Slang MBG

Hasil utama: [MBG_Kamus_Slang_Normalisasi_2000.csv](../MBG_Kamus_Slang_Normalisasi_2000.csv).
CSV ini merupakan kamus awal untuk peninjauan sebelum normalisasi komentar.
Tidak ada proses normalisasi, stemming, penghapusan stopword, atau pelabelan
sentimen yang diterapkan pada dataset komentar dalam pekerjaan ini.

## Schema

| Kolom | Arti |
| --- | --- |
| `slang` | Bentuk kata tidak formal yang benar-benar ditemukan di `Content_Cleansing`. |
| `kata_baku` | Padanan normalisasi; bisa berupa satu kata atau beberapa kata. |
| `frekuensi` | Jumlah kemunculan token dalam seluruh 20.000 record CSV sumber. |

Sumber lokal:
`output/MBG_Dataset_DirectReplies_20260907_0825_content_cleansing.csv`.
Ekspor menggunakan delimiter koma, header satu baris, dan encoding `utf-8-sig`.
Ada tepat 2.000 mapping, tanpa slang duplikat, sel kosong, atau mapping identitas.
Semua bentuk slang memiliki frekuensi lebih dari nol di sumber.

## Penyusunan

Kosakata dicocokkan dengan dua leksikon penelitian, dikoreksi pada padanan yang
keliru atau tidak sesuai konteks, dan dilengkapi variasi pengulangan huruf yang
teramati di sumber. Kamus mencakup slang, singkatan, ejaan percakapan, salah ketik,
kata daerah, dan sebagian serapan percakapan. Ini bukan sertifikasi seluruh
padanan menurut KBBI; kata bermakna ganda tetap perlu ditinjau saat kamus dipakai.

Token dihitung dari `Content_Cleansing` dengan pola
`[a-z0-9]+(?:[-'][a-z0-9]+)*`. Pencocokan berdasarkan token utuh, bukan substring.
Angka dalam ejaan seperti `anak2` dipertahankan untuk pencocokan kamus.

Seleksi mengutamakan frekuensi tinggi. Pada frekuensi sama, prioritasnya padanan
koreksi lokal, padanan leksikon, lalu variasi pengulangan huruf lokal. Hasil
ditampilkan menurut frekuensi menurun, kemudian urutan alfabet slang.
Sebanyak 128 kandidat tambahan tidak dimasukkan karena batas 2.000 mapping.
Padanan ganda yang belum diselesaikan disimpan sebagai catatan internal di
`conflicts.json` dan tidak dijadikan penggantian otomatis.

Istilah `mbg`, `bgn`, `sppg`, serta beberapa singkatan ambigu dilindungi.
Contoh koreksi: `mknn` menjadi `makanan`, dan `sulteng` menjadi `sulawesi tengah`.
`dah` tidak dimasukkan karena memiliki penggunaan berbeda di dalam komentar.
Negasi seperti `ga` menjadi `tidak`, bukan dihapus. Teks sasaran tidak distem.

## Sumber Padanan

1. [IndoCollex](https://github.com/haryoa/indo-collex), Wibowo dkk. (2021),
   khususnya [kamus informal-formal](https://github.com/haryoa/indo-collex/blob/main/dict/inforformal-formal-Indonesian-dictionary.tsv).
   Publikasi: [IndoCollex: A Testbed for Morphological Transformation of Indonesian Word Colloquialism](https://aclanthology.org/2021.findings-acl.280/).
   Salinan pemberitahuan lisensi MIT tersedia di `IndoCollex_LICENSE.txt`.
2. [Colloquial Indonesian Lexicon](https://github.com/nasalsabila/kamus-alay),
   Salsabila dkk. (2018), berkas `colloquial-indonesian-lexicon.csv`.
   Publikasi: [Colloquial Indonesian Lexicon](https://doi.org/10.1109/IALP.2018.8629151).

Salinan sumber yang digunakan tersedia di folder ini. URL serta SHA-256 sumber,
dataset input, checkpoint, hasil akhir, dan asal setiap mapping tercatat di
`validation.json`. Penanda `review_local` berarti penyesuaian lokal oleh asisten,
bukan anotasi atau persetujuan manusia. Dataset komentar pengguna tidak dikirim
ke layanan eksternal; akses jaringan hanya mengunduh leksikon rujukan publik.

## Verifikasi

Empat pemeriksaan lokal lulus melalui:

```powershell
python output/slang_mapping_support/verify_mapping.py
```

Pemeriksaan mencakup jumlah dan schema, BOM UTF-8, frekuensi dari korpus,
keunikan slang, padanan contoh, perlindungan istilah domain, tidak ada padanan
yang masih memerlukan penggantian kamus lagi, serta hasil rekonstruksi yang sama.
`fixture_mapping.csv` khusus menguji quoting koma/newline dan penolakan duplikat;
fixture ini bukan bagian dari 2.000 mapping yang diserahkan.

SHA-256 membuktikan kedua dataset lama dan seluruh checkpoint tidak berubah.
Tidak ada perubahan jalur ekspor atau resume scraper; test scraping live tidak
dijalankan. Suite aplikasi lain tidak dijalankan karena perubahan berupa kamus
turunan dan alat verifikasi lokal.

Hasil mencakup 43.631 kemunculan token dalam 13.734 record komentar. Ini adalah
cakupan pencocokan kamus, bukan persentase akurasi bahasa atau normalisasi selesai.
Dataset sumber memiliki 4.098 `Tweet_ID` unik di antara 20.000 record dan tidak
sesuai dengan `seen_ids` checkpoint. Frekuensi menghitung seluruh record, termasuk
duplikat ID yang sudah ada; sumber tidak dideduplikasi atau diubah dalam tugas ini.

Untuk merekonstruksi kandidat tanpa menulis ulang hasil akhir:

```powershell
python output/slang_mapping_support/build_mapping.py
```

Opsi `--build` hanya membuat hasil jika nama file tujuan belum ada. File CSV
final yang sudah ada tidak ditimpa.
