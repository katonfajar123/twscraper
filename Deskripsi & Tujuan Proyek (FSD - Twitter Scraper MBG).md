Deskripsi & Tujuan Proyek (FSD \- Twitter Scraper MBG) 

**Bab 1: Pendahuluan dan Lingkup Proyek (Project Scope & Objectives)**

**1.1. Latar Belakang Sistem** Proyek ini bertujuan untuk mengembangkan aplikasi perangkat lunak berbasis Desktop/Web GUI yang dirancang khusus untuk mengeksekusi ekstraksi data (*scraping*) berskala besar dari platform X (Twitter). Fokus utama sistem adalah mengumpulkan opini, reaksi, dan sentimen publik terkait "Program Makan Bergizi Gratis" (MBG). Karena platform X menerapkan pembatasan *rate limit* yang ketat, aplikasi tidak mengandalkan API publik standar, melainkan menggunakan *library* `twscrape` yang mendukung eksekusi *asynchronous*, rotasi multikun (*account pool*), dan retensi sesi berbasis SQLite untuk mencegah pemblokiran.

**1.2. Target dan Objektif Utama**

* **Kuantitas & Kualitas Data:** Mengakuisisi minimum 20.000 baris data komentar (*replies*) dan cuitan independen yang bebas dari *spam* serta sangat relevan dengan program MBG.  
* **Sentralisasi Kontrol via GUI:** Menyediakan antarmuka grafis yang memudahkan pengguna mengelola *cookies* akun, mengatur parameter *scraping*, memantau *progress bar* secara *real-time*, dan melihat pratinjau tabel hasil tanpa menyentuh *command line*.  
* **Standardisasi Format Analisis:** Menghasilkan *output* data (CSV/Dataframe) yang sudah terstruktur rapi (mencakup Tweet ID, Root ID, Teks, Timestamp, dan Engagement) agar siap diimpor ke dalam *pipeline* *Natural Language Processing* (NLP).

**1.3. Strategi Pengumpulan Data (Acquisition Logic)** Untuk mencapai 20.000 data terfokus, sistem menerapkan arsitektur penarikan data hibrida yang terbagi dalam dua metode di dalam GUI:

* **Metode A: Root Tweet Replies Extraction (Fokus Utama)** Sistem mengekstrak hirarki balasan dari sebuah cuitan pemantik (*root tweet*). Pengguna menginput deretan *Tweet ID* dari utas viral mengenai MBG (misalnya dari media nasional atau tokoh politik). Aplikasi memanfaatkan `api.tweet_replies(tweet_id)` untuk menyedot ribuan komentar murni dari audiens di utas tersebut. Cara ini menjamin kepadatan opini sentimen yang jauh lebih tinggi dibandingkan sekadar mencari kata kunci secara acak.  
* **Metode B: Keyword Mapping & Advanced Search (Fokus Perluasan)** Sistem menyediakan parameter pencarian dengan skema *Boolean queries* yang ditargetkan pada pengguna organik. Pemetaan *keyword* (*Keyword Mapping*) dirancang berlapis:  
  * **Primary Core:** `"makan bergizi gratis"` OR `"program mbg"` OR `"makan siang gratis"`  
  * **Contextual Modifiers:** `("makan bergizi" OR "mbg") AND ("prabowo" OR "gibran" OR "anggaran" OR "sekolah" OR "gizi")`  
  * **Negative Keywords/Filters (Spam Control):** `-filter:links` (mengeliminasi *bot* yang membagikan tautan berita/promosi), `-filter:media` (mengutamakan opini berbasis teks).

**1.4. Batasan Ruang Lingkup Sistem (Out of Scope)**

* Aplikasi berfokus murni pada **mesin ekstraksi dan visualisasi data mentah**, tidak mencakup proses pelabelan otomatis sentimen (Positif/Netral/Negatif) di dalam *source code* yang sama.  
* Pendaftaran akun Twitter dilakukan secara manual di luar sistem. Aplikasi hanya bertugas menerima dan mengautentikasi *cookies* (`auth_token`, `ct0`).

## **Bab 2: Arsitektur Sistem dan Spesifikasi Graphical User Interface (GUI)**

**2.1. Arsitektur Teknologi dan *Tech Stack***

