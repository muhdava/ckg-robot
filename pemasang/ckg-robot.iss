; =====================================================================
;  CKG Robot - naskah Setup.exe (Inno Setup 6)
;
;  JANGAN dikompilasi langsung: buat_paket.bat yang memanggilnya, dengan
;    /DVERSI=2026.10.12.1458   nomor versi yang baru dicap
;    /DSUMBER=<folder>         salinan bersih aplikasi (tanpa data peserta)
;    /DPYTHON=<folder>         Python bawaan dari siapkan_python.py
;    /DKELUARAN=<folder>       tempat Setup.exe ditulis
;    /DNAMA=<nama berkas>      tanpa .exe
;
;  Dipasang per pengguna di %LOCALAPPDATA%\CKG Robot - tanpa izin
;  administrator, dan tombol "Perbarui" di aplikasi bisa menulis ke sana.
; =====================================================================

#ifndef VERSI
  #error Jalankan lewat buat_paket.bat
#endif

[Setup]
AppId={{8E3C2B71-5A4D-4F0B-9C2E-7D1A6B3F4E21}
AppName=CKG Robot
AppVersion={#VERSI}
AppVerName=CKG Robot {#VERSI}
AppPublisher=CKG Robot
VersionInfoVersion={#VERSI}
VersionInfoDescription=Pemasang CKG Robot
DefaultDirName={localappdata}\CKG Robot
DefaultGroupName=CKG Robot
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir={#KELUARAN}
OutputBaseFilename={#NAMA}
SetupIconFile={#SUMBER}\inti\ikon.ico
UninstallDisplayIcon={app}\inti\ikon.ico
UninstallDisplayName=CKG Robot
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
RestartApplications=no

[Messages]
SetupAppTitle=Pemasangan
SetupWindowTitle=Pemasangan - %1
WelcomeLabel1=Selamat datang di pemasangan [name]
WelcomeLabel2=[name/ver] akan dipasang di komputer ini.%n%nPython sudah termasuk - tidak perlu memasang apa pun lagi. Pemasangan memerlukan INTERNET untuk mengunduh pustaka dan browser (beberapa menit).%n%nTutup CKG Robot bila sedang terbuka, lalu klik Lanjut.
ButtonBack=< &Kembali
ButtonNext=&Lanjut >
ButtonInstall=&Pasang
ButtonCancel=Batal
ButtonFinish=&Selesai
ButtonBrowse=&Pilih...
ButtonYes=&Ya
ButtonNo=&Tidak
SelectDirLabel3=CKG Robot akan dipasang di folder berikut.
SelectDirBrowseLabel=Klik Lanjut untuk meneruskan. Untuk memilih folder lain, klik Pilih.
WizardSelectDir=Pilih Folder Tujuan
SelectDirDesc=Di mana CKG Robot akan dipasang?
WizardSelectTasks=Pilih Tambahan
SelectTasksDesc=Apa saja yang ikut disiapkan?
SelectTasksLabel2=Pilih tambahan yang diinginkan, lalu klik Lanjut.
WizardReady=Siap Memasang
ReadyLabel1=CKG Robot siap dipasang di komputer ini.
ReadyLabel2a=Klik Pasang untuk memulai.
ReadyMemoDir=Folder tujuan:
ReadyMemoTasks=Tambahan:
WizardInstalling=Memasang
InstallingLabel=Mohon tunggu, CKG Robot sedang dipasang.
StatusExtractFiles=Menyalin berkas...
StatusRunProgram=Menyelesaikan pemasangan...
FinishedHeadingLabel=Pemasangan selesai
FinishedLabelNoIcons=CKG Robot sudah terpasang.
FinishedLabel=CKG Robot sudah terpasang. Buka lewat ikon CKG Robot di Desktop atau Start Menu.
ExitSetupTitle=Batalkan pemasangan
ExitSetupMessage=Pemasangan belum selesai. Bila dibatalkan sekarang, CKG Robot tidak terpasang.%n%nBatalkan pemasangan?
ConfirmUninstall=Hapus CKG Robot dari komputer ini?%n%nFolder data\, hasil\, dan pengaturan.txt TIDAK ikut dihapus.
UninstalledAll=CKG Robot sudah dihapus dari komputer ini.
UninstalledMost=CKG Robot sudah dihapus.%n%nBeberapa berkas (data, hasil, pengaturan) sengaja ditinggal dan bisa dihapus sendiri.

[CustomMessages]
BuatIkonDesktop=Buat ikon CKG Robot di &Desktop
BukaSekarang=Buka CKG Robot sekarang
MemasangPustaka=Mengunduh pustaka dan browser (perlu internet, beberapa menit)...

[Tasks]
Name: "desktopicon"; Description: "{cm:BuatIkonDesktop}"

[Files]
; Milik petugas: ditulis hanya bila belum ada (memasang ulang tidak menimpa pengaturannya).
Source: "{#SUMBER}\*"; DestDir: "{app}"; Excludes: "\pengaturan.txt,\inti\login_online.json"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SUMBER}\pengaturan.txt"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SUMBER}\inti\login_online.json"; DestDir: "{app}\inti"; Flags: onlyifdoesntexist
Source: "{#PYTHON}\*"; DestDir: "{app}\python"; Excludes: "versi-bawaan.txt,__pycache__"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\CKG Robot"; Filename: "{app}\aplikasi.bat"; WorkingDir: "{app}"; IconFilename: "{app}\inti\ikon.ico"; Comment: "CKG Robot - input otomatis Cek Kesehatan Gratis"
; Folder aplikasi ada di AppData (tersembunyi) - jalan pintas ke data\, hasil\, template\.
Name: "{autoprograms}\CKG Robot - folder data"; Filename: "{app}"; Comment: "Folder data, hasil, dan template CKG Robot"
Name: "{autodesktop}\CKG Robot"; Filename: "{app}\aplikasi.bat"; WorkingDir: "{app}"; IconFilename: "{app}\inti\ikon.ico"; Comment: "CKG Robot - input otomatis Cek Kesehatan Gratis"; Tasks: desktopicon

[Run]
Filename: "{cmd}"; Parameters: "/c """"{app}\pasang.bat"" /setup"""; WorkingDir: "{app}"; StatusMsg: "{cm:MemasangPustaka}"; Flags: waituntilterminated
Filename: "{app}\aplikasi.bat"; WorkingDir: "{app}"; Description: "{cm:BukaSekarang}"; Flags: postinstall nowait skipifsilent shellexec

[UninstallDelete]
; Dibuat sesudah pemasangan (pip, pembaruan, cache Python) - ikut dihapus.
; data\, hasil\, mentah\, pengaturan.txt, dan sesi browser sengaja ditinggal.
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\inti\__pycache__"
Type: filesandordirs; Name: "{app}\cadangan-versi"
Type: filesandordirs; Name: "{app}\pembaruan"
Type: files; Name: "{app}\*.baru"
