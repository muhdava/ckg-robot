@echo off
REM =====================================================================
REM  CKG Robot - versi terminal (tanpa halaman aplikasi)
REM  Pengaturan ada di pengaturan.txt
REM =====================================================================
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo [BERHENTI] Python tidak ditemukan.
    echo Jalankan pasang.bat sekali saja lebih dulu.
    echo.
    pause
    exit /b 1
)

python -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [BERHENTI] Playwright belum terpasang.
    echo Jalankan pasang.bat sekali saja, lalu coba lagi.
    echo.
    pause
    exit /b 1
)

echo.
echo ==============================================================
echo   CKG Robot - versi terminal
echo   Data: folder data\   Pengaturan: pengaturan.txt
echo ==============================================================
echo.

python "inti/run.py"
set KODE=%ERRORLEVEL%

echo.
if not "%KODE%"=="0" (
    echo [SELESAI dengan kode %KODE%] Periksa pesan di atas.
) else (
    echo [SELESAI] Hasil tersimpan di folder hasil\
)
echo.
pause
endlocal
