@echo off
REM =====================================================================
REM  CKG Robot - buat paket untuk dibagikan ke petugas lain
REM
REM  Menghasilkan satu berkas ZIP di folder INDUK (di luar folder ini),
REM  supaya paket lama tidak ikut terbawa ke paket berikutnya.
REM
REM  Yang SENGAJA tidak disertakan:
REM    .profil-browser*\ sesi login-mu, termasuk profil tiap pekerja paralel
REM                     (.profil-browser-1, -2, ...). Penyaring lama hanya cocok
REM                     pada nama PERSIS, sehingga profil pekerja ikut terbawa -
REM                     ratusan MB, dan sesi login yang seharusnya tidak dibagikan.
REM    hasil\            riwayat pekerjaanmu; kalau ikut, peserta mereka
REM                     akan dilewati karena dikira sudah selesai
REM    buat_paket.bat    alat pembuat paket ini sendiri - milik yang membagikan,
REM                     bukan milik petugas yang menerima
REM    akun.dat          akun untuk masuk aplikasi; tiap petugas membuat
REM                     akunnya sendiri lewat buat_akun.bat
REM  Dua yang pertama dibuat sendiri saat aplikasi pertama dijalankan.
REM =====================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmm"') do set "TGL=%%i"
set "NAMA=CKG-Robot-%TGL%"
set "STAGE=%TEMP%\%NAMA%"
set "ZIP=%~dp0..\%NAMA%.zip"

echo.
echo  ============================================================
echo    Membuat paket: %NAMA%.zip
echo  ============================================================
echo.
echo  Folder data\ berisi CSV peserta - nama dan NIK orang sungguhan.
set /p JAWAB="  Sertakan data peserta itu? (y/t) [t]: "
if /i "%JAWAB%"=="y" (set "IKUT=1") else (set "IKUT=0")

if exist "%STAGE%" rd /s /q "%STAGE%"
echo.
REM Nomor versi baru (tahun.bulan.tanggal.jammenit) dicap ke inti\config.py
REM SEBELUM disalin: dasar tombol "Perbarui sekarang" di aplikasi petugas.
for /f %%v in ('python "%~dp0alat\cap_versi.py"') do set "VERSI=%%v"
if not defined VERSI goto gagal
echo  Versi paket: %VERSI%
echo  [1/4] Menyalin berkas...
REM mentah\ = salinan berkas Excel yang pernah di-convert (nama & NIK orang
REM sungguhan); alat\ = skrip perapian/laporan milik pembuat paket, ada yang
REM memuat NIK di dalamnya. Keduanya bukan untuk petugas penerima.
robocopy "%~dp0." "%STAGE%" /E /NFL /NDL /NJH /NJS /NP /XD ".profil-browser*" "hasil" "mentah" "alat" "supabase" "cadangan-tampilan*" "cadangan-versi" "pembaruan" "__pycache__" ".git" "pemasang" "python" /XF "*.pyc" "*.baru" "*.sementara" "buat_paket.bat" "akun.dat" ".pintasan" "unins000.*" >nul
if errorlevel 8 goto gagal
if not exist "%STAGE%\mentah" mkdir "%STAGE%\mentah"
if exist "%~dp0mentah\BACA INI.txt" copy /y "%~dp0mentah\BACA INI.txt" "%STAGE%\mentah\" >nul

if "%IKUT%"=="0" (
    del /q "%STAGE%\data\*.csv" >nul 2>&1
    copy /y "%~dp0data\data-uji.csv" "%STAGE%\data\" >nul 2>&1
    REM Pengaturan 'berkas csv' menunjuk berkas yang barusan tidak ikut, jadi
    REM diarahkan ke contoh - kalau tidak, penerima disambut peringatan
    REM "berkas tidak ada" pada setiap kali menjalankan.
    powershell -NoProfile -Command "$f='%STAGE%\pengaturan.txt'; (Get-Content $f) -replace '^^\s*berkas csv\s*=.*', 'berkas csv = data-uji.csv' | Set-Content $f -Encoding UTF8"
    echo        data peserta TIDAK disertakan ^(hanya contoh data-uji.csv^)
) else (
    echo        data peserta ikut disertakan
)

echo  [2/4] Memampatkan...
if exist "%ZIP%" del /q "%ZIP%"
powershell -NoProfile -Command "Compress-Archive -Path '%STAGE%\*' -DestinationPath '%ZIP%' -CompressionLevel Optimal"
if errorlevel 1 goto gagal

REM Setup.exe dari salinan yang SAMA - hanya bila data peserta tidak ikut
REM (Setup diunggah ke website untuk semua petugas). Butuh Inno Setup 6.
set "SETUP="
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if "%IKUT%"=="1" (
    echo  [3/4] Setup.exe TIDAK dibuat: data peserta ikut disertakan.
    goto bersihkan
)
if not defined ISCC (
    echo  [3/4] Setup.exe dilewati: Inno Setup 6 belum terpasang.
    goto bersihkan
)
echo  [3/4] Membuat Setup.exe...
set "PYBAWAAN="
for /f "delims=" %%p in ('python "%~dp0pemasang\siapkan_python.py"') do set "PYBAWAAN=%%p"
if not defined PYBAWAAN goto gagal
"%ISCC%" /Q "/DVERSI=%VERSI%" "/DSUMBER=%STAGE%" "/DPYTHON=%PYBAWAAN%" "/DKELUARAN=%~dp0.." "/DNAMA=CKG-Robot-Setup-%TGL%" "%~dp0pemasang\ckg-robot.iss"
if errorlevel 1 goto gagal
set "SETUP=%~dp0..\CKG-Robot-Setup-%TGL%.exe"

:bersihkan
echo  [4/4] Membersihkan...
rd /s /q "%STAGE%"

echo.
for %%A in ("%ZIP%") do set /a MB=%%~zA/1048576
echo  ============================================================
echo    SELESAI - %NAMA%.zip ^(sekitar !MB! MB^)
if defined SETUP (
    for %%A in ("!SETUP!") do set /a MBS=%%~zA/1048576
    echo    dan     CKG-Robot-Setup-%TGL%.exe ^(sekitar !MBS! MB^)
)
echo    Ada di folder induk, sejajar dengan folder aplikasi ini.
echo.
echo    ZIP  : terbitkan lewat Kelola Petugas ^(tombol Perbarui^).
echo    Setup: unggah di Panel Admin website, untuk petugas baru.
echo  ============================================================
echo.
pause
exit /b 0

:gagal
echo.
echo  [GAGAL] Paket tidak selesai dibuat. Periksa pesan di atas.
echo.
if exist "%STAGE%" rd /s /q "%STAGE%"
pause
exit /b 1
