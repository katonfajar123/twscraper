"""Main Tkinter desktop dashboard for acquisition, audit, preprocessing, and mapping editor.

Designed for non-technical users and domain researchers:
- Clean, intuitive tab-based navigation
- Thread-safe background tasks to prevent GUI freezing
- Safe durable scraper execution with graceful stop flag
- Non-destructive cleansing and slang normalization
- Full audit and interactive slang dictionary editor
"""

from __future__ import annotations

import csv
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from scraper import DEFAULT_KEYWORD_CONFIG, FALLBACK_STEP1_KEYWORDS, parse_seed_ids
from keywords import KEYWORD_GROUPS

from .data_pipeline import (
    PipelineCancelled,
    PipelineError,
    PreprocessOptions,
    audit_csv,
    load_preview,
    preprocess_csv,
    read_mapping,
    write_mapping,
)
from .services import run_account_operation

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "accounts.db"
DEFAULT_MAPPING = ROOT / "output" / "MBG_Kamus_Slang_Normalisasi_2000.csv"
DEFAULT_GUI_KEYWORD_QUERIES = [
    '"makan bergizi gratis" OR "program mbg" OR "makan siang gratis"',
    '("makan bergizi" OR "mbg") AND ("prabowo" OR "gibran" OR "anggaran" OR "sekolah" OR "gizi")',
]
NUMBER_RE = re.compile(r"(?:Durable=|Total data durable\s*:)\s*([\d.,]+)")

COLOR_BG = "#eaf5ff"
COLOR_SURFACE = "#ffffff"
COLOR_PRIMARY = "#005baa"
COLOR_PRIMARY_BRIGHT = "#0072ce"
COLOR_PRIMARY_DARK = "#003f88"
COLOR_ACCENT = "#f6c443"
COLOR_TEXT = "#102a43"
COLOR_MUTED = "#486581"
COLOR_BORDER = "#a7c7e7"
COLOR_DANGER = "#b00020"
COLOR_DANGER_DARK = "#8b0018"


class TextEditAdapter:
    """Convenience adapter allowing both Tkinter text methods and PyQt-like text helpers."""

    def __init__(self, text_widget: tk.Text):
        self._w = text_widget

    def toPlainText(self) -> str:
        return self._w.get("1.0", "end-1c").strip()

    def setPlainText(self, text: str) -> None:
        self._w.delete("1.0", "end")
        self._w.insert("1.0", text)

    def get(self, *args, **kwargs) -> str:
        return self._w.get(*args, **kwargs)

    def insert(self, *args, **kwargs) -> None:
        self._w.insert(*args, **kwargs)

    def delete(self, *args, **kwargs) -> None:
        self._w.delete(*args, **kwargs)


class KeywordTableAdapter:
    """Compatibility adapter exposing text-like helpers for the keyword table."""

    def __init__(self, window: "MainWindow"):
        self._window = window

    def toPlainText(self) -> str:
        return "\n".join(self._window._current_keyword_lines())

    def setPlainText(self, text: str) -> None:
        self._window._replace_keyword_lines(text.splitlines())

    def get(self, *args, **kwargs) -> str:
        return self.toPlainText()

    def insert(self, *_args, **_kwargs) -> None:
        text = str(_args[-1]) if _args else ""
        self._window._append_keyword_lines(text.splitlines())

    def delete(self, *args, **kwargs) -> None:
        self._window._clear_keywords()


class EntryAdapter:
    """Convenience adapter allowing both StringVar/Entry methods and setText/text helpers."""

    def __init__(self, variable: tk.StringVar, entry_widget: ttk.Entry):
        self._var = variable
        self._w = entry_widget

    def text(self) -> str:
        return self._var.get().strip()

    def setText(self, value: str) -> None:
        self._var.set(value)

    def get(self) -> str:
        return self._var.get()

    def set(self, value: str) -> None:
        self._var.set(value)


class SpinAdapter:
    """Convenience adapter allowing value() and setValue()."""

    def __init__(self, variable: tk.IntVar):
        self._var = variable

    def value(self) -> int:
        return int(self._var.get())

    def setValue(self, value: int) -> None:
        self._var.set(value)


class CheckAdapter:
    """Convenience adapter for checkbox."""

    def __init__(self, variable: tk.BooleanVar):
        self._var = variable

    def isChecked(self) -> bool:
        return bool(self._var.get())

    def setChecked(self, value: bool) -> None:
        self._var.set(value)


class ComboAdapter:
    """Convenience adapter for ttk.Combobox with key-value data."""

    def __init__(self, combobox: ttk.Combobox, var: tk.StringVar, data_map: dict[str, Any]):
        self._combo = combobox
        self._var = var
        self._data_map = data_map  # label -> value

    def currentData(self) -> Any:
        label = self._var.get()
        return self._data_map.get(label, label)

    def setCurrentIndex(self, index: int) -> None:
        values = self._combo.cget("values")
        if 0 <= index < len(values):
            self._var.set(values[index])


