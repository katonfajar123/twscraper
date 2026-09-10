# =============================================================================
# keywords.py
# Keyword groups berdasarkan framework penelitian MBG (mind map):
#
#   Sentimen Program MBG
#   ├── Mutu Gizi
#   │   ├── Kecukupan Porsi & Nutrisi
#   │   ├── Variasi & Rasa Menu
#   │   └── Keamanan Konsumsi
#   ├── Tata Kelola
#   │   ├── Standarisasi Vendor/Dapur Umum
#   │   ├── Transparansi & Efisiensi Anggaran
#   │   └── Responsivitas Aduan (Grievance Handling)
#   └── Distribusi
#       ├── Ketepatan Waktu Logistik
#       ├── Pemerataan Jangkauan (Fokus 3T)
#       └── Kondisi Fisik & Pembagian
# =============================================================================

KEYWORD_GROUPS = {

    # ─── BROAD / JARING LEBAR (wajib ada di semua run) ────────────────────────
    "mbg_umum": [
        "makan bergizi gratis",
        "MBG sekolah",
        "MBG prabowo",
        "#MBG",
        "#MakanBergiziGratis",
        "program makan bergizi",
        "embege",
        "makan siang gratis siswa",
        "makan gratis anak sekolah",
        "MBG 2025",
        "makan bergizi gratis prabowo",
        "program mbg berjalan",
    ],

    # ─── MUTU GIZI ─────────────────────────────────────────────────────────────

    "mutu_gizi_porsi_nutrisi": [
        "porsi mbg",
        "gizi mbg",
        "nutrisi makan bergizi",
        "porsi makan bergizi kurang",
        "mbg tidak bergizi",
        "kecukupan gizi mbg",
        "kalori mbg",
        "mbg bergizi cukup",
        "mbg kurang porsi",
        "gizi anak sekolah mbg",
        "mbg memenuhi gizi",
        "standar gizi makan bergizi gratis",
    ],

    "mutu_gizi_variasi_menu": [
        "menu mbg",
        "variasi menu makan bergizi",
        "rasa mbg",
        "menu makan bergizi gratis",
        "mbg enak",
        "mbg tidak enak",
        "mbg bervariasi",
        "lauk mbg",
        "sayur mbg",
        "menu mbg membosankan",
        "mbg sama terus",
        "mbg ganti menu",
        "nasi mbg",
        "protein mbg",
    ],

    "mutu_gizi_keamanan": [
        "mbg basi",
        "makan bergizi gratis basi",
        "mbg keracunan",
        "keracunan makan bergizi gratis",
        "mbg kotor",
        "mbg tidak higienis",
        "higienitas mbg",
        "mbg aman",
        "mbg busuk",
        "mbg tidak layak makan",
        "mbg kadaluarsa",
        "keamanan pangan mbg",
        "sanitasi mbg",
        "mbg tercemar",
    ],

    # ─── TATA KELOLA ───────────────────────────────────────────────────────────

    "tatakelola_vendor_dapur": [
        "vendor mbg",
        "dapur umum mbg",
        "katering mbg",
        "mitra mbg",
        "standar vendor mbg",
        "dapur mbg",
        "rekanan mbg",
        "supplier mbg",
        "penyedia makan bergizi gratis",
        "catering mbg bermasalah",
        "seleksi vendor mbg",
        "dapur produksi mbg",
        "standar dapur mbg",
    ],

    "tatakelola_anggaran": [
        "anggaran mbg",
        "dana mbg",
        "korupsi mbg",
        "mbg transparan",
        "efisiensi mbg",
        "mbg dikorupsi",
        "anggaran makan bergizi gratis",
        "mbg pemborosan",
        "biaya mbg",
        "keuangan mbg",
        "mbg mark up",
        "dana makan bergizi gratis diselewengkan",
        "audit mbg",
        "transparansi anggaran mbg",
        "mbg bocor anggaran",
    ],

    "tatakelola_aduan": [
        "komplain mbg",
        "aduan mbg",
        "laporan mbg bermasalah",
        "masalah mbg",
        "keluhan mbg",
        "mbg dikeluhkan",
        "mbg tidak sampai",
        "pengaduan makan bergizi gratis",
        "mbg gagal",
        "mbg bermasalah",
        "kritik mbg",
        "mbg mengecewakan",
        "evaluasi mbg",
        "mbg tidak berfungsi",
    ],

    # ─── DISTRIBUSI ────────────────────────────────────────────────────────────

    "distribusi_logistik": [
        "distribusi mbg",
        "logistik mbg",
        "mbg terlambat",
        "mbg tidak tepat waktu",
        "jadwal mbg",
        "pengiriman mbg",
        "mbg telat",
        "distribusi makan bergizi gratis",
        "mbg tidak datang",
        "mbg molor",
        "rantai pasok mbg",
        "mbg on time",
        "ketepatan distribusi mbg",
        "mbg gagal distribusi",
    ],

    "distribusi_pemerataan_3t": [
        "mbg daerah terpencil",
        "mbg 3T",
        "mbg pelosok",
        "mbg merata",
        "mbg tidak merata",
        "mbg daerah",
        "mbg papua",
        "mbg NTT",
        "mbg perbatasan",
        "makan bergizi gratis pedesaan",
        "mbg desa",
        "pemerataan makan bergizi gratis",
        "mbg belum merata",
        "mbg Kalimantan",
        "mbg daerah tertinggal",
    ],

    "distribusi_kondisi_fisik": [
        "mbg rusak",
        "kondisi mbg",
        "kemasan mbg",
        "mbg tidak layak",
        "pembagian mbg",
        "mbg tumpah",
        "wadah mbg",
        "packaging mbg",
        "mbg bocor",
        "kondisi fisik makan bergizi gratis",
        "mbg kotak rusak",
        "kemasan makan bergizi gratis jelek",
        "mbg tidak higienis kemasan",
        "plastik mbg",
    ],
}