Sistem ini dibangun dengan pendekatan *client-side desktop application* untuk memastikan sumber daya komputasi dan manajemen jaringan (termasuk proksi jika diperlukan) terisolasi di mesin lokal pengguna.

* **Core Engine:** Python 3.10+ (mendukung penuh fitur *asynchronous* terbaru).  
* **Scraping Engine:** twscrape sebagai *library* utama penarik data. Semua sesi *login* dan antrean rotasi akun akan disimpan dalam *database* lokal SQLite (accounts.db) yang dikelola otomatis oleh *library* ini.  
* **GUI Framework:** **PyQt6** dikombinasikan dengan modul QThread atau qasync. Pemilihan PyQt6 didasarkan pada kemampuannya merender tabel data berukuran besar (puluhan ribu baris) tanpa mengalami *lag* visual yang parah dibandingkan kerangka kerja GUI yang lebih sederhana.  
* **Data Processing:** pandas digunakan sebagai *in-memory data structure* untuk menampung hasil *scraping* secara *real-time* sebelum diekspor.

**2.2. Struktur Tata Letak dan Navigasi Visual (Layouting)**

Antarmuka utama dirancang dalam bentuk *Single Page Application Dashboard* yang terbagi menjadi tiga zona visual utama agar pengguna dapat mengatur parameter sekaligus memantau hasil secara bersamaan.

* **Zona A: Sidebar Control Panel (Panel Kontrol Kiri)**  
  Area ini adalah pusat komando penarikan data, berisi elemen interaktif berikut:  
  * **Dropdown "Metode Scraping":** Pengguna dapat memilih antara "Reply via Tweet ID" atau "Keyword Advanced Search".  
  * **Input Field (Dinamis):**  
    * Jika memilih *Tweet ID*, *field* akan menerima *multiline text* untuk menempelkan beberapa ID (dipisahkan koma/baris).  
    * Jika memilih *Keyword*, *field* akan menampilkan *text box* untuk memasukkan parameter *Boolean query* (berdasarkan pemetaan di Bab 1).  
  * **Target Limit (Spinbox):** Input numerik untuk menetapkan batas maksimal data per sesi penarikan (misal: diset *default* 20.000).  
  * **Action Buttons:** Tombol **"Mulai Ekstraksi"** (hijau) dan **"Hentikan Paksa"** (merah).  
* **Zona B: Account Management & System Status (Panel Atas)**  
  Untuk mengelola amunisi *scraping*, tersedia tab atau panel ringkas untuk manajemen akun:  
  * **Form Input Cookie:** *Text field* untuk menginput auth\_token dan ct0 secara instan tanpa perlu memodifikasi konfigurasi terminal.  
  * **Indikator Rotasi:** Menampilkan jumlah total akun yang *Active*, *Locked*, atau *Banned* di dalam SQLite twscrape.  
  * **Live Progress Bar:** Bar indikator visual (0-100%) dan teks hitungan mundur (*"Berhasil mengekstrak 4.250 / 20.000 komentar..."*).  
* **Zona C: Real-Time Data Monitor (Tabel Utama Tengah)**  
  Menggunakan komponen QTableView dari PyQt6, area ini memvisualisasikan data yang sedang ditarik secara langsung (*live populate*).  
  * Sistem tidak menunggu 20.000 data selesai ditarik untuk menampilkannya. Tabel akan melakukan *auto-refresh* setiap *batch* 50 atau 100 cuitan berhasil di-*parsing*.  
  * Fitur GUI pada tabel mencakup *Auto-resize columns* dan *Click-to-copy* untuk memudahkan pengguna menginspeksi teks komentar apakah relevan dengan sentimen MBG.

**2.3. Alur Kerja Asynchronous (Mencegah GUI Freezing)**

Tantangan terbesar dalam membuat GUI *scraper* adalah antarmuka yang macet (Not Responding) saat mesin sedang mengunduh data.

