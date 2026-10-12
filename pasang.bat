@echo off
REM =====================================================================
REM  Pemasangan sekali saja - untuk komputer baru
REM
REM  Dipanggil juga oleh Setup.exe dengan "/setup": tanpa membuat shortcut
REM  (sudah diurus Setup) dan tanpa menunggu tombol bila berhasil.
REM =====================================================================
setlocal
cd /d "%~dp0"
title Memasang CKG Robot
set "MODE=%~1"

REM Python bawaan (dipasang Setup.exe) dipakai bila ada.
set "PY=python"
if exist "%~dp0python\python.exe" set "PY=%~dp0python\python.exe"

if "%PY%"=="python" (
    where python >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [BERHENTI] Python tidak ditemukan.
        echo Unduh dari https://www.python.org/downloads/ lalu pasang.
        echo PENTING: centang "Add Python to PATH" saat memasang.
        echo Atau pakai Setup CKG Robot dari website - Python sudah termasuk.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo [1/3] Memasang pustaka Python (perlu internet)...
"%PY%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto gagal

echo.
echo [2/3] Menyiapkan browser untuk Playwright...
REM Program memakai Chrome yang sudah terpasang. Chromium bawaan dipasang
REM sebagai cadangan supaya tetap jalan di komputer tanpa Chrome.
"%PY%" -m playwright install chromium
if errorlevel 1 (
    echo   [PERINGATAN] Chromium cadangan gagal diunduh. Tidak apa-apa bila
    echo   komputer ini punya Google Chrome.
)

echo.
if /i "%MODE%"=="/setup" (
    echo [3/3] Shortcut dibuat oleh Setup.
) else (
    echo [3/3] Membuat shortcut CKG Robot di Desktop dan Start Menu...
    "%PY%" "inti/pintasan.py"
)

echo.
echo ==============================================================
echo   SELESAI. Mulai sekarang cukup klik ganda ikon CKG Robot
echo   di Desktop.
echo ==============================================================
echo.
if /i not "%MODE%"=="/setup" pause
exit /b 0

:gagal
echo.
echo [GAGAL] Pustaka belum terpasang. Periksa internet.
if /i "%MODE%"=="/setup" (
    echo Tidak apa-apa: pemasangan akan dicoba lagi otomatis saat
    echo CKG Robot pertama kali dibuka.
) else (
    echo Periksa pesan di atas, lalu jalankan pasang.bat lagi.
)
echo.
pause
exit /b 1
