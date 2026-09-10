# CHANGELOG

## Unreleased

### Phase: Agentic Foundation

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
