@echo off
REM =====================================================================
REM  CKG Robot - kelola akun untuk masuk ke aplikasi
REM
REM  Kata sandi TIDAK disimpan. Yang tersimpan di akun.dat hanya hasil
REM  pengacakan searah, yang tidak bisa dikembalikan menjadi kata sandi.
REM  Karena itu kalau lupa, sandinya tidak bisa dilihat - hanya diganti.
REM =====================================================================
setlocal
cd /d "%~dp0"

:menu
echo.
echo  ============================================================
echo    AKUN CKG ROBOT
echo  ============================================================
python "inti/akun.py" daftar
echo.
echo    [1] Tambah akun baru
echo    [2] Ganti kata sandi
echo    [3] Hapus akun
echo    [4] Keluar
echo.
set "PILIH="
set /p PILIH="  Pilih (1-4): "

if "%PILIH%"=="1" goto tambah
if "%PILIH%"=="2" goto sandi
if "%PILIH%"=="3" goto hapus
if "%PILIH%"=="4" goto habis
goto menu

:tambah
set "NAMA="
set /p NAMA="  Nama pengguna baru: "
if not "%NAMA%"=="" python "inti/akun.py" tambah "%NAMA%"
goto menu

:sandi
set "NAMA="
set /p NAMA="  Nama pengguna: "
if not "%NAMA%"=="" python "inti/akun.py" sandi "%NAMA%"
goto menu

:hapus
set "NAMA="
set /p NAMA="  Nama pengguna yang dihapus: "
if not "%NAMA%"=="" python "inti/akun.py" hapus "%NAMA%"
goto menu

:habis
endlocal
