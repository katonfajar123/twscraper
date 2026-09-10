# AGENTS.md

## Scope

Instruksi ini berlaku untuk seluruh workspace Twitter Scraper MBG. File instruksi yang lebih dekat ke subdirektori boleh menambah atau mengganti aturan hanya untuk cakupan subdirektori tersebut.

## Mission

Kembangkan aplikasi berdasarkan Deskripsi & Tujuan Proyek (FSD - Twitter Scraper MBG).md dengan sasaran utama:

- minimum 20.000 baris tweet atau reply yang unik, relevan dengan MBG, dan rendah spam;
- reply dari banyak root tweet sebagai sumber utama;
- keyword search sebagai perluasan dan top-up target;
- hierarki Direct_Reply dan Nested_Reply dapat ditelusuri;
- GUI desktop tidak freeze ketika scraping berjalan;
- hasil CSV siap dianalisis dan aman dibuka di Excel.

Jangan memenuhi target secara semu dengan membuat data sintetis, menghitung duplikat, menurunkan filter kualitas tanpa persetujuan, atau mengubah checkpoint agar terlihat selesai.

## Mandatory Context Loading

Pada awal setiap pekerjaan, baca konteks yang relevan dengan urutan berikut:

1. Baca AGENTS.md ini.
2. Baca seluruh Deskripsi & Tujuan Proyek (FSD - Twitter Scraper MBG).md.
3. Baca bagian terbaru pada CHANGELOG.md, terutama phase aktif di bawah Unreleased.
4. Baca README.md, manifest dependency, source code, dan test yang berkaitan dengan permintaan.
5. Jika pekerjaan menyentuh scraping, resume, data, ekspor, atau analisis, audit output/checkpoint.json dan CSV terbaru di output/.
6. Periksa perubahan workspace yang sudah ada dan jangan menimpa pekerjaan pengguna yang tidak terkait.

Jangan membaca atau menampilkan isi .env, accounts.txt, token, password, cookie, atau session database kecuali pengguna secara eksplisit meminta pemeriksaan yang memang memerlukannya. Saat hanya memerlukan status akun, ambil metadata minimum tanpa menampilkan rahasia.

## Agentic Execution Loop

Untuk tugas implementasi, jalankan loop berikut sampai Definition of Done tercapai:

1. Observe
   - Pahami permintaan, FSD, kondisi kode, changelog terbaru, dan state data yang relevan.
   - Bedakan fakta hasil inspeksi dari asumsi.
2. Orient
   - Tentukan gap terhadap target dan risiko terhadap data, sesi akun, rate limit, serta kompatibilitas output.
3. Plan
   - Pecah pekerjaan menjadi unit kecil yang dapat diverifikasi.
   - Dahulukan blocker dan correctness sebelum polish.
4. Execute
   - Kerjakan satu unit yang terukur.
   - Pertahankan kompatibilitas data lama bila masuk akal.
5. Verify
   - Jalankan pemeriksaan paling relevan: syntax, unit test, integration test terisolasi, audit CSV, atau smoke test GUI.
   - Jangan menganggap komentar kode atau pesan sukses sebagai bukti.
6. Inspect
   - Periksa diff dan efek samping. Pastikan tidak ada secret, output besar, atau perubahan tidak terkait yang ikut terbawa.
7. Repair
   - Bila verifikasi gagal, cari akar masalah, perbaiki, lalu ulangi dari langkah Verify.
8. Document
   - Setelah implementasi dan verifikasi selesai, tambahkan entry CHANGELOG.md sesuai kebijakan di bawah.
9. Finish
   - Berhenti hanya saat kriteria selesai terpenuhi atau ada blocker nyata yang membutuhkan keputusan atau akses pengguna.

Jangan berhenti pada kegagalan pertama selama masih ada tindakan aman dan relevan. Jangan membuat infinite loop atau busy polling: setiap iterasi wajib menghasilkan perubahan atau bukti baru. Jika blocker yang sama tetap terjadi setelah tiga upaya berbeda yang masuk akal, hentikan loop, simpan state aman, dan laporkan bukti serta kebutuhan keputusan pengguna.

