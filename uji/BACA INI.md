# Server Supabase tiruan untuk uji

`mock_supabase.py` meniru Supabase (auth, RPC dari `supabase/*.sql`, storage bucket `paket`)
supaya login online, Kelola Petugas, dan **Perbarui sekarang** bisa diuji tanpa menyentuh proyek
sungguhan. Semua data hilang saat server dimatikan.

```
python uji/mock_supabase.py 8798          # port 8798; argumen ke-2 opsional = umur token (detik)
```

Menyiapkan salinan aplikasi uji (JANGAN di folder repo, dan jangan pakai data peserta sungguhan):

1. Ekstrak ZIP rilis ke folder pendek, mis. `C:\uji\CKG Robot` (jalur panjang membuat pip gagal).
2. `inti/login_online.json` → `{"mode": "online", "supabase_url": "http://127.0.0.1:8798", "kunci_publik": "kunci-uji"}`
3. Bila aplikasi sungguhan sedang jalan di 8765: ubah `PORTA = 8765` di `inti/server.py` salinan uji menjadi 8799.
   Untuk menguji **Perbarui**, ubah juga port di dalam ZIP paket baru (salinan ZIP, bukan rilis aslinya).
4. Jalankan `aplikasi.bat` salinan uji dengan `CKG_MULAI_ULANG=1` supaya tab browser tidak terbuka sendiri.

Bantuan uji di server tiruan:
- `POST /uji/sql` `{"email": "...", "ubah": {"status": "aktif", "peran": "admin"}}` — meniru SQL Editor.
- `GET /uji/keadaan` — isi pengaturan/petugas/berkas saat ini.

Daftar akun lewat halaman masuk (Daftar akun baru), lalu aktifkan dengan `/uji/sql`.
