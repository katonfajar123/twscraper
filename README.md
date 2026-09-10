# Twitter Scraper MBG

Desktop GUI dan acquisition engine untuk mengumpulkan dataset percakapan MBG
dari X/Twitter menggunakan [twscrape](https://github.com/vladkens/twscrape)
v0.20.1.

Rancangan klasifikasi Naive Bayes untuk aspek `Mutu Gizi`, `Tata Kelola`, dan
`Distribusi` tersedia di [NB-Models/DOCUMENTATION.md](NB-Models/DOCUMENTATION.md).
Jalur baru IndoBERT/Transformer untuk ABSA aspek plus polaritas tersedia di
[IndoBERT/README.md](IndoBERT/README.md).

## Prasyarat

- Python 3.10+
- Dependensi pada `requirements.txt`

---

## Mulai cepat GUI (Tkinter Desktop)

Aplikasi desktop ini menggunakan **Tkinter** bawaan standar Python, sehingga **100% stabil di Windows**, ringan, dan tidak memerlukan instalasi runtime Qt atau library GUI yang rumit.

### Cara termudah (Double-klik):

> Cukup klik dua kali file **`Jalankan MBG Studio.bat`** di folder project ini.
> Dependensi akan terinstall otomatis di awal, lalu aplikasi langsung terbuka.

### Atau via terminal:

```powershell
python main.py
```

`app.py` juga tersedia sebagai launcher alternatif:

```powershell
python app.py
```

Antarmuka dirancang khusus agar mudah digunakan oleh **pengguna awam** dengan 7 tab alur kerja:

1. **Beranda & Panduan** — Gambaran ringkas 5 langkah kerja serta status database akun.
2. **1 · Set Up Akun** — Tambah cookie Twitter (`auth_token`, `ct0`), aktifkan/nonaktifkan akun, serta reset rate-limit locks tanpa terminal. Dilengkapi tombol panduan visual cara mengambil cookie dari browser.
3. **2 · Ekstraksi Data** — Pengaturan metode scraping (Hybrid utas + keyword, balasan utas saja, atau pencarian kata kunci), input Tweet ID & query boolean, monitor progres persentase, dan log realtime tanpa membuat aplikasi freeze. Tombol *Hentikan* bekerja secara aman via stop-file durable.
4. **3 · Audit & Data** — Pengecekan kualitas file CSV (deteksi duplikat, notasi ilmiah Excel, validasi relasi direct reply vs root) dan tabel pratinjau interaktif cuplikan 200 data.
5. **4 · Preprocessing** — Pembersihan teks (URL, mention, emoji, tanda baca) dan normalisasi kata gaul/singkatan berdasarkan kamus. Menambahkan kolom baru `Content_Cleansing` dan `Content_Normalisasi` tanpa menimpa teks mentah asli.
6. **5 · Kamus Slang** — Editor tabel kamus normalisasi (`slang`, `kata_baku`, `frekuensi`) dengan pencarian cepat instan, tambah kata baru, edit, hapus, dan simpan.
7. **6 · Rencana NLP** — Panduan edukasi alur klasifikasi 3 aspek MBG (`Mutu_Gizi`, `Tata_Kelola`, `Distribusi`) vs sentimen (`Positif`, `Netral`, `Negatif`), larangan keyword-as-ground-truth, serta pintasan ke panduan anotasi.

---

## Struktur File

```
twscraper/
|-- main.py                 # Entry point GUI
|-- app.py                  # Entry point GUI alternatif
|-- mbg_gui/                # Window, worker, audit, dan preprocessing
|-- scraper.py              # Engine async + CLI yang dipakai GUI
|-- setup_accounts.py       # Setup password/IMAP legacy via CLI
|-- accounts.db             # Database sesi lokal twscrape
|-- output/                 # Dataset, checkpoint, dan mapping
`-- tests/                  # Test tanpa scraping live
```

---

## Setup akun alternatif via CLI

### 1. Buat file akun

Salin template dan isi dengan data akun Anda:

```bash
copy accounts.txt.example accounts.txt
```

Edit `accounts.txt` dengan format:

```
username:password:email:email_password
```

Contoh:

```
myaccount:MyPassword123:myemail@gmail.com:EmailPassword123
```

> **Catatan:** `email_password` digunakan twscrape untuk mengambil kode verifikasi X via IMAP secara otomatis. Jika tidak tersedia, gunakan mode `--manual`.

---

### 2. Login akun

```bash
# Login otomatis (jika IMAP email tersedia)
python setup_accounts.py

# Login manual (masukkan kode verifikasi email sendiri)
python setup_accounts.py --manual
```

Script akan:
1. Membaca `accounts.txt`
2. Menambahkan akun ke database `accounts.db`
3. Menjalankan login flow untuk setiap akun
4. Menampilkan status akhir setiap akun

---

### 3. Cek status akun via CLI

```bash
twscrape accounts
twscrape stats
```

---

## Penggunaan CLI

```bash
# Search tweet
twscrape search "python lang:id" --limit=20

# Info user
twscrape user_by_login username

# Tweet terbaru user
twscrape user_tweets USER_ID --limit=20

# Simpan ke file JSONL
twscrape search "query" --limit=100 > hasil.jsonl
```

### Resume dataset legacy sebagai root terverifikasi

CSV Step 1 lama dapat dimigrasikan secara non-destruktif ke schema v2 lalu
dipakai untuk mengambil balasan langsung. Setiap seed diverifikasi lagi dari
metadata live sebelum endpoint replies dipanggil.

```bash
python scraper.py --step 2 --target 20000 --min-replies 50 ^
  --import-legacy-roots output/mbg_tweets_20260831_164721.csv ^
  --output output/MBG_Dataset_DirectReplies.csv ^
  --checkpoint output/checkpoint_direct_replies.json
```

Seed manual dan query yang dapat diedit juga tersedia langsung di CLI:

```powershell
python scraper.py --step 2 --seed-id 1900000000000000001 `
  --seed-id https://x.com/example/status/1900000000000000002 `
  --target 20000 --output output/MBG_Replies.csv `
  --checkpoint output/checkpoint_replies.json

python scraper.py --step 1 --keyword "makan bergizi gratis" `
  --keyword "(MBG OR embege) AND sekolah" --target 5000
```

`--keyword` dan `--seed-id` boleh diulang. Seed manual tetap diverifikasi melalui
metadata live sebelum ditulis sebagai root. Opsi `--stop-file PATH` ditujukan
untuk penghentian aman oleh GUI atau otomasi lokal.

### Mengatur keyword scraping tanpa edit kode

Keyword default GUI dan CLI ada di:

```text
config/scraping_keywords.txt
```

Isi file tersebut satu keyword atau Boolean query per baris. Di tab **2 - Ekstraksi Data**, keyword ditampilkan sebagai tabel editable supaya setiap query mudah dicek sebelum scraping. Pengguna bisa:

- memilih preset **Query FSD Ringkas**, **Keyword Scraper Lama**, grup riset dari `keywords.py`, atau **Semua Grup Keyword Riset**;
- klik **Pakai Preset** untuk mengganti isi query, atau **Tambah Preset** untuk menggabungkan dengan query yang sudah diketik;
- klik **Tambah Baris**, **Edit Baris**, **Hapus Terpilih**, **Naik**, atau **Turun** untuk mengelola urutan query;
- klik **Muat** untuk membaca file keyword sendiri;
- klik **Simpan** untuk menyimpan daftar keyword yang sudah diedit dari GUI.

Saat mode Hybrid atau Keyword Search dijalankan, setiap baris tabel diteruskan ke scraper sebagai `--keyword` terpisah.

Jika checkpoint aktif sudah memiliki data resume, GUI otomatis mengisi field CSV dari `output_file` di checkpoint tersebut. Untuk melanjutkan 1.970 data durable, pakai pasangan checkpoint dan CSV yang sama; untuk dataset baru, gunakan nama checkpoint baru juga.

---

## Integritas data dan preprocessing

- Tweet ID dibaca sebagai string. Audit menolak notasi ilmiah seperti
  `2.09436E+18` karena digit aslinya sudah tidak dapat direkonstruksi dengan
  aman.
- Preprocessing menolak schema inti yang hilang, ID rusak, duplikat, relasi
  reply tidak valid, atau orphan direct reply.
- CSV turunan selalu memakai `utf-8-sig` dan quoting penuh, sedangkan CSV sumber
  serta checkpoint tidak diubah.
- URL dan mention dapat dipertahankan, dihapus, atau diganti token. Emoji dan
  tanda baca dapat dipertahankan.
- Mapping slang wajib memiliki `slang` dan `kata_baku` yang unik dan tidak
  kosong. Normalisasi menggunakan pencocokan token utuh, bukan substring.

Pelabelan sentimen/aspek otomatis tetap di luar scope scraper. Folder
`NB-Models` dan `IndoBERT` adalah jalur riset terpisah yang membutuhkan label
manusia dan evaluasi tanpa kebocoran root sebelum dapat dipakai sebagai model.

---

## Penggunaan Python API

```python
import asyncio
from twscrape import API, gather

async def main():
    api = API("accounts.db")

    # Search
    tweets = await gather(api.search("python lang:id", limit=20))
    for t in tweets:
        print(t.id, t.user.username, t.rawContent)

    # Info user
    user = await api.user_by_login("xdevelopers")
    print(user.id, user.username, user.followersCount)

asyncio.run(main())
```

---

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Login gagal | Coba `python setup_accounts.py --manual` |
| `No account available` | Akun terkena rate limit, tunggu atau tambah akun |
| Login error / suspended | Akun bermasalah, cek kolom `error_msg` di `twscrape accounts` |
| Email verifikasi tidak masuk | Pastikan IMAP aktif di akun email Anda |

### Reset lock jika terjadi hang

```bash
twscrape reset_locks
```

### Login ulang akun yang gagal

```bash
twscrape relogin_failed --manual
```

---

## Environment Variables

| Variable | Default | Keterangan |
|----------|---------|------------|
| `TWS_DB` | `accounts.db` | Path database |
| `TWS_PROXY` | - | Proxy global |
| `TWS_HTTP_BACKEND` | `httpx` | Backend HTTP (`httpx`/`curl`) |
| `TWS_WAIT_EMAIL_CODE` | `30` | Timeout kode verifikasi (detik) |
| `TWS_LOG_LEVEL` | `INFO` | Level logging |
| `TWS_TELEMETRY` | `1` | Set `0` untuk nonaktifkan telemetry |