Loop agentic tidak memberikan izin otomatis untuk scraping live, memakai kredensial, mengubah akun, mengirim data, commit, push, atau tindakan destruktif. Tindakan tersebut tetap membutuhkan permintaan pengguna yang sesuai.

## Project Rules

- Gunakan Python 3.10 atau lebih baru.
- Gunakan twscrape sebagai scraping engine dan pertahankan operasi jaringan secara asynchronous.
- Proses scraping tidak boleh berjalan di main UI thread. Gunakan QThread, signal-slot, qasync, atau pemisahan worker yang setara.
- Target menghitung baris yang sudah lolos validasi dan deduplikasi, bukan jumlah response mentah.
- Perlakukan Tweet ID, Root Tweet ID, Conversation ID, dan In-Reply-To ID sebagai string agar presisi ID aman.
- Deduplikasi wajib berdasarkan Tweet_ID sebelum sebuah baris menambah progress target.
- Mode reply wajib mendukung banyak seed Tweet ID.
- Setelah semua seed habis, keyword search hanya menjadi top-up bila target valid belum tercapai.
- Direct_Reply berarti inReplyToTweetId sama dengan target root.
- Nested_Reply berarti conversationId sama dengan target root tetapi inReplyToTweetId berbeda dari target root.
- Dataset wajib mempertahankan teks mentah. Teks bersih boleh menjadi kolom tambahan, bukan pengganti.
- Ekspor CSV wajib menggunakan encoding utf-8-sig dan penanganan quoting yang benar.
- Kegagalan jaringan atau rate limit tidak boleh merusak CSV atau membuat checkpoint lebih maju daripada data yang sudah durable.
- FSD menetapkan pelabelan sentimen otomatis di luar scope scraper. Jangan memperluas fitur sentimen legacy kecuali diminta eksplisit.
- Jangan melakukan live scraping dalam test otomatis. Gunakan fixture, mock, atau sample lokal.
- Jangan mengubah atau menghapus CSV/checkpoint lama kecuali diminta eksplisit.

## Required Dataset Contract

Implementasi akhir sekurang-kurangnya harus dapat menghasilkan:

- Tweet_ID
- Root_Tweet_ID
- Conversation_ID
- In_Reply_To_Tweet_ID
- Waktu_Posting
- Username
- Teks_Komentar
- Jumlah_Likes
- Jumlah_Retweet
- Sumber_Akuisisi
- Hierarki_Komentar

Kolom tambahan diperbolehkan selama arti kolom inti tidak berubah. Dokumentasikan migrasi schema dan kompatibilitas output di changelog.

## CSV Inspection Protocol

Agent boleh dan wajib membaca CSV lokal jika tugas berkaitan dengan data. Untuk CSV besar, audit secara terukur dan jangan menyalin seluruh isi ke percakapan.

Minimal audit CSV:

1. Temukan CSV terbaru berdasarkan LastWriteTime, kecuali pengguna menentukan file.
2. Deteksi header dan encoding; target ekspor adalah utf-8-sig.
3. Hitung jumlah baris fisik dan jumlah Tweet_ID unik.
4. Hitung duplikat Tweet_ID dan baris dengan kolom inti kosong.
5. Ringkas distribusi source atau step, hierarki komentar, bahasa, dan root coverage bila kolom tersedia.
6. Bandingkan jumlah ID CSV dengan seen_ids pada checkpoint.
7. Ambil sampel kecil hanya jika diperlukan untuk memvalidasi relevansi atau parsing.
8. Perlakukan ID sebagai string dan jangan mengonversinya ke angka floating point.

Saat melaporkan audit, tampilkan agregat dan anomali yang bisa ditindaklanjuti. Jangan menampilkan token, cookie, email, password, atau data pribadi yang tidak dibutuhkan. Audit bersifat read-only kecuali pengguna meminta perbaikan atau migrasi data.

