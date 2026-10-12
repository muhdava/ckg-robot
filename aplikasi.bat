@echo off
REM =====================================================================
REM  CKG Robot - buka aplikasi
REM  Klik ganda ikon CKG Robot di Desktop (atau berkas ini). Halaman akan
REM  terbuka sendiri di browser, dan jendela hitam ini mengecil ke taskbar.
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

title CKG Robot

REM Python bawaan (dipasang Setup.exe) dipakai bila ada; selain itu Python
REM yang terpasang di komputer.
set "PY=python"
if exist "%~dp0python\python.exe" set "PY=%~dp0python\python.exe"

if "%PY%"=="python" (
    where python >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [BERHENTI] Python tidak ditemukan.
        echo Jalankan pasang.bat sekali saja lebih dulu.
        echo.
        pause
        exit /b 1
    )
)

REM Pustaka belum lengkap (pemasangan pertama terputus, atau Setup dijalankan
REM tanpa internet): dipasang sekarang, tidak perlu mencari pasang.bat.
"%PY%" -c "import playwright, openpyxl" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Pustaka aplikasi belum lengkap - memasang sekarang.
    echo Perlu internet, bisa beberapa menit. Jangan tutup jendela ini.
    echo.
    "%PY%" -m pip install --disable-pip-version-check -r requirements.txt
    "%PY%" -c "import playwright, openpyxl" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [BERHENTI] Pustaka gagal dipasang. Periksa internet, lalu buka lagi.
        echo.
        pause
        exit /b 1
    )
)

set "CKG_KECILKAN=1"
"%PY%" "inti/server.py"
echo.
echo Aplikasi berhenti.
pause
endlocal
