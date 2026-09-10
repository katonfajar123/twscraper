@echo off
title MBG Scraper Studio
echo.
echo  ============================================
echo   MBG Scraper Studio - Memulai Aplikasi...
echo  ============================================
echo.

REM Cek apakah Python tersedia
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan!
    echo Pastikan Python 3.10+ sudah terinstall dan ada di PATH.
    echo Download: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Pindah ke folder project
cd /d "%~dp0"

REM Cek apakah requirements sudah terinstall (cek twscrape)
python -c "import twscrape" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Menginstall dependensi yang dibutuhkan...
    echo Ini hanya terjadi sekali di awal. Harap tunggu...
    echo.
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Gagal menginstall dependensi!
        echo Coba jalankan manual: python -m pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo.
    echo [OK] Dependensi berhasil diinstall!
    echo.
)

REM Jalankan GUI
echo [OK] Memulai MBG Scraper Studio...
python main.py

REM Jika ada error
if errorlevel 1 (
    echo.
    echo [ERROR] Aplikasi berhenti dengan error.
    echo Coba jalankan: python main.py
    echo di folder ini untuk melihat pesan error lengkap.
    pause
)