# =============================================================================
# LEXICON SENTIMEN (Bahasa Indonesia + konteks MBG)
# =============================================================================
POSITIVE_WORDS = {
    # Umum positif
    "bagus", "baik", "mantap", "keren", "hebat", "luar biasa", "sukses",
    "berhasil", "bermanfaat", "membantu", "senang", "suka", "setuju",
    "dukung", "mendukung", "apresiasi", "terima kasih", "alhamdulillah",
    "maju", "berkembang", "meningkat", "lebih baik", "positif",
    "aman", "sehat", "terjamin", "terpenuhi", "tercukupi",
    "lancar", "tepat waktu", "merata", "adil", "transparan",
    "inovatif", "terobosan", "solusi", "efisien", "efektif",
    "cepat", "responsive", "sigap", "tanggap",
    # Konteks MBG
    "bergizi", "nutrisi", "cukup", "kenyang", "enak", "lezat",
    "program bagus", "program baik", "bervariasi", "higienis",
    "segar", "layak", "tepat sasaran", "memuaskan",
    "bersih", "terdistribusi", "terjangkau", "gratis",
    "anak sehat", "gizi terpenuhi",
}

NEGATIVE_WORDS = {
    # Umum negatif
    "gagal", "buruk", "jelek", "parah", "menyedihkan", "mengecewakan",
    "kecewa", "marah", "tidak setuju", "tolak", "menolak", "bohong",
    "tipu", "korupsi", "curang", "sia-sia", "buang-buang", "pemborosan",
    "tidak berguna", "tidak efektif", "tidak merata", "diskriminasi",
    "salah", "keliru", "bencana", "masalah", "ribet", "susah",
    "lambat", "telat", "terlambat", "molor", "ngaret",
    "tidak transparan", "diselewengkan", "dikorupsi", "mark up",
    "tidak responsif", "tidak tanggap", "diabaikan",
    # Konteks MBG
    "tidak bergizi", "tidak sehat", "basi", "kotor", "menjijikkan",
    "tidak enak", "tidak layak", "kurang", "tidak cukup", "terbatas",
    "keracunan", "busuk", "kadaluarsa", "tercemar", "jorok",
    "tidak tepat sasaran", "tidak sampai", "tidak merata",
    "rusak", "bocor", "tumpah", "tidak higienis",
    "membosankan", "sama terus", "monoton",
}

NEUTRAL_WORDS = {
    "makan", "bergizi", "gratis", "program", "pemerintah", "sekolah",
    "siswa", "murid", "anak", "distribusi", "anggaran", "dana",
    "mbg", "vendor", "dapur", "katering", "menu", "porsi",
    "logistik", "daerah", "wilayah", "kemasan", "wadah",
}
