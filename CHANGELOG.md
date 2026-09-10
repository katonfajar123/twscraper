# CHANGELOG

## Unreleased

### Phase: Agentic Foundation

#### [2026-09-10 13:32 WIB]
[FEAT] - Mengubah input keyword scraping menjadi tabel editable
{ DETAILS CHANGE } - Tab Ekstraksi kini memakai tabel keyword dengan tambah/edit/hapus/naik/turun, preset dan file load/save tetap didukung, serta setiap baris dikirim sebagai --keyword.

#### [2026-09-10 13:32 WIB]
[FIX] - Menyamakan default CSV GUI dengan output_file checkpoint aktif
{ ISSUE } - GUI membuat nama CSV baru saat checkpoint lama berisi 1.970 data durable, sehingga scraper gagal karena checkpoint terikat ke output berbeda.
{ DETAILS CHANGE } - GUI membaca output_file dari checkpoint aktif untuk resume dan memvalidasi mismatch CSV/checkpoint sebelum subprocess dijalankan.

#### [2026-09-10 13:13 WIB]
[FEAT] - Membuka pengaturan keyword scraping dari GUI dan file config
{ DETAILS CHANGE } - Menambah config/scraping_keywords.txt, preset grup keyword, tombol muat/simpan keyword di tab Ekstraksi, dan default CLI membaca file config saat --keyword kosong.

#### [2026-09-09 20:15 WIB]
[STYLE] - Mengubah tampilan Tkinter ke tema biru klasik
{ DETAILS CHANGE } - Palette GUI dipindah ke biru terang ala mobile banking, header dibuat biru solid, tombol/progress/log diselaraskan, dan emoji icon di tab, tombol, panel, status, serta laporan UI dihapus.

#### [2026-09-09 16:49 WIB]
[FEAT] - Menambahkan launcher satu-klik `Jalankan MBG Studio.bat`
{ DETAILS CHANGE } - File .bat otomatis memeriksa Python, menginstall dependensi dari requirements.txt jika belum ada, dan menjalankan main.py; pengguna cukup double-klik tanpa perlu terminal.

#### [2026-09-09 16:48 WIB]
[FEAT] - Membangun GUI desktop native Tkinter ramah pengguna awam
{ DETAILS CHANGE } - Mengganti GUI ke Tkinter native tanpa dependensi Qt; menyediakan 7 tab ramah pemula (Beranda, Akun, Ekstraksi, Audit, Preprocessing, Kamus Slang, Rencana NLP), thread aman anti-freeze, stop flag, dan editor kamus.

#### [2026-09-09 16:48 WIB]
[TEST] - Memverifikasi inisialisasi Tkinter GUI dan argumen scraper
{ DETAILS CHANGE } - Mengadaptasi test_gui_smoke untuk menguji MainWindow Tkinter secara offscreen, validasi argumen seed/stop-file, dan verifikasi tab notebook; 28 test unittest lulus.
[TEST] - Menambah verifikasi GUI, opsi scraper, audit, mapping, dan preprocessing
{ DETAILS CHANGE } - Menambah 13 test lokal tanpa scraping live untuk window offscreen, seed/Boolean query, stop sebelum network, long ID, checkpoint, BOM+quoting, raw text, mapping duplikat, normalisasi, dan penolakan ID ilmiah; total 28 test lulus.

#### [2026-09-09 14:16 WIB]
[DOCS] - Mendokumentasikan alur GUI dan perlindungan data
{ DETAILS CHANGE } - README memuat instalasi, enam tab, setup cookie, stop aman, opsi seed/query CLI, kontrak preprocessing, editor mapping save-as, perlindungan ID panjang, dan batas pemisahan model sentimen/aspek.

#### [2026-09-09 14:16 WIB]
[FIX] - Menolak resume dan preprocessing pada Tweet ID notasi ilmiah
{ ISSUE } - CSV dapat disimpan ulang oleh spreadsheet menjadi notasi ilmiah, merusak presisi dan membuat checkpoint tidak lagi cocok dengan baris durable.
{ DETAILS CHANGE } - Audit mendeteksi ID ilmiah/duplikat dan mismatch checkpoint; scraper kini menghentikan reconcile bila kolom ID bukan digit utuh agar checkpoint tidak diturunkan ke state CSV yang sudah rusak.

#### [2026-09-09 14:16 WIB]
[FEAT] - Menambahkan pipeline audit, cleansing, normalisasi, dan editor mapping
{ DETAILS CHANGE } - Menambah audit CSV+checkpoint, validasi relasi, preview 200 record, copy cell, ekspor salinan, transformasi non-destruktif ke dua kolom baru, opsi URL/mention/emoji/tanda baca, serta mapping slang tervalidasi dan atomik.

#### [2026-09-09 14:16 WIB]
[FEAT] - Menambahkan desktop GUI MBG Scraper Studio
{ DETAILS CHANGE } - PyQt6 enam tab mencakup onboarding, cookie account pool, hybrid/keyword/multi-seed extraction via QProcess, progress/log live, stop-file durable, monitor tabel, preprocessing worker QThread, dan tema desktop; main.py/app.py menjadi launcher.

#### [2026-09-08 21:46 WIB]
[CHORE] - Menyusun kamus normalisasi slang MBG berisi 2.000 mapping
{ DETAILS CHANGE } - CSV utf-8-sig berkolom slang, kata_baku, frekuensi; seluruh slang muncul di Content_Cleansing. Padanan leksikon dikoreksi sesuai konteks, istilah MBG dilindungi. Empat cek lokal lulus; komentar dan checkpoint tetap utuh, normalisasi belum diterapkan.

