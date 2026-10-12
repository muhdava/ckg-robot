@echo off
REM =====================================================================
REM  CKG Robot - versi terminal (tanpa halaman aplikasi)
REM  Pengaturan ada di pengaturan.txt
REM =====================================================================
setlocal
cd /d "%~dp0"

REM Python bawaan (dipasang Setup.exe) dipakai bila ada.
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

"%PY%" -c "import playwright" >nul 2>&1
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

"%PY%" "inti/run.py"
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
