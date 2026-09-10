"""
setup_accounts.py
-----------------
Script untuk menambahkan akun X/Twitter dari file accounts.txt
dan menjalankan login flow.

Cara pakai:
  1. Buat file accounts.txt berdasarkan accounts.txt.example
  2. Jalankan: python setup_accounts.py
"""

import asyncio
import os
import sys
from pathlib import Path

from twscrape import API


DB_PATH = os.getenv("TWS_DB", "accounts.db")
ACCOUNTS_FILE = "accounts.txt"


async def add_accounts(api: API, accounts_file: str) -> int:
    """Baca file akun dan tambahkan ke pool."""
    path = Path(accounts_file)
    if not path.exists():
        print(f"[ERROR] File '{accounts_file}' tidak ditemukan.")
        print(f"        Buat file tersebut berdasarkan '{accounts_file}.example'")
        return 0

    added = 0
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split(":")
            if len(parts) < 3:
                print(f"[WARN] Baris {lineno} tidak valid: {line!r}")
                continue

            username       = parts[0].strip()
            password       = parts[1].strip()
            email          = parts[2].strip()
            email_password = parts[3].strip() if len(parts) > 3 else ""

            try:
                await api.pool.add_account(
                    username=username,
                    password=password,
                    email=email,
                    email_password=email_password,
                )
                print(f"[OK]   Akun ditambahkan: {username}")
                added += 1
            except Exception as exc:
                print(f"[WARN] Gagal tambah akun '{username}': {exc}")

    return added


async def main() -> None:
    api = API(DB_PATH)

    print("=== twscraper Setup ===")
    print(f"Database  : {DB_PATH}")
    print(f"File akun : {ACCOUNTS_FILE}")
    print()

    # 1. Tambahkan akun dari file
    added = await add_accounts(api, ACCOUNTS_FILE)
    if added == 0:
        print("[INFO] Tidak ada akun baru. Cek file accounts.txt Anda.")

    # 2. Tampilkan status sebelum login
    accounts = await api.pool.get_all()
    print(f"\n=== Status Akun ({len(accounts)} total) ===")
    for acc in accounts:
        status = "aktif" if acc.active else "nonaktif"
        logged = "[SESSION ADA]" if acc.has_session else "[belum login]"
        print(f"  {acc.username:20s} | {logged} | {status}")

    # 3. Jalankan login untuk akun yang belum punya session
    needs_login = [acc for acc in accounts if not acc.has_session]
    if needs_login:
        print(f"\n[INFO] Login {len(needs_login)} akun...")
        for acc in needs_login:
            print(f"  Logging in: {acc.username} ...")
            ok = await api.pool.login(acc)
            if ok:
                print(f"  [OK] {acc.username} berhasil login")
            else:
                print(f"  [FAIL] {acc.username} gagal login - cek error di atas")
    else:
        print("\n[INFO] Semua akun sudah punya session. Tidak perlu login ulang.")

    # 4. Status akhir
    accounts = await api.pool.get_all()
    print("\n=== Status Akhir ===")
    for acc in accounts:
        err = f" | ERR: {acc.error_msg}" if acc.error_msg else ""
        print(f"  {acc.username:20s} | session={acc.has_session} | aktif={acc.active}{err}")

    logged_in_count = sum(1 for a in accounts if a.has_session)
    print(f"\n[SELESAI] {logged_in_count}/{len(accounts)} akun berhasil login.")

    if logged_in_count == 0:
        print("\n[WARN] Tidak ada akun yang berhasil login.")
        print("       Coba cara alternatif via CLI:")
        print("         twscrape login_accounts")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