* Aplikasi ini akan memisahkan **Main UI Thread** (yang merender tombol dan tabel) dengan **Worker Thread** (yang menjalankan fungsi async for tweet in api.search(...) dari twscrape).  
* Worker Thread akan berkomunikasi dengan UI menggunakan sistem *Signals and Slots* bawaan PyQt. Setiap kali satu *batch* tweet didapat, *Worker* memancarkan sinyal (*emit signal*) berisi struktur JSON/Dictionary ke Main UI untuk disuntikkan ke dalam *DataFrame Pandas* dan ditampilkan ke layar tabel.

## **Bab 3: Struktur Output Data, Pemetaan Atribut, dan Mekanisme Ekspor**

**3.1. Pemetaan Struktur Data (Data Dictionary)** Karena tujuan akhir *scraper* ini adalah menyediakan *dataset* yang matang untuk model *Natural Language Processing* (NLP) atau analisis sentimen, maka *raw data* yang dikembalikan oleh objek Tweet dari twscrape harus distandardisasi dan dipetakan ke dalam struktur *DataFrame* tabular yang kohesif.

Berikut adalah spesifikasi kolom yang akan dibentuk di dalam memori Pandas secara *real-time* sebelum diekspor:

| Nama Kolom (Header) | Tipe Data | Sumber Objek twscrape | Deskripsi & Urgensi Analisis |
| :---- | :---- | :---- | :---- |
| **Tweet\_ID** | String | tweet.id | Pengidentifikasi unik untuk mencegah duplikasi data saat *merge* dataset. |
| **Root\_Tweet\_ID** | String | tweet.inReplyToTweetId | Kunci relasional. Sangat krusial jika menggunakan mode ekstraksi *Reply* untuk melacak cuitan mana yang sedang dikomentari. |
| **Waktu\_Posting** | Datetime | tweet.date | *Timestamp* (UTC/Local) untuk kebutuhan analisis deret waktu (*time-series analysis*) sentimen harian MBG. |
| **Username** | String | tweet.user.username | Nama pengguna asli untuk mendeteksi potensi *spam* atau akun yang mendominasi opini. |
| **Teks\_Komentar** | Text | tweet.rawContent | **Kolom Inti (Target NLP)**. Berisi teks mentah cuitan tanpa modifikasi, memertahankan tagar, *mention*, dan *emoji* asli. |
| **Jumlah\_Likes** | Integer | tweet.likeCount | Metrik *engagement*. Komentar dengan sentimen negatif tapi *likes* tinggi memiliki bobot polarisasi yang berbeda dengan komentar tanpa interaksi. |
| **Jumlah\_Retweet** | Integer | tweet.retweetCount | Indikator resonansi opini pengguna lain terhadap komentar tersebut. |
| **Sumber\_Akuisisi** | String | *Generated Value* | Tag internal aplikasi (contoh: "REPLY\_TWEET\_ID" atau "KEYWORD\_SEARCH") untuk membedakan asal usul baris data. |

**3.2. Pemrosesan Data In-Memory (Pre-Export Validation)**

Sebelum data disuntikkan ke GUI dan siap diunduh, sistem *backend* akan melakukan validasi ringan pada level *DataFrame*:

* **Deduplikasi Otomatis:** Menjalankan fungsi df.drop\_duplicates(subset=\['Tweet\_ID'\]) di memori untuk memastikan tidak ada komentar ganda yang terhitung ke dalam target limit 20.000 data.  
* **Sanitasi Karakter:** Meskipun Pandas menangani *newline* (\\n) dengan baik, sistem akan merangkum teks dalam kutipan (*quoting*) yang ketat agar baris CSV tidak pecah saat komentar memiliki banyak paragraf.

**3.3. Mekanisme Ekspor (Export Engineering)**

Modul ekspor dirancang agar *foolproof* bagi analis data yang akan memproses hasilnya di Microsoft Excel atau Google Sheets.

* **Format dan Encoding:** File disimpan dalam ekstensi .csv menggunakan *encoding* utf-8-sig. Penggunaan varian *Byte Order Mark* (BOM) ini mutlak diperlukan agar Excel di lingkungan Windows dapat membaca *emoji* dan karakter Unicode pada cuitan masyarakat Indonesia dengan sempurna, tanpa mengubahnya menjadi karakter *gibberish*.  
* **Penamaan File Dinamis (Dynamic Naming):** Saat tombol "Export to CSV" ditekan, GUI akan otomatis menghasilkan nama file berdasarkan *timestamp* dan metode yang dipilih untuk memudahkan pengarsipan.  
  * *Contoh pola:* MBG\_Dataset\_Replies\_20260901\_1920.csv atau MBG\_Dataset\_Keyword\_20260901\_1925.csv.  