#### [2026-09-08 21:21 WIB]
[CHORE] - Membuat CSV turunan dengan kolom Content_Cleansing
{ DETAILS CHANGE } - Menambah output direct reply baru berisi 20.000 record asli plus kolom cleansing setelah Teks_Komentar; raw text dipertahankan, utf-8-sig, URL, mention, emoji/emoticon dihapus, lowercase.

#### [2026-09-08 08:26 WIB]
[FEAT] - Menambahkan scaffold IndoBERT ABSA untuk komentar MBG
{ DETAILS CHANGE } - Membuat folder IndoBERT terpisah dari NB-Models dengan schema aspek+sentimen, dokumentasi ABSA, model card, requirements Transformer, modul data/predict/train, dan test ringan tanpa download model.

#### [2026-09-07 11:02 WIB]
[DOCS] - Merancang NB-Models untuk klasifikasi tiga aspek MBG
{ DETAILS CHANGE } - Menambah dokumentasi taksonomi Mutu Gizi, Tata Kelola, dan Distribusi; anotasi, root-group split, pipeline MNB/CNB, gerbang akurasi, output, roadmap, kajian jurnal/skripsi, pedoman BGN, serta tautan README.

#### [2026-09-07 10:32 WIB]
[CHORE] - Menyelesaikan live scrape direct reply hingga 20.000 baris
{ DETAILS CHANGE } - Akun kedua menambah 17.694 direct reply dari 191 root coverage. CSV final berisi 20.000 ID unik, 0 nested, relasi valid, utf-8-sig, dan checkpoint sinkron; akun lama logged-out dinonaktifkan.

#### [2026-09-07 10:32 WIB]
[TEST] - Memverifikasi validasi root satu-stream dan kontrak dataset final
{ DETAILS CHANGE } - Seluruh 15 test lulus; audit final memeriksa ID unik, root/direct mapping, tanpa nested, field wajib, BOM, distribusi bahasa/source, root coverage, dan kesetaraan seen_ids dengan CSV.

#### [2026-09-07 10:32 WIB]
[PERF] - Menggabungkan validasi root dan ekstraksi reply dalam satu stream
{ DETAILS CHANGE } - Step 2 memakai tweet_thread sekali per seed untuk menemukan focal root lalu memfilter Direct_Reply. Panggilan tweet_details terpisah dihapus sehingga konsumsi queue TweetDetail turun tanpa memasukkan nested.

#### [2026-09-07 08:26 WIB]
[CHORE] - Mengaudit dan menyiapkan resume dataset MBG direct reply
{ DETAILS CHANGE } - Audit 2.313 root legacy; migrasi menghasilkan 2.306 baris canonical dan 548 seed ambang >=50. Live run berhenti aman tanpa reply baru karena satu-satunya sesi X terdeteksi logged out.

#### [2026-09-07 08:26 WIB]
[DOCS] - Mendokumentasikan resume direct reply dari CSV legacy
{ DETAILS CHANGE } - README memuat contoh migrasi non-destruktif, target 20.000, ambang 50 reply, output canonical, dan checkpoint terpisah.

#### [2026-09-07 08:26 WIB]
[TEST] - Menambah cakupan migrasi legacy dan penolakan child seed
{ DETAILS CHANGE } - Suite menguji filter root legacy, antrean ambang 50, mapping relasi canonical, serta memastikan endpoint reply tidak dipanggil saat metadata live menunjukkan seed adalah child.

#### [2026-09-07 08:26 WIB]
[FIX] - Memvalidasi relasi seed terhadap metadata live sebelum Step 2
{ ISSUE } - Schema legacy tidak menyimpan conversationId sehingga label 1_root saja belum cukup membuktikan seed bukan child reply.
{ DETAILS CHANGE } - Step 2 kini mengambil TweetDetail dan hanya lanjut bila Tweet_ID sama dengan Conversation_ID serta In_Reply_To kosong; seed non-root ditandai invalid_root.

#### [2026-09-07 08:26 WIB]
[FEAT] - Menambahkan migrasi root legacy ke dataset canonical v2
{ DETAILS CHANGE } - Opsi --import-legacy-roots memetakan root valid tanpa mengubah sumber, menjaga ID sebagai string, commit CSV sebelum checkpoint, deduplikasi, dan mengantrekan root berdasarkan --min-replies.

#### [2026-09-01 19:40 WIB]
[CHORE] - Menjalankan dan mengaudit scraper Step 1 secara live
{ DETAILS CHANGE } - Resume menambah 654 root durable menjadi 2.313 baris unik, 13/30 query selesai, dan 413 root antre. Run dihentikan saat rate limit setelah backup; mismatch historis tetap 16 ID tanpa kehilangan baru.

#### [2026-09-01 19:30 WIB]
[DOCS] - Menambahkan Bab 7 SRS arsitektur teknis aplikasi
{ DETAILS CHANGE } - FSD kini memuat struktur direktori acuan, dependensi inti, dan mapping tiga tab GUI. Root tetap twscraper dan migrasi folder dapat dilakukan bertahap tanpa memindahkan file saat ini.

#### [2026-09-01 19:28 WIB]
[DOCS] - Menambahkan tata kelola agentic dan audit CSV repository
{ DETAILS CHANGE } - AGENTS.md mengatur pembacaan FSD/changelog/state data, loop observe-execute-verify-repair, kontrak CSV, keamanan kredensial, Definition of Done, serta kewajiban changelog.