class MainWindow(tk.Tk):
    """Main desktop application window using Tkinter."""

    def __init__(self):
        super().__init__()
        self.title("MBG Scraper & NLP Studio (Tkinter)")
        self.geometry("1200x780")
        self.minsize(980, 640)

        # Apply classic blue desktop style
        self.style = ttk.Style(self)
        available_themes = self.style.theme_names()
        if "clam" in available_themes:
            self.style.theme_use("clam")

        self._configure_styles()
        self.configure(bg=COLOR_BG)

        # State attributes
        self.process: subprocess.Popen[str] | None = None
        self.stop_file: Path | None = None
        self.scrape_target = 20_000
        self._preprocess_cancel: threading.Event | None = None
        self._active_threads: list[threading.Thread] = []

        # Mapping editor state
        self._mapping_rows: list[dict[str, str]] = []
        self._mapping_path: Path | None = None
        self.keyword_preset_map = self._build_keyword_presets()

        # Build UI layout
        self._build_header()
        self._build_tabs()
        self._build_status_bar()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # Initial background check
        self.after(500, self._refresh_system_status)

    def _configure_styles(self) -> None:
        """Set up classic bright-blue styles for Tkinter widgets."""
        self.style.configure(".", font=("Segoe UI", 9), background=COLOR_BG, foreground=COLOR_TEXT)
        self.style.configure("TFrame", background=COLOR_SURFACE)
        self.style.configure("BlueBanner.TFrame", background=COLOR_PRIMARY)
        self.style.configure("TLabel", background=COLOR_SURFACE, foreground=COLOR_TEXT)
        self.style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground="white", background=COLOR_PRIMARY)
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 10), foreground="#d7ecff", background=COLOR_PRIMARY)
        self.style.configure("TNotebook", tabposition="nw", padding=2, background=COLOR_BG, borderwidth=0)
        self.style.configure(
            "TNotebook.Tab",
            padding=[14, 8],
            font=("Segoe UI", 10, "bold"),
            background="#d7ecff",
            foreground=COLOR_PRIMARY_DARK,
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", COLOR_PRIMARY_BRIGHT), ("active", "#c3e2ff")],
            foreground=[("selected", "white"), ("active", COLOR_PRIMARY_DARK)],
        )
        self.style.configure(
            "Section.TLabelframe",
            background=COLOR_SURFACE,
            bordercolor=COLOR_ACCENT,
            relief="solid",
        )
        self.style.configure(
            "Section.TLabelframe.Label",
            font=("Segoe UI", 10, "bold"),
            foreground=COLOR_PRIMARY_DARK,
            background=COLOR_SURFACE,
        )
        self.style.configure("TButton", padding=(10, 5), background="#e8f3ff", foreground=COLOR_PRIMARY_DARK)
        self.style.map("TButton", background=[("active", "#cfe8ff")], foreground=[("disabled", "#7b8794")])
        self.style.configure("Success.TButton", font=("Segoe UI", 10, "bold"), foreground="white", background=COLOR_PRIMARY_BRIGHT)
        self.style.map("Success.TButton", background=[("active", COLOR_PRIMARY), ("disabled", "#9fb3c8")])
        self.style.configure("Action.TButton", font=("Segoe UI", 9, "bold"), foreground="white", background=COLOR_PRIMARY)
        self.style.map("Action.TButton", background=[("active", COLOR_PRIMARY_DARK), ("disabled", "#9fb3c8")])
        self.style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"), foreground="white", background=COLOR_DANGER)
        self.style.map("Danger.TButton", background=[("active", COLOR_DANGER_DARK), ("disabled", "#cbd2d9")])
        self.style.configure(
            "TEntry",
            fieldbackground="white",
            bordercolor=COLOR_BORDER,
            lightcolor=COLOR_PRIMARY_BRIGHT,
            darkcolor=COLOR_BORDER,
        )
        self.style.configure("TCombobox", fieldbackground="white", bordercolor=COLOR_BORDER, arrowcolor=COLOR_PRIMARY)
        self.style.configure("Horizontal.TProgressbar", background=COLOR_PRIMARY_BRIGHT, troughcolor="#d7ecff")
        self.style.configure("Treeview", background="white", fieldbackground="white", foreground=COLOR_TEXT, rowheight=24)
        self.style.configure("Treeview.Heading", background=COLOR_PRIMARY, foreground="white", font=("Segoe UI", 9, "bold"))

    def _build_header(self) -> None:
        """Top banner showing title and quick status."""
        banner = ttk.Frame(self, padding=(16, 12, 16, 10), style="BlueBanner.TFrame")
        banner.pack(fill="x", side="top")

        left_box = ttk.Frame(banner, style="BlueBanner.TFrame")
        left_box.pack(side="left", fill="x", expand=True)

        title = ttk.Label(left_box, text="MBG Scraper & NLP Studio", style="Header.TLabel")
        title.pack(anchor="w")

        subtitle = ttk.Label(
            left_box,
            text="Ekstraksi Data, Audit CSV, Cleansing & Normalisasi Slang - Ramah Pemula & Riset",
            style="SubHeader.TLabel",
        )
        subtitle.pack(anchor="w", pady=(2, 0))

    def _build_tabs(self) -> None:
        """Build the main 7 Notebook tabs."""
        self.tabs = ttk.Notebook(self)
        # Add compatibility helper for tab counting
        self.tabs.count = lambda: len(self.tabs.tabs())  # type: ignore[attr-defined]
        self.tabs.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        # Build each tab frame
        self.tab_home = ttk.Frame(self.tabs, padding=12)
        self.tab_account = ttk.Frame(self.tabs, padding=12)
        self.tab_extract = ttk.Frame(self.tabs, padding=12)
        self.tab_audit = ttk.Frame(self.tabs, padding=12)
        self.tab_preprocess = ttk.Frame(self.tabs, padding=12)
        self.tab_mapping = ttk.Frame(self.tabs, padding=12)
        self.tab_roadmap = ttk.Frame(self.tabs, padding=12)

        self.tabs.add(self.tab_home, text=" Beranda ")
        self.tabs.add(self.tab_account, text=" 1 · Set Up Akun ")
        self.tabs.add(self.tab_extract, text=" 2 · Ekstraksi Data ")
        self.tabs.add(self.tab_audit, text=" 3 · Audit & Data ")
        self.tabs.add(self.tab_preprocess, text=" 4 · Preprocessing ")
        self.tabs.add(self.tab_mapping, text=" 5 · Kamus Slang ")
        self.tabs.add(self.tab_roadmap, text=" 6 · Rencana NLP ")

        self._init_home_tab()
        self._init_account_tab()
        self._init_extract_tab()
        self._init_audit_tab()
        self._init_preprocess_tab()
        self._init_mapping_tab()
        self._init_roadmap_tab()

    def _build_status_bar(self) -> None:
        """Bottom status bar."""
        self.status_frame = ttk.Frame(self, relief="sunken", padding=(8, 4))
        self.status_frame.pack(fill="x", side="bottom")

        self.status_label = ttk.Label(
            self.status_frame,
            text="Siap - Silakan pilih tab di atas untuk memulai.",
            font=("Segoe UI", 9),
        )
        self.status_label.pack(side="left")

        self.status_db_label = ttk.Label(
            self.status_frame,
            text="DB: accounts.db",
            font=("Segoe UI", 8),
            foreground=COLOR_MUTED,
        )
        self.status_db_label.pack(side="right", padx=10)

    def set_status(self, text: str) -> None:
        """Update the status bar text."""
        self.status_label.config(text=text)

    # =========================================================================
    # TAB 0: BERANDA & PANDUAN
    # =========================================================================
    def _init_home_tab(self) -> None:
        f = self.tab_home

        intro_box = ttk.LabelFrame(f, text=" Selamat Datang di MBG Studio ", style="Section.TLabelframe", padding=14)
        intro_box.pack(fill="x", pady=(0, 10))

        intro_text = (
            "Aplikasi ini dirancang khusus agar siapa saja (mahasiswa, peneliti, analis, maupun pengguna awam) "
            "dapat mengumpulkan data komentar X/Twitter tentang program Makan Bergizi Gratis (MBG), "
            "memeriksa kebersihannya, dan menyiapkan teks untuk pemodelan sentimen maupun klasifikasi aspek.\n\n"
            "Semua proses dilakukan di komputer lokal Anda dengan aman tanpa mengunggah data atau password ke pihak ketiga."
        )
        ttk.Label(intro_box, text=intro_text, wraplength=920, font=("Segoe UI", 10), justify="left").pack(anchor="w")

        steps_box = ttk.LabelFrame(f, text=" Alur Kerja 5 Langkah Mudah ", style="Section.TLabelframe", padding=14)
        steps_box.pack(fill="both", expand=True, pady=(0, 10))

        steps = [
            ("Langkah 1: Set Up Akun", "Tab '1 · Set Up Akun' -> Masukkan cookie akun Twitter Anda agar scraper memiliki izin menarik data dari platform X."),
            ("Langkah 2: Ekstraksi Data", "Tab '2 · Ekstraksi Data' -> Masukkan Tweet ID utas viral atau kata kunci MBG, tentukan target baris (misal 20.000), lalu klik Mulai."),
            ("Langkah 3: Audit & Pratinjau", "Tab '3 · Audit & Data' -> Pastikan data terkumpul valid, bebas ID notasi ilmiah, tidak ada baris rusak, dan siap dianalisis."),
            ("Langkah 4: Preprocessing Teks", "Tab '4 · Preprocessing' -> Jalankan pembersihan otomatis (URL, mention, emoji) dan normalisasi kata gaul/singkatan menjadi kata baku."),
            ("Langkah 5: Kelola Kamus Slang", "Tab '5 · Kamus Slang' -> Tambah atau sesuaikan kata gaul/singkatan baru kapan saja dengan antarmuka tabel yang mudah."),
            ("Langkah 6: Rencana Model NLP", "Tab '6 · Rencana NLP' -> Pahami bagaimana data bersih ini nantinya diberi label aspek (Mutu Gizi, Tata Kelola, Distribusi) atau sentimen."),
        ]

        for title, desc in steps:
            row = ttk.Frame(steps_box)
            row.pack(fill="x", pady=4)
            lbl_title = ttk.Label(row, text=title, font=("Segoe UI", 10, "bold"), width=28, foreground=COLOR_PRIMARY_DARK)
            lbl_title.pack(side="left", anchor="n")
            lbl_desc = ttk.Label(row, text=desc, font=("Segoe UI", 9), wraplength=680, justify="left")
            lbl_desc.pack(side="left", fill="x", expand=True)

        btn_row = ttk.Frame(f)
        btn_row.pack(fill="x", pady=4)
        btn_go = ttk.Button(btn_row, text="Mulai dari Langkah 1: Set Up Akun", style="Action.TButton", command=lambda: self.tabs.select(1))
        btn_go.pack(side="left")

    # =========================================================================
    # TAB 1: SET UP AKUN
    # =========================================================================
    def _init_account_tab(self) -> None:
        f = self.tab_account

        # Left: Form Add Cookie
        left_pane = ttk.LabelFrame(f, text=" Tambah Akun via Cookie ", style="Section.TLabelframe", padding=12)
        left_pane.pack(side="left", fill="both", expand=False, padx=(0, 10))

        help_text = (
            "Untuk mengambil data, Twitter mewajibkan autentikasi akun.\n"
            "Cukup masukkan Username dan 2 nilai cookie dari browser:\n"
            "1. auth_token\n2. ct0"
        )
        ttk.Label(left_pane, text=help_text, font=("Segoe UI", 9), foreground=COLOR_MUTED, wraplength=320, justify="left").pack(anchor="w", pady=(0, 10))

        self.acc_username_var = tk.StringVar()
        ttk.Label(left_pane, text="Username Twitter (tanpa @):", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Entry(left_pane, textvariable=self.acc_username_var, width=35).pack(fill="x", pady=(2, 8))

        self.acc_token_var = tk.StringVar()
        ttk.Label(left_pane, text="Cookie auth_token:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Entry(left_pane, textvariable=self.acc_token_var, width=35, show="*").pack(fill="x", pady=(2, 8))

        self.acc_ct0_var = tk.StringVar()
        ttk.Label(left_pane, text="Cookie ct0:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Entry(left_pane, textvariable=self.acc_ct0_var, width=35, show="*").pack(fill="x", pady=(2, 12))

        btn_add = ttk.Button(left_pane, text="Simpan Akun ke Database", style="Success.TButton", command=self._add_account_cookie)
        btn_add.pack(fill="x", pady=4)

        btn_cookie_help = ttk.Button(left_pane, text="Panduan Mengambil Cookie", command=self._show_cookie_help)
        btn_cookie_help.pack(fill="x", pady=4)

        self.db_path_var = tk.StringVar(value=str(DEFAULT_DB))
        self.db_edit = EntryAdapter(self.db_path_var, ttk.Entry(left_pane))  # Compatibility adapter

        # Right: Account List
        right_pane = ttk.LabelFrame(f, text=" Daftar Akun di Database Pool ", style="Section.TLabelframe", padding=12)
        right_pane.pack(side="right", fill="both", expand=True)

        cols = ("Username", "Status", "Terakhir Dipakai", "Keterangan")
        self.acc_tree = ttk.Treeview(right_pane, columns=cols, show="headings", height=15)
        self.acc_tree.heading("Username", text="Username")
        self.acc_tree.heading("Status", text="Status")
        self.acc_tree.heading("Terakhir Dipakai", text="Terakhir Dipakai")
        self.acc_tree.heading("Keterangan", text="Keterangan / Limit")

        self.acc_tree.column("Username", width=140, anchor="w")
        self.acc_tree.column("Status", width=90, anchor="center")
        self.acc_tree.column("Terakhir Dipakai", width=160, anchor="w")
        self.acc_tree.column("Keterangan", width=200, anchor="w")

        tree_scroll = ttk.Scrollbar(right_pane, orient="vertical", command=self.acc_tree.yview)
        self.acc_tree.configure(yscrollcommand=tree_scroll.set)
        self.acc_tree.pack(side="top", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        acc_btn_row = ttk.Frame(right_pane)
        acc_btn_row.pack(fill="x", pady=(10, 0))

        ttk.Button(acc_btn_row, text="Segarkan Daftar", command=self._refresh_accounts).pack(side="left", padx=4)
        ttk.Button(acc_btn_row, text="Aktifkan Akun", command=lambda: self._set_account_active(True)).pack(side="left", padx=4)
        ttk.Button(acc_btn_row, text="Nonaktifkan Akun", command=lambda: self._set_account_active(False)).pack(side="left", padx=4)
        ttk.Button(acc_btn_row, text="Reset Kunci Rate-Limit", command=self._reset_rate_locks).pack(side="right", padx=4)

    def _show_cookie_help(self) -> None:
        msg = (
            "CARA MENDAPATKAN COOKIE DARI BROWSER (Chrome/Edge/Firefox):\n\n"
            "1. Buka https://x.com di browser dan pastikan Anda sudah login.\n"
            "2. Tekan tombol F12 pada keyboard untuk membuka Developer Tools (Inspect Element).\n"
            "3. Klik tab 'Application' (atau 'Storage' di Firefox).\n"
            "4. Di menu sebelah kiri, buka 'Cookies' -> klik 'https://x.com'.\n"
            "5. Cari nama cookie:\n"
            "   - 'auth_token' -> Klik barisnya, salin isinya dari kolom 'Value'.\n"
            "   - 'ct0' -> Klik barisnya, salin isinya dari kolom 'Value'.\n"
            "6. Tempelkan kedua nilai tersebut ke form di aplikasi ini, lalu klik Simpan.\n\n"
            "Selesai! Akun Anda siap dipakai untuk scraping."
        )
        messagebox.showinfo("Panduan Mengambil Cookie", msg)

    def _add_account_cookie(self) -> None:
        username = self.acc_username_var.get().strip().lstrip("@")
        token = self.acc_token_var.get().strip()
        ct0 = self.acc_ct0_var.get().strip()
        if not username or not token or not ct0:
            messagebox.showwarning("Form Kurang Lengkap", "Silakan isi Username, auth_token, dan ct0.")
            return

        def work():
            try:
                run_account_operation(
                    self.db_path_var.get(),
                    "add_cookies",
                    {"username": username, "auth_token": token, "ct0": ct0},
                )
                self.after(0, self._on_account_added, username)
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Gagal Menyimpan Akun", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _on_account_added(self, username: str) -> None:
        self.acc_username_var.set("")
        self.acc_token_var.set("")
        self.acc_ct0_var.set("")
        messagebox.showinfo("Sukses", f"Cookie untuk akun @{username} berhasil disimpan!")
        self._refresh_accounts()

    def _refresh_accounts(self) -> None:
        def work():
            try:
                accounts = run_account_operation(self.db_path_var.get(), "list")
                self.after(0, self._populate_accounts, accounts)
            except Exception as exc:
                self.after(0, lambda: self.set_status(f"Gagal memuat akun: {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def _populate_accounts(self, accounts: Any) -> None:
        for item in self.acc_tree.get_children():
            self.acc_tree.delete(item)

        if not accounts:
            self.set_status("Belum ada akun di database.")
            return

        active_count = 0
        for acc in accounts:
            # acc is an Account object from twscrape
            uname = getattr(acc, "username", str(acc))
            active = "Aktif" if getattr(acc, "active", False) else "Nonaktif"
            if getattr(acc, "active", False):
                active_count += 1
            last_used = getattr(acc, "last_used", "") or "-"
            msg = getattr(acc, "error_msg", "") or "Normal"
            self.acc_tree.insert("", "end", values=(f"@{uname}", active, str(last_used)[:19], msg))

        self.set_status(f"Daftar akun diperbarui. Total: {len(accounts)} akun ({active_count} aktif).")

    def _set_account_active(self, active: bool) -> None:
        selected = self.acc_tree.selection()
        if not selected:
            messagebox.showwarning("Pilih Akun", "Pilih salah satu akun di tabel terlebih dahulu.")
            return
        vals = self.acc_tree.item(selected[0], "values")
        username = vals[0].lstrip("@")

        def work():
            try:
                run_account_operation(self.db_path_var.get(), "set_active", {"username": username, "active": active})
                self.after(0, self._refresh_accounts)
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _reset_rate_locks(self) -> None:
        def work():
            try:
                run_account_operation(self.db_path_var.get(), "reset_locks")
                self.after(0, lambda: messagebox.showinfo("Reset Sukses", "Lock rate-limit lokal akun berhasil direset!"))
                self.after(0, self._refresh_accounts)
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    # =========================================================================
    # TAB 2: EKSTRAKSI DATA (SCRAPING)
    # =========================================================================
    def _init_extract_tab(self) -> None:
        f = self.tab_extract

        # Left: Settings
        left_box = ttk.Frame(f)
        left_box.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Mode frame
        mode_frame = ttk.LabelFrame(left_box, text=" Metode Ekstraksi ", style="Section.TLabelframe", padding=10)
        mode_frame.pack(fill="x", pady=(0, 8))

        self.method_data_map = {
            "Mode Hybrid (Utas Viral + Top-up Keyword) [Direkomendasikan]": 0,
            "Mode Balasan Utas Saja (Direct Replies dari Tweet ID)": 2,
            "Mode Pencarian Kata Kunci Saja (Keyword Search)": 1,
        }
        self.method_var = tk.StringVar(value=list(self.method_data_map.keys())[0])
        self.method_combo_widget = ttk.Combobox(
            mode_frame,
            textvariable=self.method_var,
            values=list(self.method_data_map.keys()),
            state="readonly",
            font=("Segoe UI", 9),
        )
        self.method_combo_widget.pack(fill="x", pady=2)
        self.method_combo = ComboAdapter(self.method_combo_widget, self.method_var, self.method_data_map)

        # Target and options row
        opt_grid = ttk.Frame(mode_frame)
        opt_grid.pack(fill="x", pady=(6, 2))

        ttk.Label(opt_grid, text="Target Data:").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.target_var = tk.IntVar(value=20000)
        ttk.Spinbox(opt_grid, from_=100, to=100000, increment=500, textvariable=self.target_var, width=10).grid(row=0, column=1, sticky="w", padx=4)
        self.target_spin = SpinAdapter(self.target_var)

        ttk.Label(opt_grid, text="Batas per Seed:").grid(row=0, column=2, sticky="w", padx=6, pady=2)
        self.limit_var = tk.IntVar(value=600)
        ttk.Spinbox(opt_grid, from_=50, to=2000, increment=50, textvariable=self.limit_var, width=8).grid(row=0, column=3, sticky="w", padx=4)
        self.limit_spin = SpinAdapter(self.limit_var)

        ttk.Label(opt_grid, text="Min Reply:").grid(row=0, column=4, sticky="w", padx=6, pady=2)
        self.min_replies_var = tk.IntVar(value=50)
        ttk.Spinbox(opt_grid, from_=0, to=500, increment=10, textvariable=self.min_replies_var, width=8).grid(row=0, column=5, sticky="w", padx=4)
        self.min_replies_spin = SpinAdapter(self.min_replies_var)

        self.delay_var = tk.IntVar(value=1)
        self.delay_spin = SpinAdapter(self.delay_var)
        self.batch_var = tk.IntVar(value=100)
        self.batch_spin = SpinAdapter(self.batch_var)
        self.lang_var = tk.StringVar(value="in")
        self.language_combo = ComboAdapter(ttk.Combobox(opt_grid), self.lang_var, {"in": "in"})

        self.nested_var = tk.BooleanVar(value=False)
        self.nested_check = CheckAdapter(self.nested_var)
        ttk.Checkbutton(mode_frame, text="Sertakan Nested Replies (Balasan dari komentar pengguna lain)", variable=self.nested_var).pack(anchor="w", pady=(4, 0))

        # Inputs frame (Seed & Keyword)
        input_box = ttk.LabelFrame(left_box, text=" Amunisi Input (Tweet ID & Query) ", style="Section.TLabelframe", padding=10)
        input_box.pack(fill="both", expand=True, pady=(0, 8))

        ttk.Label(input_box, text="Daftar Tweet ID / Link Utas Viral (satu per baris):", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.seed_text = ScrolledText(input_box, height=4, font=("Consolas", 9))
        self.seed_text.pack(fill="both", expand=True, pady=(2, 6))
        self.seed_edit = TextEditAdapter(self.seed_text)

        kw_header = ttk.Frame(input_box)
        kw_header.pack(fill="x")
        ttk.Label(kw_header, text="Kata Kunci / Boolean Search Query:", font=("Segoe UI", 9, "bold")).pack(side="left")

        keyword_tools = ttk.Frame(input_box)
        keyword_tools.pack(fill="x", pady=(2, 2))
        ttk.Label(keyword_tools, text="Preset Keyword:").pack(side="left", padx=(0, 4))
        self.keyword_preset_var = tk.StringVar(value="Query FSD Ringkas")
        self.keyword_preset_combo = ttk.Combobox(
            keyword_tools,
            textvariable=self.keyword_preset_var,
            values=list(self.keyword_preset_map.keys()),
            state="readonly",
            width=34,
            font=("Segoe UI", 9),
        )
        self.keyword_preset_combo.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(keyword_tools, text="Pakai Preset", command=lambda: self._apply_keyword_preset(False)).pack(side="left", padx=2)
        ttk.Button(keyword_tools, text="Tambah Preset", command=lambda: self._apply_keyword_preset(True)).pack(side="left", padx=2)
        ttk.Button(keyword_tools, text="Bersihkan", command=self._clear_keywords).pack(side="left", padx=2)

        keyword_file_row = ttk.Frame(input_box)
        keyword_file_row.pack(fill="x", pady=(0, 2))
        ttk.Label(keyword_file_row, text="File Keyword:").pack(side="left", padx=(0, 4))
        self.keyword_file_var = tk.StringVar(value=str(DEFAULT_KEYWORD_CONFIG))
        ttk.Entry(keyword_file_row, textvariable=self.keyword_file_var).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(keyword_file_row, text="Browse...", command=self._pick_keyword_file).pack(side="left", padx=2)
        ttk.Button(keyword_file_row, text="Muat", command=self._load_keyword_file_from_var).pack(side="left", padx=2)
        ttk.Button(keyword_file_row, text="Simpan", command=self._save_keyword_file_from_var).pack(side="left", padx=2)

        self.keyword_text = ScrolledText(input_box, height=3, font=("Consolas", 9))
        self.keyword_text.pack(fill="both", expand=True, pady=(2, 6))
        self.keyword_edit = TextEditAdapter(self.keyword_text)
        self._load_initial_keywords()

        # Files frame
        file_box = ttk.LabelFrame(left_box, text=" Lokasi Penyimpanan Hasil ", style="Section.TLabelframe", padding=8)
        file_box.pack(fill="x")

        # Output CSV
        f_row1 = ttk.Frame(file_box)
        f_row1.pack(fill="x", pady=2)
        ttk.Label(f_row1, text="File CSV:", width=12).pack(side="left")
        default_output = ROOT / "output" / f"MBG_Dataset_DirectReplies_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        self.output_path_var = tk.StringVar(value=str(default_output))
        ttk.Entry(f_row1, textvariable=self.output_path_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(f_row1, text="Browse...", command=self._pick_output_csv).pack(side="right")
        self.output_edit = EntryAdapter(self.output_path_var, ttk.Entry(f_row1))

        # Checkpoint JSON
        f_row2 = ttk.Frame(file_box)
        f_row2.pack(fill="x", pady=2)
        ttk.Label(f_row2, text="Checkpoint:", width=12).pack(side="left")
        default_cp = ROOT / "output" / "checkpoint_direct_replies.json"
        self.checkpoint_path_var = tk.StringVar(value=str(default_cp))
        ttk.Entry(f_row2, textvariable=self.checkpoint_path_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(f_row2, text="Browse...", command=self._pick_checkpoint_json).pack(side="right")
        self.checkpoint_edit = EntryAdapter(self.checkpoint_path_var, ttk.Entry(f_row2))

        self.legacy_path_var = tk.StringVar()
        self.legacy_edit = EntryAdapter(self.legacy_path_var, ttk.Entry(file_box))

        # Right: Action & Live Monitor
        right_box = ttk.LabelFrame(f, text=" Monitor Ekstraksi Real-time ", style="Section.TLabelframe", padding=10)
        right_box.pack(side="right", fill="both", expand=True)

        btn_ctrl = ttk.Frame(right_box)
        btn_ctrl.pack(fill="x", pady=(0, 6))

        self.btn_start_scrape = ttk.Button(btn_ctrl, text="Mulai Scraping", style="Success.TButton", command=self.start_scraping)
        self.btn_start_scrape.pack(side="left", padx=(0, 6), fill="x", expand=True)

        self.btn_stop_scrape = ttk.Button(btn_ctrl, text="Hentikan Scraping", style="Danger.TButton", state="disabled", command=self.stop_scraping)
        self.btn_stop_scrape.pack(side="right", fill="x", expand=True)

        # Progress
        self.scrape_progress = ttk.Progressbar(right_box, orient="horizontal", mode="determinate")
        self.scrape_progress.pack(fill="x", pady=4)

        self.scrape_status_lbl = ttk.Label(right_box, text="Status: Menunggu instruksi...", font=("Segoe UI", 9, "bold"))
        self.scrape_status_lbl.pack(anchor="w", pady=(0, 4))

        # Live log
        self.log_view = ScrolledText(right_box, height=20, bg="#002f6c", fg="#eaf5ff", font=("Consolas", 8), insertbackground="white")
        self.log_view.pack(fill="both", expand=True)

    def _fill_default_keywords(self) -> None:
        self._replace_keyword_lines(DEFAULT_GUI_KEYWORD_QUERIES)

    def _build_keyword_presets(self) -> dict[str, list[str]]:
        presets: dict[str, list[str]] = {
            "Query FSD Ringkas": DEFAULT_GUI_KEYWORD_QUERIES,
            "Keyword Scraper Lama": FALLBACK_STEP1_KEYWORDS,
        }

        grouped_lines: list[str] = []
        for group_name, lines in KEYWORD_GROUPS.items():
            clean_lines = self._dedupe_keyword_lines(lines)
            if not clean_lines:
                continue
            display_name = group_name.replace("_", " ").title()
            presets[f"Grup: {display_name}"] = clean_lines
            grouped_lines.extend(clean_lines)

        all_grouped = self._dedupe_keyword_lines(grouped_lines)
        if all_grouped:
            presets["Semua Grup Keyword Riset"] = all_grouped
        return presets

    @staticmethod
    def _dedupe_keyword_lines(lines: list[str] | tuple[str, ...]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for line in lines:
            text = str(line).strip()
            key = text.lower()
            if text and key not in seen:
                cleaned.append(text)
                seen.add(key)
        return cleaned

    def _current_keyword_lines(self) -> list[str]:
        return self._dedupe_keyword_lines(self.keyword_text.get("1.0", "end").splitlines())

    def _replace_keyword_lines(self, lines: list[str] | tuple[str, ...]) -> None:
        default_kw = "\n".join(self._dedupe_keyword_lines(lines))
        self.keyword_text.delete("1.0", "end")
        self.keyword_text.insert("1.0", default_kw)

    def _append_keyword_lines(self, lines: list[str] | tuple[str, ...]) -> None:
        merged = [*self._current_keyword_lines(), *self._dedupe_keyword_lines(lines)]
        self._replace_keyword_lines(merged)

    def _apply_keyword_preset(self, append: bool) -> None:
        label = self.keyword_preset_var.get()
        lines = self.keyword_preset_map.get(label, [])
        if append:
            self._append_keyword_lines(lines)
        else:
            self._replace_keyword_lines(lines)
        action = "ditambahkan" if append else "dipakai"
        self.set_status(f"Preset keyword '{label}' {action}: {len(lines):,} query.")

    def _clear_keywords(self) -> None:
        self.keyword_text.delete("1.0", "end")
        self.set_status("Daftar keyword dikosongkan. Isi manual, muat file, atau pilih preset sebelum scraping.")

    def _read_keyword_file(self, path: Path) -> list[str]:
        return self._dedupe_keyword_lines(path.read_text(encoding="utf-8-sig").splitlines())

    def _load_initial_keywords(self) -> None:
        path = Path(self.keyword_file_var.get().strip())
        if path.is_file():
            self._replace_keyword_lines(self._read_keyword_file(path))
            return
        self._fill_default_keywords()

    def _pick_keyword_file(self) -> None:
        chosen = filedialog.askopenfilename(
            initialdir=str(ROOT / "config"),
            title="Pilih File Keyword Scraping",
            filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if chosen:
            self.keyword_file_var.set(chosen)
            self._load_keyword_file_from_var()

    def _load_keyword_file_from_var(self) -> None:
        raw_path = self.keyword_file_var.get().strip()
        if not raw_path:
            messagebox.showwarning("Lokasi File Kosong", "Tentukan lokasi file keyword terlebih dahulu.")
            return
        path = Path(raw_path)
        if not path.is_file():
            messagebox.showwarning("File Keyword Tidak Ditemukan", f"File keyword tidak ditemukan:\n{path}")
            return
        try:
            lines = self._read_keyword_file(path)
            if not lines:
                messagebox.showwarning("File Keyword Kosong", "File keyword tidak berisi query yang dapat dipakai.")
                return
            self._replace_keyword_lines(lines)
            self.set_status(f"Keyword dimuat dari file: {len(lines):,} query.")
        except OSError as exc:
            messagebox.showerror("Gagal Membaca Keyword", str(exc))

    def _save_keyword_file_from_var(self) -> None:
        raw_path = self.keyword_file_var.get().strip()
        if not raw_path:
            messagebox.showwarning("Lokasi File Kosong", "Tentukan lokasi file keyword terlebih dahulu.")
            return
        path = Path(raw_path)
        lines = self._current_keyword_lines()
        if not lines:
            messagebox.showwarning("Daftar Keyword Kosong", "Isi minimal satu query sebelum menyimpan.")
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.set_status(f"Keyword disimpan ke file: {path}")
            messagebox.showinfo("Keyword Tersimpan", f"{len(lines):,} query disimpan ke:\n{path}")
        except OSError as exc:
            messagebox.showerror("Gagal Menyimpan Keyword", str(exc))

    def _pick_output_csv(self) -> None:
        chosen = filedialog.asksaveasfilename(
            initialdir=str(ROOT / "output"),
            title="Simpan File CSV Output",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            defaultextension=".csv",
        )
        if chosen:
            self.output_path_var.set(chosen)

    def _pick_checkpoint_json(self) -> None:
        chosen = filedialog.asksaveasfilename(
            initialdir=str(ROOT / "output"),
            title="Simpan File Checkpoint JSON",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            defaultextension=".json",
        )
        if chosen:
            self.checkpoint_path_var.set(chosen)

    def _scraper_arguments(self) -> list[str]:
        output = self.output_path_var.get().strip()
        checkpoint = self.checkpoint_path_var.get().strip()
        if not output or not checkpoint:
            raise ValueError("File output CSV dan checkpoint JSON wajib ditentukan.")

        mode = self.method_combo.currentData()
        seeds = parse_seed_ids([self.seed_text.get("1.0", "end")])
        keywords = self._current_keyword_lines()

        if mode == 2 and not seeds and not Path(checkpoint).exists():
            raise ValueError("Mode replies memerlukan minimal satu Tweet ID atau checkpoint berantrean.")
        if mode in {0, 1} and not keywords:
            raise ValueError("Minimal satu query/keyword pencarian diperlukan.")

        args = [
            "-u",
            str(ROOT / "scraper.py"),
            "--step",
            str(mode),
            "--target",
            str(self.target_var.get()),
            "--limit",
            str(self.limit_var.get()),
            "--min-replies",
            str(self.min_replies_var.get()),
            "--lang",
            str(self.lang_var.get()),
            "--delay",
            str(self.delay_var.get()),
            "--batch-size",
            str(self.batch_var.get()),
            "--output",
            output,
            "--checkpoint",
            checkpoint,
        ]
        if self.nested_var.get():
            args.append("--include-nested")
        for kw in keywords:
            args.extend(["--keyword", kw])
        for seed in seeds:
            args.extend(["--seed-id", seed])
        if self.legacy_path_var.get().strip():
            args.extend(["--import-legacy-roots", self.legacy_path_var.get().strip()])
        if self.stop_file:
            args.extend(["--stop-file", str(self.stop_file)])
        return args

    def start_scraping(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return

        self.stop_file = ROOT / "output" / f".gui_stop_{uuid.uuid4().hex}.flag"
        try:
            arguments = self._scraper_arguments()
        except ValueError as exc:
            self.stop_file = None
            messagebox.showwarning("Pengaturan Belum Lengkap", str(exc))
            return

        self.scrape_target = self.target_var.get()
        self.log_view.delete("1.0", "end")
        self.scrape_progress["value"] = 0
        self.scrape_status_lbl.config(text="Status: Memulai engine scraper...")
        self.btn_start_scrape.config(state="disabled")
        self.btn_stop_scrape.config(state="normal")
        self.set_status("Ekstraksi berjalan di latar belakang...")

        cmd = [sys.executable] + arguments
        env = os.environ.copy()
        env["TWS_DB"] = self.db_path_var.get().strip() or str(DEFAULT_DB)

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(ROOT),
                env=env,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as exc:
            self.btn_start_scrape.config(state="normal")
            self.btn_stop_scrape.config(state="disabled")
            messagebox.showerror("Gagal Menjalankan Scraper", str(exc))
            return

        # Start stdout reader thread
        threading.Thread(target=self._scrape_reader_thread, daemon=True).start()

    def _scrape_reader_thread(self) -> None:
        if not self.process or not self.process.stdout:
            return
        for line in iter(self.process.stdout.readline, ""):
            if not line:
                break
            self.after(0, self._append_scrape_log, line)
        self.process.wait()
        exit_code = self.process.returncode
        self.after(0, self._scrape_finished, exit_code)

    def _append_scrape_log(self, line: str) -> None:
        self.log_view.insert("end", line)
        self.log_view.see("end")

        # Parse durable progress
        match = NUMBER_RE.search(line)
        if match:
            raw_num = match.group(1).replace(".", "").replace(",", "")
            try:
                durable = int(raw_num)
                pct = min(100.0, (durable / max(1, self.scrape_target)) * 100.0)
                self.scrape_progress["value"] = pct
                self.scrape_status_lbl.config(text=f"Terkumpul: {durable:,} / {self.scrape_target:,} data ({pct:.1f}%)")
            except ValueError:
                pass

    def _scrape_finished(self, exit_code: int) -> None:
        self.btn_start_scrape.config(state="normal")
        self.btn_stop_scrape.config(state="disabled")
        if self.stop_file and self.stop_file.exists():
            try:
                self.stop_file.unlink()
            except OSError:
                pass
        self.stop_file = None

        if exit_code == 0:
            self.scrape_status_lbl.config(text="Status: Ekstraksi selesai!")
            self.set_status("Ekstraksi data selesai dengan sukses.")
            messagebox.showinfo("Selesai", "Ekstraksi data selesai. Anda dapat memeriksa hasilnya di tab '3 · Audit & Data'.")
        else:
            self.scrape_status_lbl.config(text=f"Status: Scraper berhenti (kode: {exit_code})")
            self.set_status("Scraper terhenti atau dibatalkan.")

    def stop_scraping(self) -> None:
        if self.stop_file:
            self.stop_file.touch(exist_ok=True)
            self.scrape_status_lbl.config(text="Mengirim sinyal stop aman... Menunggu checkpoint tersimpan.")
            self.set_status("Menunggu proses scraper berhenti secara aman...")
        else:
            if self.process:
                self.process.terminate()

    # =========================================================================
    # TAB 3: AUDIT & MONITOR DATA
    # =========================================================================
    def _init_audit_tab(self) -> None:
        f = self.tab_audit

        # Top file selection
        top_bar = ttk.Frame(f)
        top_bar.pack(fill="x", pady=(0, 8))

        ttk.Label(top_bar, text="Pilih File CSV:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        self.audit_file_var = tk.StringVar()
        self.audit_entry = ttk.Entry(top_bar, textvariable=self.audit_file_var)
        self.audit_entry.pack(side="left", fill="x", expand=True, padx=4)

        # Auto-detect latest CSV
        self._auto_detect_latest_csv()

        ttk.Button(top_bar, text="Browse...", command=self._pick_audit_file).pack(side="left", padx=4)
        ttk.Button(top_bar, text="Jalankan Audit", style="Action.TButton", command=self._run_audit).pack(side="left", padx=4)
        ttk.Button(top_bar, text="Buka Folder", command=self._open_output_folder).pack(side="left", padx=4)

        # Middle: Report text and stats
        mid_pane = ttk.PanedWindow(f, orient="vertical")
        mid_pane.pack(fill="both", expand=True)

        # Report box
        report_frame = ttk.LabelFrame(mid_pane, text=" Laporan Hasil Audit & Kualitas Data ", style="Section.TLabelframe", padding=8)
        mid_pane.add(report_frame, weight=1)

        self.audit_report_text = ScrolledText(report_frame, height=9, font=("Consolas", 9))
        self.audit_report_text.pack(fill="both", expand=True)
        self.audit_report_text.insert(
            "1.0",
            "Pilih file CSV di atas lalu klik 'Jalankan Audit' untuk memeriksa:\n"
            "- Total baris & keunikan Tweet ID (memastikan ID tidak terpotong atau duplikat)\n"
            "- Deteksi kerusakan notasi ilmiah Excel (misal 2.09E+18)\n"
            "- Validasi relasi Direct Reply vs Root Tweet\n"
            "- Distribusi bahasa dan sumber data",
        )

        # Preview table
        preview_frame = ttk.LabelFrame(mid_pane, text=" Pratinjau 200 Baris Data Terbaru ", style="Section.TLabelframe", padding=8)
        mid_pane.add(preview_frame, weight=2)

        self.preview_tree = ttk.Treeview(preview_frame, show="headings", height=8)
        p_scroll_y = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_tree.yview)
        p_scroll_x = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.preview_tree.xview)
        self.preview_tree.configure(yscrollcommand=p_scroll_y.set, xscrollcommand=p_scroll_x.set)

        self.preview_tree.pack(side="top", fill="both", expand=True)
        p_scroll_y.pack(side="right", fill="y")
        p_scroll_x.pack(side="bottom", fill="x")

        # Row actions
        row_act = ttk.Frame(preview_frame)
        row_act.pack(fill="x", pady=(4, 0))
        ttk.Button(row_act, text="Salin Teks Baris Terpilih", command=self._copy_selected_preview).pack(side="left")
        ttk.Button(row_act, text="Gunakan File Ini di Tab Preprocessing", command=self._send_to_preprocess).pack(side="left", padx=8)

    def _auto_detect_latest_csv(self) -> None:
        out_dir = ROOT / "output"
        if out_dir.exists():
            csvs = list(out_dir.glob("*.csv"))
            if csvs:
                latest = max(csvs, key=lambda p: p.stat().st_mtime)
                self.audit_file_var.set(str(latest))

    def _pick_audit_file(self) -> None:
        chosen = filedialog.askopenfilename(
            initialdir=str(ROOT / "output"),
            title="Pilih File CSV untuk Diaudit",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if chosen:
            self.audit_file_var.set(chosen)

    def _open_output_folder(self) -> None:
        out_dir = ROOT / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(out_dir))
        else:
            subprocess.run(["xdg-open", str(out_dir)], check=False)

    def _run_audit(self) -> None:
        path = Path(self.audit_file_var.get().strip())
        if not path.is_file():
            messagebox.showwarning("File Tidak Ditemukan", f"File tidak ditemukan:\n{path}")
            return

        self.set_status("Menjalankan audit dataset...")
        self.audit_report_text.delete("1.0", "end")
        self.audit_report_text.insert("1.0", "Memeriksa dataset... Harap tunggu...")

        def work():
            try:
                res = audit_csv(path)
                headers, rows = load_preview(path, limit=200)
                self.after(0, self._show_audit_results, res, headers, rows)
            except Exception as exc:
                self.after(0, lambda: self.audit_report_text.delete("1.0", "end"))
                self.after(0, lambda: self.audit_report_text.insert("1.0", f"Gagal audit: {exc}"))
                self.after(0, lambda: messagebox.showerror("Gagal Audit", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _show_audit_results(self, audit: dict, headers: list[str], rows: list[list[str]]) -> None:
        self.audit_report_text.delete("1.0", "end")

        ok_tag = "LULUS" if audit.get("contract_ok") else "PERHATIAN / KONTRAK GAGAL"
        invalid_direct = audit.get("invalid_direct_relations", 0)
        direct_rel_status = "Valid" if invalid_direct == 0 else f"Rusak: {invalid_direct}"
        lines = [
            f"=== HASIL AUDIT DATASET ({ok_tag}) ===",
            f"File Target          : {audit.get('path')}",
            f"Encoding UTF-8 BOM   : {'Ya (utf-8-sig, aman dibuka di Excel)' if audit.get('utf8_bom') else 'Bukan UTF-8 BOM'}",
            f"Total Baris Fisik    : {audit.get('physical_lines'):,}",
            f"Total Record Logis   : {audit.get('total_rows'):,}",
            f"Tweet ID Unik        : {audit.get('unique_tweet_ids'):,}",
            f"Duplikat Tweet ID    : {audit.get('duplicate_rows'):,} (Target: 0)",
            f"ID Notasi Ilmiah     : {audit.get('scientific_notation_ids'):,} (Target: 0, jika ada presisi ID rusak oleh Excel)",
            f"Jumlah Root Tweet    : {audit.get('root_rows'):,}",
            f"Cakupan Root Utas    : {audit.get('root_coverage'):,}",
            f"Direct Reply Relasi  : {direct_rel_status}",
            f"Orphan Direct Reply  : {audit.get('orphan_direct_replies'):,} (Balasan tanpa tweet root)",
            f"Distribusi Hierarki  : {json.dumps(audit.get('hierarchy_distribution', {}), ensure_ascii=False)}",
            f"Distribusi Sumber    : {json.dumps(audit.get('source_distribution', {}), ensure_ascii=False)}",
        ]
        if audit.get("contract_errors"):
            lines.append("\nDAFTAR KESALAHAN KONTRAK:")
            for err in audit["contract_errors"]:
                lines.append(f" - {err}")
        else:
            lines.append("\nSemua verifikasi integritas data terpenuhi dengan sempurna!")

        self.audit_report_text.insert("1.0", "\n".join(lines))

        # Populate preview Treeview
        self.preview_tree["columns"] = headers
        for h in headers:
            self.preview_tree.heading(h, text=h)
            self.preview_tree.column(h, width=130, anchor="w")
        if "Teks_Komentar" in headers:
            self.preview_tree.column("Teks_Komentar", width=350, anchor="w")

        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)

        for row in rows:
            self.preview_tree.insert("", "end", values=row)

        self.set_status(f"Audit selesai. {audit.get('total_rows'):,} baris diperiksa.")

    def _copy_selected_preview(self) -> None:
        sel = self.preview_tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Pilih salah satu baris di tabel pratinjau terlebih dahulu.")
            return
        vals = self.preview_tree.item(sel[0], "values")
        text_to_copy = "\t".join(str(v) for v in vals)
        self.clipboard_clear()
        self.clipboard_append(text_to_copy)
        messagebox.showinfo("Tersalin", "Data baris berhasil disalin ke clipboard!")

    def _send_to_preprocess(self) -> None:
        fpath = self.audit_file_var.get().strip()
        if fpath:
            self.pre_input_var.set(fpath)
            # Suggest output
            p = Path(fpath)
            out_p = p.with_name(f"{p.stem}_preprocessed.csv")
            self.pre_output_var.set(str(out_p))
            self.tabs.select(4)  # Switch to Preprocess tab

    # =========================================================================
    # TAB 4: PREPROCESSING (CLEANSING & NORMALISASI)
    # =========================================================================
    def _init_preprocess_tab(self) -> None:
        f = self.tab_preprocess

        desc_box = ttk.LabelFrame(f, text=" Apa itu Cleansing & Normalisasi? ", style="Section.TLabelframe", padding=10)
        desc_box.pack(fill="x", pady=(0, 8))

        guide = (
            "• Cleansing: Membersihkan gangguan seperti URL berita/spam, mention akun pengguna (@username), "
            "emoji berlebihan, atau tanda baca rusak.\n"
            "• Normalisasi: Mengubah kata singkatan / bahasa gaul (slang) menjadi kata baku (misal: 'gk' -> 'tidak', 'yg' -> 'yang') "
            "berdasarkan kamus pemetaan (mapping dictionary).\n"
            "• Keamanan Data: Teks mentah asli TIDAK DIHAPUS. Sistem menambahkan dua kolom baru: 'Content_Cleansing' dan 'Content_Normalisasi'."
        )
        ttk.Label(desc_box, text=guide, font=("Segoe UI", 9), wraplength=920, justify="left").pack(anchor="w")

        # Paths
        p_paths = ttk.LabelFrame(f, text=" Berkas Data & Kamus ", style="Section.TLabelframe", padding=10)
        p_paths.pack(fill="x", pady=(0, 8))

        # Input
        r1 = ttk.Frame(p_paths)
        r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="CSV Sumber Data:", width=18, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.pre_input_var = tk.StringVar()
        ttk.Entry(r1, textvariable=self.pre_input_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(r1, text="Browse...", command=lambda: self._pick_file(self.pre_input_var, "CSV Files", "*.csv")).pack(side="right")

        # Mapping
        r2 = ttk.Frame(p_paths)
        r2.pack(fill="x", pady=2)
        ttk.Label(r2, text="Kamus Slang (Mapping):", width=18, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.pre_mapping_var = tk.StringVar(value=str(DEFAULT_MAPPING))
        ttk.Entry(r2, textvariable=self.pre_mapping_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(r2, text="Browse...", command=lambda: self._pick_file(self.pre_mapping_var, "CSV Files", "*.csv")).pack(side="right")

        # Output
        r3 = ttk.Frame(p_paths)
        r3.pack(fill="x", pady=2)
        ttk.Label(r3, text="CSV Hasil Bersih:", width=18, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.pre_output_var = tk.StringVar()
        ttk.Entry(r3, textvariable=self.pre_output_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(r3, text="Browse...", command=self._pick_pre_output).pack(side="right")

        # Options
        opt_box = ttk.LabelFrame(f, text=" Pilihan Pembersihan (Cleansing & Normalisasi Rules) ", style="Section.TLabelframe", padding=10)
        opt_box.pack(fill="x", pady=(0, 8))

        g = ttk.Frame(opt_box)
        g.pack(fill="x")

        self.pre_lower_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(g, text="Ubah huruf kecil semua (Lowercase)", variable=self.pre_lower_var).grid(row=0, column=0, sticky="w", padx=10, pady=2)

        self.pre_norm_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(g, text="Terapkan Normalisasi Slang (Ganti kata gaul jadi baku)", variable=self.pre_norm_var).grid(row=0, column=1, sticky="w", padx=10, pady=2)

        self.pre_emoji_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(g, text="Pertahankan Emoji (Bermanfaat untuk deteksi sentimen)", variable=self.pre_emoji_var).grid(row=1, column=0, sticky="w", padx=10, pady=2)

        self.pre_punct_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(g, text="Pertahankan Tanda Baca", variable=self.pre_punct_var).grid(row=1, column=1, sticky="w", padx=10, pady=2)

        # URL Mode
        ttk.Label(g, text="Penanganan URL:").grid(row=2, column=0, sticky="w", padx=10, pady=(6, 2))
        self.pre_url_var = tk.StringVar(value="Ganti dengan token 'url'")
        self.url_map = {"Ganti dengan token 'url'": "token", "Hapus URL": "remove", "Pertahankan URL": "keep"}
        ttk.Combobox(g, textvariable=self.pre_url_var, values=list(self.url_map.keys()), state="readonly", width=25).grid(row=2, column=1, sticky="w", padx=10, pady=(6, 2))

        # Mention Mode
        ttk.Label(g, text="Penanganan Mention (@user):").grid(row=3, column=0, sticky="w", padx=10, pady=2)
        self.pre_mention_var = tk.StringVar(value="Ganti dengan token 'user'")
        self.mention_map = {"Ganti dengan token 'user'": "token", "Hapus mention": "remove", "Pertahankan mention": "keep"}
        ttk.Combobox(g, textvariable=self.pre_mention_var, values=list(self.mention_map.keys()), state="readonly", width=25).grid(row=3, column=1, sticky="w", padx=10, pady=2)

        # Actions
        act_row = ttk.Frame(f)
        act_row.pack(fill="x", pady=4)

        self.btn_run_pre = ttk.Button(act_row, text="Jalankan Cleansing & Normalisasi", style="Success.TButton", command=self.run_preprocessing)
        self.btn_run_pre.pack(side="left", padx=(0, 6))

        self.btn_cancel_pre = ttk.Button(act_row, text="Batalkan", style="Danger.TButton", state="disabled", command=self.cancel_preprocessing)
        self.btn_cancel_pre.pack(side="left")

        self.pre_progress = ttk.Progressbar(f, orient="horizontal", mode="determinate")
        self.pre_progress.pack(fill="x", pady=4)

        self.pre_result_text = ScrolledText(f, height=6, font=("Consolas", 9))
        self.pre_result_text.pack(fill="both", expand=True)

    def _pick_file(self, var: tk.StringVar, title: str, pattern: str) -> None:
        chosen = filedialog.askopenfilename(
            initialdir=str(ROOT / "output"),
            title=f"Pilih {title}",
            filetypes=[(title, pattern), ("All Files", "*.*")],
        )
        if chosen:
            var.set(chosen)

    def _pick_pre_output(self) -> None:
        chosen = filedialog.asksaveasfilename(
            initialdir=str(ROOT / "output"),
            title="Simpan CSV Hasil Preprocessing",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            defaultextension=".csv",
        )
        if chosen:
            self.pre_output_var.set(chosen)

    def run_preprocessing(self) -> None:
        in_path = self.pre_input_var.get().strip()
        out_path = self.pre_output_var.get().strip()
        map_path = self.pre_mapping_var.get().strip()

        if not in_path or not Path(in_path).is_file():
            messagebox.showwarning("File Tidak Ditemukan", "Pilih file CSV sumber terlebih dahulu.")
            return
        if not out_path:
            # Auto name
            p = Path(in_path)
            out_path = str(p.with_name(f"{p.stem}_preprocessed.csv"))
            self.pre_output_var.set(out_path)

        options = PreprocessOptions(
            lowercase=self.pre_lower_var.get(),
            url_mode=self.url_map.get(self.pre_url_var.get(), "token"),
            mention_mode=self.mention_map.get(self.pre_mention_var.get(), "token"),
            preserve_emoji=self.pre_emoji_var.get(),
            preserve_punctuation=self.pre_punct_var.get(),
            normalize_slang=self.pre_norm_var.get(),
        )

        self._preprocess_cancel = threading.Event()
        self.btn_run_pre.config(state="disabled")
        self.btn_cancel_pre.config(state="normal")
        self.pre_progress["value"] = 0
        self.pre_result_text.delete("1.0", "end")
        self.pre_result_text.insert("1.0", "Memulai proses cleansing dan normalisasi...\n")
        self.set_status("Preprocessing sedang berjalan...")

        def progress_cb(current: int, total: int):
            pct = (current / max(1, total)) * 100.0
            self.after(0, lambda: self.pre_progress.configure(value=pct))
            self.after(0, lambda: self.set_status(f"Preprocessing: {current:,} / {total:,} baris ({pct:.1f}%)..."))

        def work():
            try:
                res = preprocess_csv(
                    Path(in_path),
                    Path(out_path),
                    mapping_path=Path(map_path) if options.normalize_slang else None,
                    options=options,
                    overwrite=True,
                    progress=progress_cb,
                    cancel_event=self._preprocess_cancel,
                )
                self.after(0, self._on_preprocess_success, res)
            except PipelineCancelled:
                self.after(0, lambda: self._on_preprocess_error("Proses preprocessing dibatalkan oleh pengguna."))
            except Exception as exc:
                self.after(0, lambda: self._on_preprocess_error(str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def cancel_preprocessing(self) -> None:
        if self._preprocess_cancel:
            self._preprocess_cancel.set()
            self.set_status("Membatalkan preprocessing...")

    def _on_preprocess_success(self, res: dict) -> None:
        self.btn_run_pre.config(state="normal")
        self.btn_cancel_pre.config(state="disabled")
        self.pre_progress["value"] = 100

        summary = (
            "PROSES PREPROCESSING SELESAI DENGAN SUKSES\n\n"
            f"- File Sumber      : {res.get('input')}\n"
            f"- File Hasil       : {res.get('output')}\n"
            f"- Total Baris      : {res.get('rows'):,}\n"
            f"- Kamus Terpasang  : {res.get('mapping_entries'):,} kata baku\n"
            f"- Baris Terpengaruh: {res.get('rows_changed_by_normalization'):,} baris dinormalisasi\n"
            f"- Format Output    : UTF-8 with BOM (utf-8-sig, aman dibuka di Excel)\n\n"
            "Data baru ini sekarang memiliki kolom 'Content_Cleansing' dan 'Content_Normalisasi' "
            "yang siap digunakan untuk pelatihan model NLP atau analisis sentimen."
        )
        self.pre_result_text.delete("1.0", "end")
        self.pre_result_text.insert("1.0", summary)
        self.set_status("Preprocessing selesai.")
        messagebox.showinfo("Sukses Preprocessing", "Data berhasil dibersihkan dan dinormalisasi!")

    def _on_preprocess_error(self, err: str) -> None:
        self.btn_run_pre.config(state="normal")
        self.btn_cancel_pre.config(state="disabled")
        self.pre_result_text.insert("end", f"\nGagal: {err}\n")
        self.set_status(f"Error: {err}")
        messagebox.showerror("Gagal Preprocessing", err)

    # =========================================================================
    # TAB 5: EDITOR KAMUS SLANG (MAPPING)
    # =========================================================================
    def _init_mapping_tab(self) -> None:
        f = self.tab_mapping

        # Top file bar
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 6))

        ttk.Label(top, text="File Kamus Slang:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        self.mapping_file_var = tk.StringVar(value=str(DEFAULT_MAPPING))
        ttk.Entry(top, textvariable=self.mapping_file_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(top, text="Browse...", command=self._pick_mapping_file).pack(side="left", padx=2)
        ttk.Button(top, text="Buka Kamus", style="Action.TButton", command=self._load_mapping_data).pack(side="left", padx=2)
        ttk.Button(top, text="Simpan Perubahan", style="Success.TButton", command=self._save_mapping_data).pack(side="left", padx=2)
        ttk.Button(top, text="Simpan Sebagai...", command=self._save_mapping_as).pack(side="left", padx=2)

        # Search bar
        search_box = ttk.Frame(f)
        search_box.pack(fill="x", pady=(0, 6))
        ttk.Label(search_box, text="Cari Kata Slang / Baku:", font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.mapping_search_var = tk.StringVar()
        self.mapping_search_var.trace_add("write", lambda *_: self._filter_mapping_table())
        ttk.Entry(search_box, textvariable=self.mapping_search_var, width=30).pack(side="left")
        ttk.Button(search_box, text="Hapus Pencarian", command=lambda: self.mapping_search_var.set("")).pack(side="left", padx=6)
        self.mapping_count_lbl = ttk.Label(search_box, text="Memuat...", font=("Segoe UI", 9, "italic"), foreground=COLOR_MUTED)
        self.mapping_count_lbl.pack(side="right")

        # Split: Table (Left/Center) and Edit Form (Right)
        body = ttk.Frame(f)
        body.pack(fill="both", expand=True)

        # Treeview
        tree_frame = ttk.Frame(body)
        tree_frame.pack(side="left", fill="both", expand=True)

        m_cols = ("slang", "kata_baku", "frekuensi")
        self.mapping_tree = ttk.Treeview(tree_frame, columns=m_cols, show="headings", height=16)
        self.mapping_tree.heading("slang", text="Kata Gaul / Slang")
        self.mapping_tree.heading("kata_baku", text="Kata Baku Pengganti")
        self.mapping_tree.heading("frekuensi", text="Frekuensi Kemunculan")

        self.mapping_tree.column("slang", width=180, anchor="w")
        self.mapping_tree.column("kata_baku", width=220, anchor="w")
        self.mapping_tree.column("frekuensi", width=120, anchor="center")

        m_scrolly = ttk.Scrollbar(tree_frame, orient="vertical", command=self.mapping_tree.yview)
        self.mapping_tree.configure(yscrollcommand=m_scrolly.set)
        self.mapping_tree.pack(side="left", fill="both", expand=True)
        m_scrolly.pack(side="right", fill="y")

        self.mapping_tree.bind("<<TreeviewSelect>>", self._on_mapping_select)

        # Edit form (Right pane)
        form_box = ttk.LabelFrame(body, text=" Tambah / Ubah Kata ", style="Section.TLabelframe", padding=12)
        form_box.pack(side="right", fill="y", padx=(10, 0))

        ttk.Label(form_box, text="Kata Gaul / Slang (Kecil):", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.m_slang_var = tk.StringVar()
        ttk.Entry(form_box, textvariable=self.m_slang_var, width=28).pack(fill="x", pady=(2, 8))

        ttk.Label(form_box, text="Kata Baku Pengganti:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.m_baku_var = tk.StringVar()
        ttk.Entry(form_box, textvariable=self.m_baku_var, width=28).pack(fill="x", pady=(2, 8))

        ttk.Label(form_box, text="Frekuensi (opsional):", font=("Segoe UI", 9)).pack(anchor="w")
        self.m_freq_var = tk.StringVar(value="1")
        ttk.Entry(form_box, textvariable=self.m_freq_var, width=28).pack(fill="x", pady=(2, 12))

        ttk.Button(form_box, text="Tambah / Perbarui Kata", style="Action.TButton", command=self._add_or_update_mapping).pack(fill="x", pady=4)
        ttk.Button(form_box, text="Hapus Kata Terpilih", style="Danger.TButton", command=self._delete_mapping_row).pack(fill="x", pady=4)
        ttk.Button(form_box, text="Bersihkan Form", command=self._clear_mapping_form).pack(fill="x", pady=4)

        info_lbl = ttk.Label(
            form_box,
            text="Tips: Jangan membuat slang yang sama persis dengan kata baku (misal: 'mbg' -> 'mbg'). "
            "Kamus ini digunakan otomatis di Tab 4 Preprocessing.",
            wraplength=220,
            font=("Segoe UI", 8),
            foreground=COLOR_MUTED,
        )
        info_lbl.pack(fill="x", pady=(14, 0))

        # Auto-load default mapping on startup
        self.after(600, self._load_mapping_data)

    def _pick_mapping_file(self) -> None:
        chosen = filedialog.askopenfilename(
            initialdir=str(ROOT / "output"),
            title="Pilih File Kamus Slang CSV",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )
        if chosen:
            self.mapping_file_var.set(chosen)
            self._load_mapping_data()

    def _load_mapping_data(self) -> None:
        p = Path(self.mapping_file_var.get().strip())
        if not p.is_file():
            self.mapping_count_lbl.config(text="File kamus tidak ditemukan.")
            return

        try:
            self._mapping_rows = read_mapping(p)
            self._mapping_path = p
            self._filter_mapping_table()
            self.set_status(f"Kamus slang dimuat: {len(self._mapping_rows):,} entri.")
        except Exception as exc:
            messagebox.showerror("Gagal Membaca Kamus", str(exc))

    def _filter_mapping_table(self) -> None:
        q = self.mapping_search_var.get().strip().lower()
        for item in self.mapping_tree.get_children():
            self.mapping_tree.delete(item)

        count = 0
        for row in self._mapping_rows:
            slang = row.get("slang", "")
            baku = row.get("kata_baku", "")
            freq = row.get("frekuensi", "")
            if not q or q in slang.lower() or q in baku.lower():
                self.mapping_tree.insert("", "end", values=(slang, baku, freq))
                count += 1

        self.mapping_count_lbl.config(text=f"Menampilkan {count:,} dari {len(self._mapping_rows):,} entri")

    def _on_mapping_select(self, _event=None) -> None:
        sel = self.mapping_tree.selection()
        if sel:
            vals = self.mapping_tree.item(sel[0], "values")
            self.m_slang_var.set(vals[0])
            self.m_baku_var.set(vals[1])
            self.m_freq_var.set(vals[2] if len(vals) > 2 else "1")

    def _clear_mapping_form(self) -> None:
        self.m_slang_var.set("")
        self.m_baku_var.set("")
        self.m_freq_var.set("1")

    def _add_or_update_mapping(self) -> None:
        slang = self.m_slang_var.get().strip().lower()
        baku = self.m_baku_var.get().strip().lower()
        freq = self.m_freq_var.get().strip() or "1"

        if not slang or not baku:
            messagebox.showwarning("Form Belum Lengkap", "Kata gaul (slang) dan kata baku wajib diisi.")
            return
        if slang == baku:
            messagebox.showwarning("Mapping Identitas", "Kata gaul tidak boleh sama persis dengan kata baku.")
            return

        # Check existing
        found = False
        for row in self._mapping_rows:
            if row["slang"] == slang:
                row["kata_baku"] = baku
                row["frekuensi"] = freq
                found = True
                break

        if not found:
            self._mapping_rows.append({"slang": slang, "kata_baku": baku, "frekuensi": freq})
            self._mapping_rows.sort(key=lambda r: r["slang"])

        self._filter_mapping_table()
        self.set_status(f"Kata '{slang}' {'diperbarui' if found else 'ditambahkan'}. Jangan lupa klik 'Simpan Perubahan'.")

    def _delete_mapping_row(self) -> None:
        slang = self.m_slang_var.get().strip().lower()
        if not slang:
            messagebox.showwarning("Pilih Baris", "Pilih baris yang ingin dihapus terlebih dahulu.")
            return

        self._mapping_rows = [r for r in self._mapping_rows if r["slang"] != slang]
        self._clear_mapping_form()
        self._filter_mapping_table()
        self.set_status(f"Kata '{slang}' telah dihapus dari daftar sementara.")

    def _save_mapping_data(self) -> None:
        if not self._mapping_path:
            self._save_mapping_as()
            return
        try:
            write_mapping(self._mapping_path, self._mapping_rows, overwrite=True)
            messagebox.showinfo("Tersimpan", f"Kamus berhasil disimpan ke:\n{self._mapping_path}")
            self.set_status(f"Kamus berhasil disimpan ({len(self._mapping_rows):,} entri).")
        except Exception as exc:
            messagebox.showerror("Gagal Menyimpan", str(exc))

    def _save_mapping_as(self) -> None:
        chosen = filedialog.asksaveasfilename(
            initialdir=str(ROOT / "output"),
            title="Simpan Kamus Slang Sebagai...",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            defaultextension=".csv",
        )
        if chosen:
            try:
                write_mapping(Path(chosen), self._mapping_rows, overwrite=True)
                self._mapping_path = Path(chosen)
                self.mapping_file_var.set(chosen)
                messagebox.showinfo("Tersimpan", f"Kamus berhasil disimpan ke:\n{chosen}")
            except Exception as exc:
                messagebox.showerror("Gagal Menyimpan", str(exc))

    # =========================================================================
    # TAB 6: RENCANA MASA DEPAN (NLP ROADMAP & LABELING)
    # =========================================================================
    def _init_roadmap_tab(self) -> None:
        f = self.tab_roadmap

        desc_box = ttk.LabelFrame(f, text=" Roadmap: Setelah Preprocessing, Apa Langkah Selanjutnya? ", style="Section.TLabelframe", padding=12)
        desc_box.pack(fill="both", expand=True)

        info_text = (
            "Banyak pengguna awam bingung: setelah data tweet di-cleansing dan dinormalisasi, apa yang harus dilakukan?\n\n"
            "Berikut adalah panduan ilmiah dan teknis sesuai standar FSD MBG:\n\n"
            "1. MEMBEDAKAN ASPEK VS SENTIMEN (JANGAN DICAMPUR!)\n"
            "   • Aspek adalah TOPIK/MASALAH operasional MBG yang dibahas:\n"
            "     1. Mutu_Gizi   : Porsi makan, gizi/nutrisi, rasa lauk, variasi menu, makanan basi/keracunan.\n"
            "     2. Tata_Kelola : Standar dapur/SPPG, transparansi anggaran, mark-up dana, respon pengaduan.\n"
            "     3. Distribusi  : Keterlambatan jadwal pengiriman, jangkauan sekolah di 3T, kemasan tumpah/rusak.\n"
            "   • Sentimen adalah SIKAP/POLARITAS: Positif, Netral, Negatif.\n"
            "   • Sentimen dan Aspek adalah dua sumbu analisis terpisah, tidak boleh digabung menjadi satu kelas target.\n\n"
            "2. KENAPA KEYWORD TIDAK BOLEH MENJADI GROUND TRUTH OTOMATIS?\n"
            "   • Pelabelan otomatis hanya berbasis kata kunci menghasilkan bias yang sangat besar.\n"
            "   • Banyak komentar netizen yang sarkas atau pendek (misal: 'parah banget', 'setuju', 'harus dievaluasi').\n"
            "   • Komentar pendek hanya bisa dipahami jika dibaca bersama teks tweet utamanya (Root Tweet Context).\n\n"
            "3. TAHAP ANOTASI MANUSIA (PILOT 300 & GROUND TRUTH)\n"
            "   • Di folder NB-Models, disiapkan file template anotasi yang menggabungkan Direct Reply dengan Teks Root.\n"
            "   • Dua orang penilai (Annotator 1 & Annotator 2) memberi label secara independen.\n"
            "   • Jika terjadi selisih, dilakukan adjudikasi oleh reviewer untuk menetapkan label final.\n\n"
            "4. PELATIHAN MODEL MACHINE LEARNING\n"
            "   • Setelah data berlabel tersedia, model Naive Bayes (Complement Naive Bayes / MNB) atau IndoBERT\n"
            "     dapat dilatih menggunakan group-split bebas kebocoran root (zero leakage)."
        )
        t = ScrolledText(desc_box, wrap="word", font=("Segoe UI", 10), padx=8, pady=8)
        t.pack(fill="both", expand=True)
        t.insert("1.0", info_text)
        t.config(state="disabled")

        btn_bar = ttk.Frame(f)
        btn_bar.pack(fill="x", pady=(8, 0))

        ttk.Button(btn_bar, text="Buka Panduan Pelabelan (LABELING_GUIDE.md)", command=lambda: self._open_doc("NB-Models/LABELING_GUIDE.md")).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Buka Dokumentasi Arsitektur (DOCUMENTATION.md)", command=lambda: self._open_doc("NB-Models/DOCUMENTATION.md")).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Buka Folder NB-Models di Explorer", command=lambda: self._open_folder(ROOT / "NB-Models")).pack(side="left", padx=4)

    def _open_doc(self, rel_path: str) -> None:
        p = ROOT / rel_path
        if p.exists():
            if sys.platform == "win32":
                os.startfile(str(p))
            else:
                webbrowser.open(p.as_uri())
        else:
            messagebox.showwarning("File Tidak Ditemukan", f"Dokumentasi belum ada:\n{p}")

    def _open_folder(self, folder: Path) -> None:
        if folder.exists():
            if sys.platform == "win32":
                os.startfile(str(folder))
            else:
                subprocess.run(["xdg-open", str(folder)], check=False)

    # =========================================================================
    # SYSTEM STATUS & CLEANUP
    # =========================================================================
    def _refresh_system_status(self) -> None:
        """Periodic background status updater."""
        db_exists = DEFAULT_DB.is_file()
        self.status_db_label.config(text=f"DB Akun: {'Terhubung' if db_exists else 'Belum Ada (Buat di Tab Akun)'}")

    def close(self) -> None:
        """Close/destroy the window."""
        self.destroy()

    def _on_window_close(self) -> None:
        """Ensure child processes are cleanly handled on close."""
        if self.process is not None and self.process.poll() is None:
            ans = messagebox.askyesno(
                "Proses Masih Berjalan",
                "Scraping masih berjalan di latar belakang!\n\n"
                "Apakah Anda ingin menghentikannya secara aman dan keluar?",
            )
            if not ans:
                return
            if self.stop_file:
                self.stop_file.touch(exist_ok=True)
            try:
                self.process.terminate()
            except OSError:
                pass
        self.destroy()


def run() -> int:
    """Entry point to launch the Tkinter GUI."""
    app = MainWindow()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