* **Partial Export (Ekspor Darurat):** Jika koneksi terputus atau akun X terkena limit sebelum mencapai angka 20.000, pengguna tetap bisa mengekspor progres data yang sudah terkumpul di tabel GUI tanpa risiko kehilangan tangkapan.

Pertanyaan yang sangat kritis dan tepat sasaran\! Ini adalah tantangan klasik dalam pengumpulan data Twitter. Karena struktur percakapan X berupa *tree* (pohon bercabang), sebuah komentar yang viral bisa beranak-pinak menjadi utas baru di dalam utas utama. Jika tidak dipisahkan, algoritma sentimen Anda bisa kebingungan menentukan konteksnya.

Untuk mengatasi hal ini, kita akan merumuskan spesifikasi penanganannya di dalam **Bab 4**.

## **Bab 4: Arsitektur Hierarki Komentar & Penanganan *Nested Replies***

**4.1. Logika *Conversation ID* vs *In-Reply-To ID*** Untuk membedakan mana yang merupakan balasan langsung (*direct reply*) ke cuitan utama dan mana yang merupakan balasan dari balasan pengguna lain (*nested replies*), sistem akan mengeksploitasi dua parameter bawaan dari *metadata* X/Twitter yang diekstrak oleh `twscrape`:

1. **`tweet.conversationId`**: Ini adalah ID absolut dari cuitan paling pertama yang memulai seluruh utas (Root Tweet sebenarnya).  
2. **`tweet.inReplyToTweetId`**: Ini adalah ID dari cuitan yang *secara spesifik* sedang dibalas oleh komentar tersebut.

**4.2. Algoritma Pelabelan Kedalaman (Depth Tagging)** Saat *scraper* berjalan dan menangkap objek `Tweet`, sistem *backend* Python akan menjalankan fungsi *conditional logic* (IF-ELSE) sebelum menampilkannya di tabel GUI:

* **Level 1 (Direct Reply):** Jika `tweet.inReplyToTweetId` **SAMA DENGAN** `Target_Root_ID` yang diinput pengguna. *Status:* Ini adalah opini langsung terhadap isu MBG yang dilempar oleh pembuat cuitan utama.  
* **Level 2+ (Nested Reply / Komentar Beranak):** Jika `tweet.conversationId` **SAMA DENGAN** `Target_Root_ID`, **TETAPI** `tweet.inReplyToTweetId`\-nya berbeda (merujuk ke ID komentar pengguna lain). *Status:* Ini adalah interaksi antar-netizen (debat kusir, setuju/tidak setuju dengan komentar orang lain, bukan langsung merespons utas utama).

**4.3. Pembaruan Struktur Database (Penambahan Kolom)** Untuk mengakomodasi pelacakan hierarki ini, kita akan menambahkan dua kolom baru pada struktur CSV yang sudah kita buat di Bab 3:

* **`Conversation_ID` (String):** Menyimpan ID utas utama sebagai benang merah seluruh percakapan.  
* **`Hierarki_Komentar` (String/Kategori):** Akan diisi otomatis oleh sistem dengan label: **"Direct\_Reply"** atau **"Nested\_Reply"**.

**4.4. Implementasi Fitur Filter di GUI** Karena Anda menargetkan 20.000 data sentimen MBG yang berkualitas, sistem antarmuka (GUI) di *Sidebar Panel Kiri* akan diberikan satu opsi *Toggle/Checkbox* tambahan:

* **\[ \] Ekstrak Semua Komentar (Termasuk Anak Cucu Komentar)**  
* **\[x\] Hanya Ekstrak Balasan Langsung (Level 1\)**

**Fungsi Toggle:** Jika pengguna memilih "Hanya Ekstrak Balasan Langsung", maka setiap kali *worker thread* mendapatkan `Nested_Reply`, data tersebut akan **di-drop (diabaikan)** dan tidak akan dihitung ke dalam kuota target 20.000 limit. Ini memastikan kualitas *dataset* Anda benar-benar murni berisi opini masyarakat terhadap MBG, bukan data *noise* dari netizen yang saling bertengkar di kolom balasan.

