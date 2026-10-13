"""
Supabase TIRUAN untuk menguji login online tanpa proyek sungguhan.

Meniru: /auth/v1/signup, /auth/v1/token (password & refresh_token),
/auth/v1/logout, /rest/v1/rpc/<fungsi> - dengan logika yang disalin dari
supabase/skema.sql. Plus /uji/sql untuk meniru "SQL Editor" (jadikan admin).
"""
import json
import secrets
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

KUNCI = "kunci-uji"
UMUR = int(sys.argv[2]) if len(sys.argv) > 2 else 3600
USERS, PETUGAS, PERANGKAT, AKSES, SEGAR = {}, {}, [], {}, {}
ATUR = {"versi_minimal": "", "maks_perangkat": 2, "pengumuman": "", "versi_terbaru": "", "sha256_terbaru": "",
        "ukuran_terbaru": 0, "catatan_terbaru": "", "diterbitkan": None}


def info():
    return {k: ATUR[k] for k in ("versi_terbaru", "sha256_terbaru", "ukuran_terbaru", "catatan_terbaru", "diterbitkan")}
LOG = []
CRLF = bytes([13, 10])
BERKAS = {}   # nama -> (bytes, jenis, waktu)
PAKAI = {}


def sesi(uid):
    a, s = secrets.token_hex(16), secrets.token_hex(16)
    AKSES[a] = (uid, time.time() + UMUR)
    SEGAR[s] = uid
    return {"access_token": a, "refresh_token": s, "expires_in": UMUR,
            "expires_at": int(time.time() + UMUR), "token_type": "bearer",
            "user": {"id": uid, "email": USERS[uid]["email"], "aud": "authenticated", "role": "authenticated",
                     "app_metadata": {}, "user_metadata": {}, "created_at": "2026-10-07T00:00:00Z"}}


def gagal(alasan, pesan):
    return {"ok": False, "alasan": alasan, "pesan": pesan}


def admin(uid):
    p = PETUGAS.get(uid)
    return bool(p and p["peran"] == "admin" and p["status"] == "aktif")