## Verification Baseline

Pilih pemeriksaan sesuai perubahan:

- Syntax Python:

      python -m py_compile main.py scraper.py analyze.py keywords.py setup_accounts.py

- Unit/integration test jika tersedia:

      python -m pytest

- CLI smoke test harus memakai input lokal atau mock dan tidak melakukan scraping live tanpa izin.
- GUI smoke test harus memastikan import berhasil, window dapat dibuat, worker tidak memblokir UI, stop bekerja, dan partial export dapat dipanggil.
- Perubahan output wajib disertai fixture CSV kecil untuk memeriksa schema, encoding, quoting, deduplikasi, dan resume durability.

Jika dependency atau test belum tersedia, jangan menyatakan semuanya lolos. Laporkan pemeriksaan yang benar-benar dijalankan dan gap yang tersisa.

## Definition of Done

Pekerjaan baru dianggap selesai jika:

- behavior yang diminta sudah diterapkan;
- implementasi tidak bertentangan dengan FSD atau penyimpangannya dijelaskan;
- verifikasi relevan sudah dijalankan dan hasilnya lulus;
- diff tidak membawa secret atau perubahan tidak terkait;
- dokumentasi yang terkena dampak sudah diperbarui;
- CHANGELOG.md sudah mendapat entry terbaru pada phase aktif;
- response akhir merangkum hasil, verifikasi, dan risiko tersisa secara jujur.

## Change Log Policy

1. Wajib maintain file CHANGELOG.md di root workspace.
2. Setiap perubahan sistem, termasuk fitur, fix, refactor, style, chore, test, build, CI, security, performance, dan docs, wajib dicatat setelah perubahan selesai.
3. Timestamp wajib memakai timezone Asia/Jakarta dengan format [YYYY-MM-DD HH:mm WIB].
4. Gunakan kategori:
   - [FEAT] untuk capability atau behavior baru;
   - [FIX] untuk bug, regression, atau behavior salah;
   - [REFACTOR] untuk perubahan struktur tanpa mengubah behavior produk;
   - [STYLE] untuk visual, layout, copy, atau formatting tanpa perubahan rule;
   - [PERF] untuk peningkatan performa;
   - [SECURITY] untuk hardening atau perbaikan keamanan;
   - [TEST] untuk perubahan test-only;
   - [BUILD] atau [CI] untuk dependency, build, dan pipeline;
   - [CHORE] untuk maintenance operasional; dan
   - [DOCS] untuk dokumentasi-only.
5. Entry wajib menggunakan struktur:

      #### [YYYY-MM-DD HH:mm WIB]
      [KATEGORI] - Ringkasan teknis singkat
      { ISSUE } - Problem awal yang diperbaiki
      { DETAILS CHANGE } - Detail perubahan maksimal 300 karakter

6. Baris { ISSUE } hanya wajib dan hanya digunakan untuk kategori [FIX]. Problem, bug, atau regression awal harus ditulis eksplisit.
7. Baris { DETAILS CHANGE } wajib untuk semua kategori dan maksimal 300 karakter.
8. Struktur phase:

      # CHANGELOG
      ## Unreleased
      ### Phase: <nama fase aktif>
      #### [YYYY-MM-DD HH:mm WIB]
      [KATEGORI] - Ringkasan teknis singkat
      { ISSUE } - Khusus FIX
      { DETAILS CHANGE } - Detail perubahan

9. Entry terbaru ditempatkan paling atas pada phase aktif.
10. Gunakan beberapa entry bila dampaknya berbeda. Jangan menyamarkan fix sebagai chore atau mencampur perubahan tidak terkait.
11. Tulis changelog setelah implementasi selesai tetapi sebelum commit atau push.
12. Jangan mengarang riwayat lama. Catat hanya perubahan yang dapat dibuktikan dari pekerjaan saat ini atau histori repository.
13. Setelah menyelesaikan perubahan, response ke pengguna wajib ditutup dengan kalimat persis:

      ✅ CHANGELOG.md telah diupdate