Pengalaman Anda sangat valid dan ini adalah isu fundamental dalam *scraping* Twitter modern. Batas \~600 balasan itu bukan *rate limit* IP atau akun, melainkan **"Pagination Wall"** dari algoritma *frontend* (GraphQL) Twitter itu sendiri.

Twitter memotong *cursor* paginasi pada sebuah utas tunggal untuk menghemat beban *server* mereka. Walaupun sebuah *tweet* memiliki 5.000 balasan tertulis, API internal Twitter biasanya hanya akan merender sekitar 500-800 balasan teratas (yang relevan atau dari akun terverifikasi), lalu berhenti memberikan data *next\_cursor*.

Berikut adalah rumusan Bab 5 untuk membongkar batasan tersebut di dalam sistem aplikasi Anda.

**Bab 5: Mitigasi "Pagination Wall" & Manajemen Sesi (Error Handling)**

**5.1. Strategi *Multi-Seed Array* (Antrean Root Tweet)** Karena satu utas (*root tweet*) secara matematis hanya bisa menghasilkan \~600 balasan murni, sistem tidak bisa mengandalkan satu *Tweet ID* untuk mencapai target 20.000 data.

* **Implementasi GUI:** *Input field* untuk Mode Reply diubah menjadi kotak teks area besar yang menerima daftar puluhan *Tweet ID* (dipisahkan baris baru).  
* **Worker Logic:** Aplikasi akan mengubah *input* ini menjadi sebuah *Array/List*. *Worker thread* akan melakukan *looping*: masuk ke ID pertama, sedot mentok (\~600 data), otomatis rilis kunci sesi, lalu lompat ke ID kedua, dan seterusnya tanpa intervensi manual.  
* **Kebutuhan Seed:** Untuk mencapai 20.000, pengguna perlu menyiapkan sekitar 35 \- 40 *Tweet ID* (viral) sebagai amunisi awal (35 \* 600 \= 21.000 data).

**5.2. Fitur *Hybrid Top-Up Target*** Bagaimana jika antrean 40 *Tweet ID* sudah habis tapi target data di GUI baru mencapai 17.500? Sistem akan dilengkapi fitur pengisi kekosongan otomatis (*Top-Up*).

* **Logic:** Jika target batas (20.000) belum tercapai setelah antrean ID habis, aplikasi akan otomatis memicu Mode 2 (Pencarian Kata Kunci) menggunakan rentang tanggal hari ini mundur ke belakang, hingga selisih 2.500 data tersebut terpenuhi.  
* Ini memastikan pengguna selalu mendapatkan output akhir persis sesuai limit yang diinput di GUI.

**5.3. Manajemen Rotasi Akun (`twscrape` Native Pool)** Meskipun batas 600 adalah masalah paginasi, tarikan masif hingga 20.000 baris *pasti* akan memicu *Rate Limit* (HTTP 429\) dari Twitter. Sistem akan mengintegrasikan manajemen *pool* bawaan `twscrape`:

* **Database Akun:** GUI akan memiliki tab "Manajemen Akun" yang membaca langsung dari `accounts.db`.  
* **Failover Otomatis:** Saat mengeksekusi `api.tweet_replies()`, jika akun A terkena *timeout*, *library* akan mengunci akun A, menyimpannya di SQLite, dan langsung menggantinya dengan akun B secara *seamless* di dalam *loop* tanpa memberhentikan proses *scraping* atau meng- *crash* GUI.  
* **Rekomendasi Skala:** FSD menyaratkan pengguna menyiapkan minimal 5 hingga 10 akun *cookie* aktif di dalam *pool* untuk merotasi beban 20.000 permintaan API.

**5.4. Penanganan *Crash* dan *Auto-Save* (Resume State)** Untuk mencegah kerugian waktu jika komputer mati mendadak saat data baru ditarik 15.000 baris:

* **Chunk Saving:** *Pandas DataFrame* tidak hanya disimpan saat pengguna menekan "Export". Sistem akan memicu *auto-save* ke file sementara (`temp_mbg_scrape.csv`) setiap kelipatan 500 baris.  
* Saat aplikasi dibuka kembali, GUI akan mendeteksi file *temp* tersebut dan menawarkan pop-up: *"Sesi sebelumnya terhenti di 15.000 data. Lanjutkan scraping?"*

**Bab 6: Kebutuhan Sistem, Dependensi, dan Panduan Instalasi (Deployment)**

**6.1. Spesifikasi Lingkungan Kerja (Environment)** Sistem dirancang untuk berjalan secara stabil di lingkungan *desktop* lokal atau *virtual server* dengan syarat minimum berikut:

* **Sistem Operasi:** Windows 10/11, macOS, atau Linux (Ubuntu/Debian).  
* **Runtime:** Python 3.10 atau versi lebih baru (mutlak diperlukan untuk kestabilan *asynchronous* generator pada *scraper*).  
* **Memori (RAM):** Minimal 8GB. Mengelola dan merender 20.000 baris data (teks, ID, dan metrik) ke dalam memori aktif (Pandas DataFrame) sekaligus menampilkannya ke GUI membutuhkan alokasi RAM yang memadai untuk mencegah *memory leak*.  
* **Koneksi Jaringan:** Disarankan menggunakan IP dinamis atau menyiapkan daftar *proxy* jika rotasi akun sering memicu *rate limit* berbasis IP dari pihak X.

**6.2. Manajemen Dependensi Utama** Aplikasi membutuhkan instalasi paket yang akan dikunci pada `requirements.txt`:

* `twscrape[curl]`: Pustaka utama pencari data. *Flag* `[curl]` memastikan *backend* `curl-cffi` ikut terinstal untuk meniru *TLS fingerprint* mirip *browser* asli agar terhindar dari deteksi *bot* dasar X.  
* `PyQt6` & `qasync`: Kerangka kerja GUI beserta *event loop bridge* yang memungkinkan proses *scraping* berjalan tanpa membekukan (Not Responding) antarmuka pengguna.  
* `pandas`: Pustaka utama untuk validasi, deduplikasi, dan konversi data tabular ke CSV.

**6.3. Urutan Inisialisasi Repositori** Untuk menjaga kebersihan *environment* dan menghindari konflik riwayat, penggelaran kode ke mesin lokal wajib menggunakan sekuens inisialisasi repositori, bukan kloning langsung.

* **Langkah 1:** Siapkan ruang kerja baru dan aktifkan pelacakan Git. `mkdir mbg-twitter-scraper && cd mbg-twitter-scraper` `git init`  
* **Langkah 2:** Kaitkan repositori *remote* sumber. `git remote add origin <URL_REPOSITORY_ANDA>`  
* **Langkah 3:** Tarik pembaruan spesifik dari cabang utama. `git fetch origin` `git pull origin main`  
* **Langkah 4:** Isolasi *environment* dan pasang dependensi. `python -m venv venv` `.\venv\Scripts\activate` (Untuk OS Windows) `pip install -r requirements.txt`

**6.4. Persiapan Pre-Flight Akun (SQLite Database)** Sebelum GUI utama dieksekusi, *database* lokal `accounts.db` harus diisi.

* Pengguna mengekspor data *cookie* (`auth_token` dan `ct0`) dari peramban.  
* Pengguna menjalankan perintah CLI bawaan twscrape: `twscrape add_cookie nama_akun_1`.  
* Verifikasi kesiapan akun dengan perintah `twscrape accounts`. Jika kolom `active` bernilai `True`, maka aplikasi visual bisa langsung dijalankan dengan perintah `python app.py`.

## **Bab 7: Software Requirements Specification (SRS)**

Bab ini menerjemahkan logika bisnis pada FSD menjadi cetak biru teknis agar tanggung jawab *backend*, *data layer*, dan *frontend* tidak tumpang tindih.

### **7.1. Struktur Direktori Proyek (Foldering)**

Pemisahan antara *thread* GUI dan *worker* wajib dilakukan agar aplikasi tidak *crash* atau *Not Responding* saat `twscrape` menjalankan proses penarikan data yang berat.

