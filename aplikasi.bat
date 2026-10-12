@echo off
REM =====================================================================
REM  CKG Robot - buka aplikasi
REM  Klik ganda berkas ini. Halaman akan terbuka sendiri di browser.
REM  JANGAN tutup jendela hitam ini selama aplikasi dipakai.
REM =====================================================================
setlocal
cd /d "%~dp0"

REM Pembaruan dari dalam aplikasi menulis versi baru berkas INI sebagai
REM aplikasi.bat.baru (berkas yang sedang dijalankan cmd tidak boleh ditimpa).
REM Ditukar di sini, lalu versi barunya dijalankan. Seluruh blok dibaca cmd
REM sekaligus sebelum dijalankan, jadi menukar berkasnya di tengah aman.
if exist "%~dp0aplikasi.bat.baru" (
    move /y "%~dp0aplikasi.bat.baru" "%~f0" >nul
    call "%~f0" %*
    exit /b
)

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

python "inti/server.py"
echo.
echo Aplikasi berhenti.
pause
endlocal