def periksa_izin(uid, a):
    if not uid:
        return gagal("belum_masuk", "Sesi tidak sah. Silakan masuk lagi.")
    p = PETUGAS.get(uid)
    if not p:
        return gagal("akun_tidak_ada", "Akun tidak terdaftar sebagai petugas. Hubungi admin.")
    if p["status"] == "menunggu":
        return gagal("menunggu", "Akun belum disetujui admin. Coba lagi setelah admin menyetujuinya.")
    if p["status"] == "nonaktif":
        return gagal("nonaktif", "Akun ini dinonaktifkan admin.")
    if ATUR["versi_minimal"] and (a.get("p_versi") or "") < ATUR["versi_minimal"]:
        return {**gagal("versi_lama", f"CKG Robot versi {a.get('p_versi') or '?'} sudah tidak dipakai. "
                                      f"Perbarui ke versi {ATUR['versi_minimal']} atau yang lebih baru."),
                "nama": p["nama"], "peran": p["peran"], **info()}
    kode = (a.get("p_kode") or "")[:128]
    if not kode:
        return gagal("perangkat_kosong", "Komputer ini tidak bisa dikenali.")
    milik = [d for d in PERANGKAT if d["petugas_id"] == uid]
    ada = next((d for d in milik if d["kode"] == kode), None)
    if ada:
        ada.update(terakhir=time.strftime("%Y-%m-%dT%H:%M:%S"), versi=a.get("p_versi", ""),
                   nama_komputer=a.get("p_nama_komputer", ""))
    else:
        batas = p["maks_perangkat"] if p["maks_perangkat"] is not None else ATUR["maks_perangkat"]
        if p["peran"] != "admin" and batas > 0 and len(milik) >= batas:
            return gagal("perangkat_penuh", f"Akun ini sudah dipakai di {len(milik)} komputer (batas {batas}). "
                                            "Minta admin melepas komputer yang lama.")
        PERANGKAT.append({"id": len(PERANGKAT) + 1 + int(time.time()) % 1000, "petugas_id": uid, "kode": kode,
                          "nama_komputer": a.get("p_nama_komputer", ""), "versi": a.get("p_versi", ""),
                          "pertama": time.strftime("%Y-%m-%dT%H:%M:%S"),
                          "terakhir": time.strftime("%Y-%m-%dT%H:%M:%S")})
    p["terakhir_masuk"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return {"ok": True, "nama": p["nama"], "email": p["email"], "peran": p["peran"],
            "puskesmas": p["puskesmas"], "pengumuman": ATUR["pengumuman"], **info()}


def rpc(fungsi, uid, a):
    LOG.append(fungsi)
    if fungsi == "periksa_izin":
        return periksa_izin(uid, a)
    if fungsi == "ping":
        return {"ok": True, "waktu": time.strftime("%H:%M:%S")}
    if fungsi == "catat_pemakaian":
        if not uid or PETUGAS.get(uid, {}).get("status") != "aktif":
            return gagal("bukan_petugas_aktif", "Hanya petugas aktif.")
        k = (uid, a["p_tanggal"])
        d = PAKAI.setdefault(k, {"tuntas": 0, "beres_lain": 0, "data_salah": 0, "gagal": 0, "versi": ""})
        for x in ("tuntas", "beres_lain", "data_salah", "gagal"):
            d[x] = max(0, d[x] + int(a.get("p_" + x) or 0))
        d["versi"] = a.get("p_versi", "")
        return {"ok": True}
    if fungsi == "admin_pemakaian" and admin(uid):
        hari = {}
        org = {}
        for (u, tgl), d in PAKAI.items():
            h = hari.setdefault(tgl, {"tanggal": tgl, "tuntas": 0, "beres_lain": 0, "data_salah": 0, "gagal": 0, "petugas": 0})
            o = org.setdefault(u, {"nama": PETUGAS[u]["nama"], "email": PETUGAS[u]["email"], "puskesmas": PETUGAS[u]["puskesmas"],
                                   "tuntas": 0, "beres_lain": 0, "data_salah": 0, "gagal": 0, "hari_aktif": 0, "terakhir": tgl, "versi": d["versi"]})
            for x in ("tuntas", "beres_lain", "data_salah", "gagal"):
                h[x] += d[x]; o[x] += d[x]
            h["petugas"] += 1; o["hari_aktif"] += 1
        return {"ok": True, "per_hari": sorted(hari.values(), key=lambda h: h["tanggal"], reverse=True),
                "per_petugas": list(org.values())}
    if fungsi == "profil_saya":
        if not uid:
            return gagal("belum_masuk", "Silakan masuk.")
        p = PETUGAS.get(uid)
        if not p:
            return gagal("akun_tidak_ada", "Akun tidak terdaftar sebagai petugas. Hubungi admin.")
        return {"ok": True, "status": p["status"], "peran": p["peran"], "nama": p["nama"], "email": p["email"],
                "puskesmas": p["puskesmas"], "pengumuman": ATUR["pengumuman"], **info()}
    if not admin(uid):
        return gagal("bukan_admin", "Hanya admin.")
    if fungsi == "admin_daftar":
        return {"ok": True, "pengaturan": dict(ATUR), "petugas": [
            dict(p, perangkat=[{k: d[k] for k in ("id", "nama_komputer", "versi", "pertama", "terakhir")}
                               for d in PERANGKAT if d["petugas_id"] == p["id"]])
            for p in sorted(PETUGAS.values(), key=lambda p: (p["status"] != "menunggu", p["dibuat"]))]}
    if fungsi == "admin_ubah":
        pid = a["p_id"]
        if pid == uid and ((a.get("p_status") or "aktif") != "aktif" or (a.get("p_peran") or "admin") != "admin"):
            return gagal("diri_sendiri", "Tidak bisa menonaktifkan atau menurunkan peran akun sendiri.")
        p = PETUGAS.get(pid)
        if not p:
            return gagal("tidak_ada", "Petugas tidak ditemukan.")
        for k in ("status", "peran", "nama", "puskesmas", "no_hp"):
            if a.get(f"p_{k}") is not None:
                p[k] = a[f"p_{k}"]
        if a.get("p_maks_perangkat") is not None:
            p["maks_perangkat"] = None if a["p_maks_perangkat"] < 0 else a["p_maks_perangkat"]
        return {"ok": True}
    if fungsi == "admin_lepas_perangkat":
        PERANGKAT[:] = [d for d in PERANGKAT if d["id"] != a["p_id"]]
        return {"ok": True}
    if fungsi == "admin_ganti_sandi":
        if len(a.get("p_sandi") or "") < 8:
            return gagal("sandi_pendek", "Kata sandi minimal 8 karakter.")
        USERS[a["p_id"]]["pw"] = a["p_sandi"]
        return {"ok": True}
    if fungsi == "admin_ganti_email":                      # supabase/tambahan-ubah-email.sql
        import re as _re
        e = (a.get("p_email") or "").strip().lower()
        if not _re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e) or len(e) > 254:
            return gagal("email_salah", "Format email tidak sah.")
        if any(u["email"].lower() == e and i != a["p_id"] for i, u in USERS.items()):
            return gagal("email_dipakai", "Email ini sudah dipakai akun lain.")
        if a["p_id"] not in USERS:
            return gagal("tidak_ada", "Petugas tidak ditemukan.")
        USERS[a["p_id"]]["email"] = e
        PETUGAS[a["p_id"]]["email"] = e
        return {"ok": True}
    if fungsi == "admin_terbitkan":
        import re as _re
        if not _re.fullmatch(r"\d{4}\.\d{2}\.\d{2}(\.\d{4})?", a.get("p_versi") or ""):
            return gagal("versi_salah", "Format versi tidak dikenal.")
        if not _re.fullmatch(r"[0-9a-f]{64}", a.get("p_sha256") or ""):
            return gagal("sidik_salah", "Sidik SHA-256 tidak sah.")
        ATUR.update(versi_terbaru=a["p_versi"], sha256_terbaru=a["p_sha256"], ukuran_terbaru=a.get("p_ukuran") or 0,
                    catatan_terbaru=a.get("p_catatan") or "", diterbitkan=time.strftime("%Y-%m-%dT%H:%M:%S"))
        return {"ok": True}
    if fungsi == "admin_pengaturan":
        if a.get("p_versi_minimal") is not None:
            ATUR["versi_minimal"] = a["p_versi_minimal"]
        if a.get("p_maks_perangkat") is not None:
            ATUR["maks_perangkat"] = max(0, a["p_maks_perangkat"])
        if a.get("p_pengumuman") is not None:
            ATUR["pengumuman"] = a["p_pengumuman"]
        return {"ok": True}
    return None


