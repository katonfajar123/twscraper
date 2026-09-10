"""Small service boundary used by Qt workers."""

from __future__ import annotations

import asyncio
from pathlib import Path

from twscrape import API


async def _account_operation(
    db_path: str,
    operation: str,
    payload: dict | None = None,
) -> object:
    api = API(db_path)
    payload = payload or {}
    if operation == "list":
        return await api.pool.accounts_info()
    if operation == "add_cookies":
        username = str(payload.get("username", "")).strip()
        auth_token = str(payload.get("auth_token", "")).strip()
        ct0 = str(payload.get("ct0", "")).strip()
        if not username or not auth_token or not ct0:
            raise ValueError("Username, auth_token, dan ct0 wajib diisi")
        await api.pool.add_account_cookies(
            username,
            f"auth_token={auth_token}; ct0={ct0}",
        )
        return {"message": f"Cookie @{username} tersimpan", "username": username}
    if operation == "set_active":
        username = str(payload.get("username", "")).strip()
        active = bool(payload.get("active"))
        if not username:
            raise ValueError("Pilih akun terlebih dahulu")
        await api.pool.set_active(username, active)
        return {"message": f"@{username} {'diaktifkan' if active else 'dinonaktifkan'}"}
    if operation == "reset_locks":
        await api.pool.reset_locks()
        return {"message": "Lock rate-limit lokal sudah direset"}
    raise ValueError(f"Operasi akun tidak dikenal: {operation}")


def run_account_operation(
    db_path: str | Path,
    operation: str,
    payload: dict | None = None,
) -> object:
    """Run local account-pool work inside a dedicated QThread."""
    return asyncio.run(_account_operation(str(db_path), operation, payload))
