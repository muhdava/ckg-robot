@echo off
REM =====================================================================
REM  Pemasangan sekali saja — untuk komputer baru
REM =====================================================================
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo [BERHENTI] Python tidak ditemukan.
    echo Unduh dari https://www.python.org/downloads/ lalu pasang.
    echo PENTING: centang "Add Python to PATH" saat memasang.
    echo.
    pause
    exit /b 1
)

echo.
echo [1/2] Memasang pustaka Python...
python -m pip install -r requirements.txt
if errorlevel 1 goto gagal

echo.
echo [2/2] Menyiapkan browser untuk Playwright...
REM Program memakai Chrome yang sudah terpasang. Chromium bawaan dipasang
REM sebagai cadangan supaya tetap jalan di komputer tanpa Chrome.
python -m playwright install chromium
if errorlevel 1 goto gagal

echo.
echo ==============================================================
echo   SELESAI. Mulai sekarang cukup klik ganda jalankan.bat
echo ==============================================================
echo.
pause
exit /b 0

:gagal
echo.
echo [GAGAL] Pemasangan tidak selesai. Periksa pesan di atas.
echo.
pause
exit /b 1