class P(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def uid(self):
        tok = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        uid, sampai = AKSES.get(tok, (None, 0))
        return uid if uid and sampai > time.time() else None

    def kirim(self, kode, isi=None):
        b = json.dumps(isi).encode() if isi is not None else b""
        self.send_response(kode)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/storage/v1/object/sign/paket/"):
            nama = u.path.rsplit("/", 1)[-1]
            tok = parse_qs(u.query).get("token", [""])[0]
            if tok != f"tanda-{nama}" or nama not in BERKAS:
                self.kirim(400, {"error": "InvalidSignature", "message": "invalid signature"}); return
            isi, jenis, _ = BERKAS[nama]
            self.send_response(200)
            self.send_header("Content-Type", jenis)
            if "download" in parse_qs(u.query):
                self.send_header("Content-Disposition", f'attachment; filename="{nama}"')
            self.send_header("Content-Length", str(len(isi)))
            self.end_headers(); self.wfile.write(isi); return
        if self.path == "/uji/keadaan":
            self.kirim(200, {"petugas": PETUGAS, "perangkat": PERANGKAT, "atur": ATUR, "log": LOG[-50:]})
        else:
            self.kirim(404, {})

    def do_POST(self):
        u = urlparse(self.path)
        mentah = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if u.path.startswith("/storage/v1/"):
            return self.storage(u, mentah)
        a = json.loads(mentah or b"{}")
        if u.path.startswith("/uji/"):
            if u.path == "/uji/sql":                       # tiru SQL Editor
                for p in PETUGAS.values():
                    if p["email"] == a["email"]:
                        p.update(a["ubah"])
                self.kirim(200, {"ok": True})
            return
        if self.headers.get("apikey") != KUNCI:
            self.kirim(401, {"message": "Invalid API key"})
            return
        if u.path == "/auth/v1/signup":
            email = a.get("email", "").lower()
            if any(x["email"] == email for x in USERS.values()):
                self.kirim(422, {"code": 422, "error_code": "user_already_exists", "msg": "User already registered"})
                return
            if len(a.get("password", "")) < 6:
                self.kirim(422, {"code": 422, "error_code": "weak_password", "msg": "Password should be at least 6"})
                return
            uid = str(uuid.uuid4())
            USERS[uid] = {"email": email, "pw": a["password"]}
            m = a.get("data") or {}
            PETUGAS[uid] = {"id": uid, "email": email, "nama": m.get("nama", "")[:100],
                            "puskesmas": m.get("puskesmas", "")[:100], "no_hp": m.get("no_hp", "")[:30],
                            "peran": "petugas", "status": "menunggu", "maks_perangkat": None,
                            "dibuat": time.strftime("%Y-%m-%dT%H:%M:%S.") + f"{len(USERS):04d}",
                            "terakhir_masuk": None}
            self.kirim(200, sesi(uid))
        elif u.path == "/auth/v1/token":
            jenis = parse_qs(u.query).get("grant_type", [""])[0]
            if jenis == "password":
                uid = next((k for k, x in USERS.items()
                            if x["email"] == a.get("email", "").lower() and x["pw"] == a.get("password")), None)
                if not uid:
                    self.kirim(400, {"code": 400, "error_code": "invalid_credentials",
                                     "msg": "Invalid login credentials"})
                    return
                self.kirim(200, sesi(uid))
            elif jenis == "refresh_token":
                uid = SEGAR.pop(a.get("refresh_token"), None)
                if not uid:
                    self.kirim(400, {"code": 400, "error_code": "refresh_token_not_found", "msg": "Invalid Refresh Token"})
                    return
                LOG.append("refresh")
                self.kirim(200, sesi(uid))
        elif u.path == "/auth/v1/logout":
            self.kirim(204)
        elif u.path.startswith("/rest/v1/rpc/"):
            tok = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
            uid, sampai = AKSES.get(tok, (None, 0))
            if uid and sampai < time.time():
                self.kirim(401, {"code": "PGRST301", "message": "JWT expired"})
                return
            hasil = rpc(u.path.rsplit("/", 1)[-1], uid, a)
            if hasil is None:
                self.kirim(404, {"message": "Could not find the function"})
            else:
                self.kirim(200, hasil)
        else:
            self.kirim(404, {})


def _storage(self, u, mentah):
    if self.headers.get("apikey") != KUNCI:
        self.kirim(401, {"message": "Invalid API key"}); return
    uid = self.uid()
    aktif = bool(uid and PETUGAS.get(uid, {}).get("status") == "aktif")
    if u.path == "/storage/v1/object/list/paket":
        if not aktif:
            self.kirim(200, []); return                    # RLS: tak terlihat
        self.kirim(200, [{"name": n, "id": n, "updated_at": w, "created_at": w,
                          "metadata": {"size": len(b), "mimetype": j}} for n, (b, j, w) in BERKAS.items()]); return
    if u.path.startswith("/storage/v1/object/sign/paket/"):
        nama = u.path.rsplit("/", 1)[-1]
        if not aktif or nama not in BERKAS:
            self.kirim(400, {"statusCode": "404", "error": "not_found", "message": "Object not found"}); return
        self.kirim(200, {"signedURL": f"/object/sign/paket/{nama}?token=tanda-{nama}"}); return
    if u.path.startswith("/storage/v1/object/paket/"):
        nama = u.path.rsplit("/", 1)[-1]
        if not admin(uid):
            self.kirim(400, {"statusCode": "403", "error": "Unauthorized",
                             "message": "new row violates row-level security policy"}); return
        jenis = self.headers.get("Content-Type", "")
        isi = mentah
        if jenis.startswith("multipart/form-data"):     # supabase-js mengirim FormData
            batas = jenis.split("boundary=")[1].encode()
            for bagian in mentah.split(b"--" + batas):
                kepala, _, badan = bagian.partition(CRLF * 2)
                if b'name=""' in kepala or b"filename" in kepala:
                    isi = badan.rsplit(CRLF, 1)[0]
                    m = [l for l in kepala.split(CRLF) if l.lower().startswith(b"content-type")]
                    jenis = m[0].split(b":", 1)[1].strip().decode() if m else "application/octet-stream"
        BERKAS[nama] = (isi, jenis, time.strftime("%Y-%m-%dT%H:%M:%SZ"))
        LOG.append(f"unggah {nama} {len(isi)}")
        self.kirim(200, {"Key": f"paket/{nama}", "Id": nama}); return
    self.kirim(404, {"message": "not found"})


P.storage = _storage

ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8798), P).serve_forever()
