"""
Login ONLINE lewat Supabase - pengganti akun.dat bila diaktifkan.

Aktif bila ada berkas `inti/login_online.json`:

    {"mode": "online",
     "supabase_url": "https://xxxx.supabase.co",
     "kunci_publik": "sb_publishable_... atau anon key (eyJ...)"}

Kunci publik memang boleh ikut di paket: kunci itu sendiri tidak membuka
apa pun. Semua tabel di Supabase terkunci, dan satu-satunya pintu adalah
fungsi yang memeriksa siapa pemanggilnya (lihat supabase/skema.sql).
KUNCI service_role TIDAK BOLEH ditaruh di sini.

Yang dikirim ke Supabase hanya: email, kata sandi (lewat HTTPS, diurus
Supabase Auth), data petugas saat mendaftar, sidik komputer (hash), nama
komputer, dan versi aplikasi. TIDAK ADA data peserta CKG.

Memakai pustaka bawaan Python saja - tidak ada pustaka baru untuk dipasang.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import ssl
import time
import urllib.error
import urllib.request

import config

BERKAS = config.AKAR / "inti" / "login_online.json"
BATAS_WAKTU = 20          # detik per permintaan ke Supabase


class GagalOnline(Exception):
    """Galat yang pesannya layak ditampilkan apa adanya ke petugas."""

    def __init__(self, pesan: str, alasan: str = ""):
        super().__init__(pesan)
        self.pesan = pesan
        self.alasan = alasan


# ------------------------------------------------------------- pengaturan
def _baca() -> dict:
    try:
        return json.loads(BERKAS.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def aktif() -> bool:
    d = _baca()
    return (str(d.get("mode", "")).strip().lower() == "online"
            and bool(d.get("supabase_url")) and bool(d.get("kunci_publik")))


def _url() -> str:
    return str(_baca().get("supabase_url", "")).strip().rstrip("/")


def _kunci() -> str:
    return str(_baca().get("kunci_publik", "")).strip()


# ---------------------------------------------------------------- perangkat
def kode_perangkat() -> str:
    """
    Sidik komputer yang tetap sama selama Windows-nya sama.

    Diambil dari MachineGuid Windows lalu di-hash - yang terkirim hanya
    hash-nya, bukan nomor aslinya. Bila tidak terbaca (bukan Windows),
    dipakai alamat MAC.
    """
    dasar = ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            dasar = str(winreg.QueryValueEx(k, "MachineGuid")[0])
    except Exception:
        import uuid
        dasar = f"mac-{uuid.getnode():x}"
    return hashlib.sha256(f"ckg-robot|{dasar}".encode("utf-8")).hexdigest()[:40]


def nama_komputer() -> str:
    return (os.environ.get("COMPUTERNAME") or platform.node() or "")[:100]


# ------------------------------------------------------------------- HTTP
def _minta(metode: str, jalan: str, isi: dict | None = None, akses: str = "") -> dict:
    kepala = {"apikey": _kunci(), "Content-Type": "application/json", "Accept": "application/json"}
    if akses:
        kepala["Authorization"] = f"Bearer {akses}"
    data = json.dumps(isi).encode("utf-8") if isi is not None else None
    req = urllib.request.Request(_url() + jalan, data=data, headers=kepala, method=metode)
    try:
        with urllib.request.urlopen(req, timeout=BATAS_WAKTU,
                                    context=ssl.create_default_context()) as r:
            mentah = r.read()
            return json.loads(mentah) if mentah.strip() else {}
    except urllib.error.HTTPError as e:
        try:
            badan = json.loads(e.read() or b"{}")
        except Exception:
            badan = {}
        raise GagalOnline(_terjemahkan(e.code, badan), str(badan.get("error_code")
                                                          or badan.get("code") or e.code)) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise GagalOnline("Tidak bisa menghubungi server login. Periksa koneksi internet, "
                          f"lalu coba lagi. ({type(e).__name__})", "jaringan") from None


def _terjemahkan(kode: int, badan: dict) -> str:
    """Pesan Supabase (Inggris, teknis) -> kalimat untuk petugas."""
    jenis = str(badan.get("error_code") or badan.get("error") or "").lower()
    asli = str(badan.get("msg") or badan.get("error_description") or badan.get("message") or "")
    if jenis in ("invalid_credentials", "invalid_grant") or "invalid login" in asli.lower():
        return "Email atau kata sandi salah."
    if jenis == "email_not_confirmed":
        return ("Email belum dikonfirmasi. Admin perlu mematikan 'Confirm email' di "
                "Supabase (Authentication > Sign In / Providers > Email).")
    if jenis in ("user_already_exists", "email_exists") or "already registered" in asli.lower():
        return "Email ini sudah terdaftar. Silakan masuk, atau minta admin mengganti sandinya."
    if jenis == "weak_password":
        return "Kata sandi terlalu lemah. Pakai minimal 8 karakter, campur huruf dan angka."
    if jenis == "email_address_invalid" or "invalid" in jenis and "email" in jenis:
        return "Alamat email tidak sah."
    if jenis == "signup_disabled":
        return "Pendaftaran akun baru sedang ditutup admin."
    if kode == 429 or "rate" in jenis:
        return "Terlalu banyak percobaan ke server login. Tunggu beberapa menit."
    if kode == 404 and "periksa_izin" in asli:
        return "Server login belum disiapkan (skema.sql belum dijalankan). Hubungi admin."
    if kode >= 500:
        return ("Server login tidak menjawab dengan benar - mungkin sedang di-pause. "
                "Hubungi admin.")
    return f"Server login menolak permintaan ({kode}{': ' + asli if asli else ''})."


# --------------------------------------------------------------- auth
def _token(d: dict) -> dict:
    if not d.get("access_token"):
        raise GagalOnline("Server login tidak memberi sesi. Hubungi admin.", "tanpa_sesi")
    return {"akses": d["access_token"],
            "segar": d.get("refresh_token", ""),
            "sampai": float(d.get("expires_at") or time.time() + float(d.get("expires_in") or 3600)),
            "id": (d.get("user") or {}).get("id", "")}


def masuk(email: str, sandi: str) -> dict:
    return _token(_minta("POST", "/auth/v1/token?grant_type=password",
                         {"email": email.strip(), "password": sandi}))


def segarkan(token: dict) -> dict:
    """Akses token Supabase berumur ~1 jam; diperbarui dengan refresh token."""
    baru = _token(_minta("POST", "/auth/v1/token?grant_type=refresh_token",
                         {"refresh_token": token["segar"]}))
    token.update(baru)
    return token


def akses_segar(token: dict) -> str:
    if token["sampai"] - 90 < time.time():
        segarkan(token)
    return token["akses"]


def daftar(email: str, sandi: str, nama: str, puskesmas: str, no_hp: str) -> dict:
    """
    Daftarkan akun baru. Statusnya 'menunggu' sampai disetujui admin.
    Dipakai juga oleh admin untuk membuatkan akun (lalu langsung disetujui).
    """
    d = _minta("POST", "/auth/v1/signup", {
        "email": email.strip(), "password": sandi,
        "data": {"nama": nama.strip()[:100], "puskesmas": puskesmas.strip()[:100],
                 "no_hp": no_hp.strip()[:30]}})
    pengguna = d.get("user") or d          # tanpa sesi bila 'Confirm email' menyala
    return {"id": pengguna.get("id", ""), "perlu_konfirmasi": not d.get("access_token")}


def keluar(token: dict) -> None:
    try:
        _minta("POST", "/auth/v1/logout", {}, token.get("akses", ""))
    except GagalOnline:
        pass                               # sesi lokal tetap dihapus


def rpc(nama_fungsi: str, argumen: dict, token: dict) -> dict:
    hasil = _minta("POST", f"/rest/v1/rpc/{nama_fungsi}", argumen, akses_segar(token))
    return hasil if isinstance(hasil, dict) else {"ok": False, "pesan": "Jawaban server tidak dikenal."}


BUCKET = "paket"


def tautan_unduh(token: dict, nama: str, detik: int = 300) -> str:
    """Tautan sementara ke berkas di bucket privat - hanya untuk petugas AKTIF."""
    d = _minta("POST", f"/storage/v1/object/sign/{BUCKET}/{nama}", {"expiresIn": detik}, akses_segar(token))
    jalan = d.get("signedURL") or d.get("signedUrl") or ""
    if not jalan:
        raise GagalOnline("Server tidak memberi tautan unduhan.", "tanpa_tautan")
    return jalan if jalan.startswith("http") else _url() + "/storage/v1" + jalan


def unggah(token: dict, nama: str, isi: bytes, jenis: str) -> None:
    """Unggah/timpa berkas di bucket 'paket' (aturan Storage: hanya admin)."""
    kepala = {"apikey": _kunci(), "Authorization": f"Bearer {akses_segar(token)}",
              "Content-Type": jenis, "x-upsert": "true", "cache-control": "max-age=60"}
    req = urllib.request.Request(f"{_url()}/storage/v1/object/{BUCKET}/{nama}", data=isi, headers=kepala,
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180, context=ssl.create_default_context()) as r:
            r.read()
    except urllib.error.HTTPError as e:
        try:
            badan = json.loads(e.read() or b"{}")
        except Exception:
            badan = {}
        pesan = str(badan.get("message") or badan.get("error") or e.code)
        if "row-level security" in pesan or "Unauthorized" in pesan:
            pesan = "ditolak aturan penyimpanan - pastikan akun ini admin dan tambahan-website-2 sudah dijalankan"
        raise GagalOnline(f"Gagal mengunggah paket: {pesan}", "unggah") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise GagalOnline(f"Gagal mengunggah paket ({type(e).__name__}). Periksa internet.", "jaringan") from None


def periksa_izin(token: dict) -> dict:
    return rpc("periksa_izin", {"p_kode": kode_perangkat(), "p_nama_komputer": nama_komputer(),
                                "p_versi": config.VERSI}, token)


# --------------------------------------------------------- terminal (run.py)
def masuk_terminal() -> bool:
    """Untuk jalankan.bat: minta email + sandi di jendela hitam, lalu periksa izin."""
    import akun                            # _baca_sandi (menampilkan bintang)
    print("\nMode login ONLINE - masuk dengan akun CKG Robot.")
    for _ in range(3):
        email = input("  Email      : ").strip()
        sandi = akun._baca_sandi("  Kata sandi : ")
        try:
            token = masuk(email, sandi)
            izin = periksa_izin(token)
        except GagalOnline as e:
            print(f"  [DITOLAK] {e.pesan}")
            continue
        if izin.get("ok"):
            print(f"  Masuk sebagai {izin.get('nama') or email}.\n")
            return True
        print(f"  [DITOLAK] {izin.get('pesan')}")
        return False
    return False