Struktur berikut merupakan **acuan pemisahan tanggung jawab**, bukan kewajiban untuk mengganti nama atau langsung memindahkan seluruh file. Folder root proyek boleh tetap bernama `twscraper/`, dan struktur yang sudah ada dapat dimigrasikan secara bertahap selama batas tanggung jawab antarmodul tetap dipertahankan.

~~~text
twscraper/
├── main.py                 # Entry point aplikasi dan inisialisasi window
├── requirements.txt        # Daftar dependensi library terkunci
├── accounts.db             # Database SQLite bawaan twscrape (auto-generated)
├── core/                   # Backend logic
│   ├── scraper.py          # Logika qasync, rotasi akun, dan fungsi twscrape
│   └── data_manager.py     # Handler pandas untuk deduplikasi dan auto-save
├── ui/                     # Komponen visual PyQt6
│   ├── main_window.py      # Layout utama, tab widget, dan layouting
│   ├── components.py       # Kustomisasi tombol dan tabel data viewer
│   └── theme.qss           # Styling antarmuka (dark mode)
└── exports/                # Folder tujuan ekspor
    └── temp/               # Auto-save chunk per 500 data untuk resume state
~~~

### **7.2. Spesifikasi Library & Dependensi Lingkungan**

Lingkungan kerja menggunakan Python 3.10+ untuk mendukung eksekusi *asynchronous* tingkat lanjut.

| Library Inti | Fungsi & Justifikasi Teknis |
| :--- | :--- |
| `twscrape[curl]` | *Engine* ekstraksi utama. Ekstensi `[curl]` melalui `curl-cffi` digunakan untuk meniru *TLS fingerprint* peramban dan mengurangi risiko deteksi bot X/Twitter. |
| `PyQt6` | Kerangka kerja *frontend*. Komponen `QTableView` dipakai bersama model data agar tabel berukuran besar dapat dirender secara efisien. |
| `qasync` | Jembatan antara *asyncio event loop* Python dan *event loop* Qt agar operasi seperti `await api.tweet_replies()` dapat berjalan tanpa membekukan UI. |
| `pandas` | Pemrosesan *DataFrame in-memory*, deduplikasi Tweet ID, pelabelan hierarki *nested reply*, dan ekspor CSV dengan encoding `utf-8-sig`. |

Versi dependensi wajib dikunci di `requirements.txt` dan diuji pada Python 3.10 atau versi yang lebih baru sebelum distribusi.

### **7.3. Pemetaan Layar Antarmuka (GUI Screen Mapping)**

Aplikasi dirancang sebagai *Single Window Dashboard* menggunakan navigasi `QTabWidget` untuk memisahkan fokus kontrol, manajemen akun, dan pemantauan data.

#### **Tab 1: Extraction Control (Pusat Komando)**

* **Input Area:** Form *multiline* untuk menampung daftar panjang Tweet ID pada Mode Reply atau *query string* pada Mode Pencarian.
* **Parameter Panel:** *Spinbox* penentu batas target dengan nilai default 20.000 dan *checkbox* **"Hanya Ekstrak Balasan Langsung (Level 1)"**.
* **Live Tracker:** `QProgressBar` horizontal dan konsol teks mini yang menampilkan log aktivitas secara langsung, misalnya saat memasuki Tweet ID baru atau melakukan rotasi akun setelah terkena *rate limit*.

#### **Tab 2: Account Pool Manager (Manajemen Amunisi)**

* **Credential Input:** *Text field* khusus untuk memasukkan `auth_token` dan `ct0`, lalu menyimpannya ke pool SQLite melalui fungsi integrasi cookie yang kompatibel dengan versi `twscrape` yang digunakan.
* **Status Table:** Menampilkan status dari `accounts.db` berupa Username, Status Aktif, Terakhir Digunakan, dan Total Request tanpa mengekspos nilai cookie atau kredensial.

#### **Tab 3: Real-Time Data Viewer (Monitor Hasil)**

* **Main Table:** `QTableView` yang diintegrasikan dengan `QAbstractTableModel` untuk menampilkan *Pandas DataFrame* secara *live* setiap kali worker mengirimkan batch data baru.
* **Export Control:** Tombol **"Export to CSV"** dan indikator numerik jumlah baris unik yang telah lolos deduplikasi serta validasi.
