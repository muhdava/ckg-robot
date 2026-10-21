r"""
Buat DEMO interaktif aplikasi untuk website (Website CKG Robot\demo\index.html).

    python alat\buat_demo_web.py

Demo = antarmuka.html yang ASLI, ditambah tiruan server lokal di dalam
halamannya sendiri (window.fetch untuk /api/* dijawab JavaScript). Jadi
tampilannya selalu sama persis dengan aplikasi; jalankan ulang skrip ini
setiap kali antarmuka.html berubah, lalu deploy ulang Netlify.

Tidak ada yang terhubung ke portal. Datanya rekaan ("CONTOH ...").
Halaman demo ikut terkunci: hanya akun AKTIF (sama dengan website) yang
bisa membukanya; selain itu dialihkan ke halaman masuk.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "inti"))
import sapu_pelayanan  # noqa: E402
import tatalaksana  # noqa: E402
SUMBER = AKAR / "inti" / "antarmuka.html"
WEB = AKAR.parent / "Website CKG Robot"
TUJUAN = WEB / "demo" / "index.html"

TIRUAN = r"""<script>
/* ======================================================================
   SERVER TIRUAN UNTUK DEMO - dibuat oleh alat/buat_demo_web.py
   Semua /api/* dijawab di sini. Tidak ada yang dikirim ke mana pun.
   ====================================================================== */
(() => {
const asli = window.fetch.bind(window);
const jeda = (ms) => new Promise(r => setTimeout(r, ms));
const J = (d, kode = 200) => new Response(JSON.stringify(d),
    {status: kode, headers: {'Content-Type': 'application/json'}});
let benih = 20261007;
const acak = () => (benih = (benih * 16807) % 2147483647) / 2147483647;
const pilih = (a) => a[Math.floor(acak() * a.length)];
const jam = () => new Date().toTimeString().slice(0, 8);

const DEPAN = ['ADI', 'BUDI', 'CITRA', 'DEWI', 'EKA', 'FAJAR', 'GITA', 'HADI', 'INDAH', 'JOKO', 'KARTIKA',
               'LINA', 'MAYA', 'NANDA', 'OKI', 'PUTRI', 'RIZKY', 'SARI', 'TONI', 'WULAN'];
const BELAKANG = ['SAPUTRA', 'LESTARI', 'PRATAMA', 'WULANDARI', 'NUGROHO', 'PERMATA', 'SANTOSO', 'KUSUMA',
                  'HIDAYAT', 'RAHMAWATI', 'SETIAWAN', 'ANGGRAINI'];
const BERKAS = [
  {nama: 'contoh-dewasa-lansia.csv', jumlah: 120, sekolah: false},
  {nama: 'contoh-sdn-lagoa-kelas-5.csv', jumlah: 64, sekolah: true},
];
let K = null;                                  // pekerjaan yang sedang berjalan

function uraiRentang(teks, maks){
  const hasil = new Set();
  for (const bagian of String(teks || '').split(',')){
    const m = bagian.trim().match(/^(\d+)\s*(?:-\s*(\d+))?$/);
    if (!m) continue;
    const a = +m[1], b = m[2] ? +m[2] : a;
    for (let i = Math.min(a, b); i <= Math.max(a, b) && hasil.size < 2000; i++)
      if (i >= 1 && i <= maks) hasil.add(i);
  }
  return [...hasil].sort((x, y) => x - y);
}

function nasib(sekolah){
  const r = acak();
  const form = sekolah ? 9 + Math.floor(acak() * 4) : 12 + Math.floor(acak() * 6);
  if (r < .74) return {status: 'tuntas', tiket: String(100 + Math.floor(acak() * 900)).padStart(4, '0'),
                       keterangan: (sekolah ? 'cari murid · konfirmasi hadir' : 'terdaftar · konfirmasi hadir')
                                   + ` · mulai pemeriksaan · ${form} form terisi`};
  if (r < .84) return {status: 'sudah_pelayanan', keterangan: 'portal: sudah menerima layanan — dilewati'};
  if (r < .89) return sekolah ? {status: 'ckg_umum', keterangan: 'sudah diperiksa lewat CKG Umum'}
                              : {status: 'ckg_sekolah', keterangan: 'sudah diperiksa lewat jalur CKG Sekolah'};
  if (r < .94) return {status: 'tidak_valid', keterangan: 'portal menolak: tanggal lahir tidak cocok dengan NIK'};
  if (r < .97) return {status: 'puskesmas_berbeda', keterangan: 'sudah diperiksa di puskesmas lain'};
  return {status: 'gagal_daftar', keterangan: 'tiket tidak muncul dalam 45 dtk — bisa dijalankan ulang'};
}

// Tatalaksana Gigi: tanpa berkas, satu pekerja, peserta "diambil dari portal".
function nasibTl(){
  const r = acak();
  if (r < .88) return {status: 'tuntas', keterangan: 'status awal: Belum tatalaksana | form dikirim | '
                                                     + 'status: Selesai tatalaksana'};
  if (r < .96) return {status: 'sudah_tatalaksana', keterangan: 'status awal: Selesai tatalaksana'};
  return {status: 'gagal_isi', keterangan: 'TIDAK dikirim - isian tidak sesuai (contoh) | menyerah setelah 3 percobaan'};
}

function mulai(d){
  if (K && !K.selesai && !d.paksa)
    return J({ok: false, bisa_paksa: true, pesan: 'Masih ada pekerjaan sebelumnya yang berjalan. '
                                                + 'Tekan “Mulai paksa” bila memang mau memulai baru.'});
  if (d.alur === 'tatalaksana_gigi' || d.alur === 'sapu_belum'){
    const n = parseInt(d.jumlah, 10);
    if (!(n >= 1 && n <= 500)) return J({ok: false, pesan: 'Jumlah peserta 1 sampai 500 per jalan.'});
    const antre = Array.from({length: Math.min(n, 40)}, (_, i) => i + 1);
    const w = {nomor: 1, antre, sudah: 0, total: antre.length, login: false, akun: '', berikut: 0,
               catatan: [d.alur === 'sapu_belum'
                           ? `- ${jam()} Alur: Sapu Belum Pemeriksaan (tanpa berkas) · dewasa/lansia · maksimal ${n} peserta`
                           : `- ${jam()} Alur: Tatalaksana Gigi · 2026 · Gigi · Gigi berlubang · maksimal ${n} peserta`,
                         `- ${jam()} Browser portal dibuka — menunggu login…`]};
    K = {tl: d.alur === 'tatalaksana_gigi', berkas: {sekolah: false}, pekerja: [w], hasil: [], mulai: Math.floor(Date.now() / 1000),
         berhenti: false, selesai: false};
    return J({ok: true});
  }
  const b = BERKAS.find(x => x.nama === d.berkas) || BERKAS[0];
  const nomor = uraiRentang(d.rentang, b.jumlah).slice(0, 150);
  if (!nomor.length)
    return J({ok: false, pesan: `Nomor data "${d.rentang}" tidak ada di ${b.nama} (1–${b.jumlah}).`});
  const n = Math.max(1, Math.min(+d.pekerja || 1, nomor.length));
  const w = Array.from({length: n}, (_, i) => ({nomor: i + 1, antre: [], sudah: 0, total: 0,
      login: false, akun: '', catatan: [], berikut: 0}));
  nomor.forEach((no, i) => w[i % n].antre.push(no));
  w.forEach(x => {
    x.total = x.antre.length;
    x.catatan.push(`- ${jam()} Pekerja ${x.nomor}: ${x.total} peserta · profil .profil-browser-${x.nomor}`,
                   `- ${jam()} Browser portal dibuka — menunggu login…`);
  });
  K = {berkas: b, pekerja: w, hasil: [], mulai: Math.floor(Date.now() / 1000), berhenti: false, selesai: false};
  return J({ok: true});
}

function sudahLogin(d){
  if (!K) return J({ok: false});
  K.pekerja.filter(w => !d.pekerja || w.nomor === d.pekerja).forEach(w => {
    if (w.login) return;
    w.login = true;
    w.akun = 'PUSKESMAS CONTOH' + (K.pekerja.length > 1 ? ' ' + w.nomor : '');
    w.berikut = Date.now() + 900;
    w.catatan.push(`- ${jam()} Login diterima (${w.akun}) — mulai bekerja`);
  });
  return J({ok: true});
}

function maju(){
  if (!K || K.selesai) return;
  const kini = Date.now();
  for (const w of K.pekerja){
    if (!w.login) continue;
    if (K.berhenti && w.antre.length){
      w.catatan.push(`- ${jam()} Dihentikan atas permintaan — ${w.antre.length} peserta tidak dikerjakan`);
      w.antre = [];
    }
    while (w.antre.length && kini >= w.berikut){
      const no = w.antre.shift();
      const nik = '3172030000' + String(no).padStart(6, '0');
      const nama = `CONTOH ${pilih(DEPAN)} ${pilih(BELAKANG)}`;
      const h = K.tl ? nasibTl() : nasib(K.berkas.sekolah);
      const t = `- ${jam()} baris ${no}`;
      let lama = 1100 + acak() * 900;
      if (K.tl){
        // tanpa gangguan 429 di demo tatalaksana
      } else if (acak() < .06){
        w.catatan.push(`${t} 429 Too Many Requests — tunggu 15 dtk, lalu muat ulang`,
                       `${t} daftar layanan kembali — lanjut form yang belum`);
        lama += 2500;
      } else if (acak() < .05){
        w.catatan.push(`${t} tertahan di "Kembali ke Halaman Utama" — muat ulang: form sudah terisi → Kirim`);
        lama += 1500;
      }
      w.catatan.push(`${t} ${h.status}${h.tiket ? ' · tiket ' + h.tiket : ''}`);
      K.hasil.push({baris: no, nik, nama, status: h.status, keterangan: h.keterangan,
                    tiket: h.tiket || '', waktu: jam()});
      w.sudah++;
      w.berikut += lama;
    }
  }
  if (K.pekerja.every(w => w.login && !w.antre.length)){
    K.selesai = true;
    K.pekerja.forEach(w => w.catatan.push(`- ${jam()} Selesai.`));
  }
}

function keadaanPekerja(w){
  if (!w.login) return 'menunggu-login';
  return w.antre.length ? 'berjalan' : 'selesai';
}

function status(){
  if (!K) return J({keadaan: 'siap', pesan: '', total: 0, selesai: 0, hasil: [], catatan: [],
                    berkas_hasil: '', pekerja: [], mulai_pada: 0});
  maju();
  const tunggu = K.pekerja.some(w => !w.login);
  const keadaan = K.selesai ? 'selesai' : tunggu ? 'menunggu-login' : 'berjalan';
  const pesan = K.selesai
      ? (K.berhenti ? 'Dihentikan. Peserta yang sudah dikerjakan tetap tercatat.'
                    : `Selesai. ${K.hasil.length} peserta dikerjakan.`)
      : tunggu ? 'DEMO: di aplikasi asli, browser portal terbuka dan kamu login sendiri (ada captcha). '
               + 'Di sini cukup tekan tombol “Sudah login”.' : '';
  const catatan = [];
  K.pekerja.forEach(w => w.catatan.forEach(c => catatan.push(`[P${w.nomor}] ${c}`)));
  return J({
    keadaan, pesan, total: K.pekerja.reduce((s, w) => s + w.total, 0), selesai: K.hasil.length,
    hasil: [...K.hasil].sort((a, b) => a.baris - b.baris),
    catatan: catatan.sort((a, b) => a.slice(7).localeCompare(b.slice(7))).slice(-160),
    berkas_hasil: K.pekerja.map(w => `hasil-demo-p${w.nomor}.csv`).join(', '),
    mulai_pada: K.mulai,
    pekerja: K.pekerja.map(w => ({nomor: w.nomor, keadaan: keadaanPekerja(w),
        pesan: w.login ? '' : `Login akun untuk pekerja ${w.nomor} di jendela browsernya.`,
        total: w.total, sudah: w.sudah, berkas: `hasil-demo-p${w.nomor}.csv`, akun: w.akun,
        catatan: w.catatan})),
  });
}

async function konversi(d){
  await jeda(900);
  const dasar = String(d.berkas || 'berkas').replace(/\.[^.]+$/, '');
  const sekolah = /sekolah|sd|smp|sma|kelas|murid|siswa/i.test(dasar);
  const nama = 'datackg-' + dasar.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') + '.csv';
  const jumlah = 24 + (dasar.length * 7) % 60;
  if (!BERKAS.some(b => b.nama === nama)) BERKAS.unshift({nama, jumlah, sekolah});
  return J({berkas: d.berkas, sebutan: sekolah ? 'Register sekolah' : 'Template CKG Dewasa/Lansia',
            alasan: 'DEMO — isi berkasmu tidak dibaca dan tidak dikirim ke mana pun',
            jumlah, tujuan: 'data\\' + nama, peringatan: [],
            catatan: ['baris 12: NIK hanya 15 angka — tidak akan dijalankan (contoh)',
                      'baris 31: tanggal lahir disamakan dengan NIK (contoh)']});
}

const tanpaBerkas = (apa) => J({ok: false, pesan: `DEMO: di aplikasi asli, tombol ini menyimpan ${apa}. `
                                                + 'Di demo tidak ada berkas yang dibuat.'});

window.fetch = async (alamat, pilihan = {}) => {
  const u = new URL(alamat, location.href);
  if (!u.pathname.startsWith('/api/')) return asli(alamat, pilihan);
  let d = {};
  try { d = pilihan.body ? JSON.parse(pilihan.body) : {}; } catch (e) {}
  await jeda(120);
  switch (u.pathname){
    case '/api/awal': return J({berkas: BERKAS.map(b => ({nama: b.nama, jumlah: b.jumlah})),
        tahap: 'penuh', kategori: 'auto', mode_uji: false, maks_pekerja: 4,
        pengguna: 'Petugas Demo', peran: '', pengumuman: '', versi: 'demo', online: true,
        tatalaksana: __TATALAKSANA__, sapu: __SAPU__});
    case '/api/status': return status();
    case '/api/mulai': return mulai(d);
    case '/api/sudah-login': return sudahLogin(d);
    case '/api/berhenti': if (K) K.berhenti = true; return J({ok: true});
    case '/api/konversi': return konversi(d);
    case '/api/export': return tanpaBerkas('Excel berisi lembar Hasil & Rekap');
    case '/api/laporan': return tanpaBerkas('laporan Excel berisi data asli + kolom hasil');
    case '/api/kabar': return J({ok: true, online: true, pengumuman: '', akun: ''});
    case '/api/periksa-pembaruan': await jeda(700); return J({ok: true, pembaruan: null, versi: 'demo'});
    case '/api/fokus': return J({ok: false, pesan: 'Di demo tidak ada jendela browser.'});
    default: return J({ok: true});
  }
};
})();
</script>
"""

GERBANG = r"""<script type="module">
// Demo ikut terkunci seperti websitenya: hanya akun AKTIF.
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';
const sb = createClient('__URL__', '__KUNCI__');
const keluar = () => location.replace('../');
try {
  const { data: { session } } = await sb.auth.getSession();
  if (!session) keluar();
  else {
    const { data } = await sb.rpc('profil_saya');
    if (data?.ok && data.status === 'aktif') document.documentElement.classList.add('boleh');
    else keluar();
  }
} catch (e) { keluar(); }
</script>
"""

GAYA = """
  /* ---- DEMO ---- */
  html:not(.boleh) body{visibility:hidden}
  .pita-demo{background:#4338ca; color:#fff; text-align:center;
             font-size:13px; font-weight:600; padding:7px 12px; letter-spacing:.01em}
  #tombol-keluar, #tombol-admin, .tombol-panduan, .pengguna .tautan{display:none !important}
"""


def main() -> None:
    t = SUMBER.read_text(encoding="utf-8")
    web = (WEB / "index.html").read_text(encoding="utf-8")
    url = re.search(r"const SUPABASE_URL = '([^']+)'", web).group(1)
    kunci = re.search(r"const KUNCI_PUBLIK = '([^']+)'", web).group(1)

    def ganti(lama: str, baru: str) -> None:
        nonlocal t
        assert t.count(lama) == 1, f"{t.count(lama)}x {lama[:60]!r}"
        t = t.replace(lama, baru)

    ganti("<title>", "<title>Demo · ")
    ganti("</style>", GAYA + "</style>\n" + GERBANG.replace("__URL__", url).replace("__KUNCI__", kunci))
    # Pita di DALAM kepala yang menempel, supaya tidak menutupi kepala aplikasi.
    ganti('<div class="atas-tetap">', '<div class="atas-tetap">\n<div class="pita-demo">🧪 MODE DEMO · data '
                                       'rekaan, tidak terhubung ke portal. Tidak ada yang benar-benar didaftarkan.</div>')
    # Tiruan harus terpasang SEBELUM skrip aplikasi memanggil /api/awal.
    # Pilihan Tatalaksana Gigi diambil dari kode robot, bukan disalin ulang.
    tiruan = TIRUAN.replace("__SAPU__", json.dumps(sapu_pelayanan.pilihan_untuk_aplikasi(),
                                                    ensure_ascii=False))
    tiruan = tiruan.replace("__TATALAKSANA__", json.dumps(tatalaksana.pilihan_untuk_aplikasi(),
                                                          ensure_ascii=False))
    ganti("<script>\nconst $", tiruan + "<script>\nconst $")
    TUJUAN.parent.mkdir(parents=True, exist_ok=True)
    TUJUAN.write_text(t, encoding="utf-8")
    print(f"demo ditulis: {TUJUAN}  ({len(t) // 1024} KB)")


if __name__ == "__main__":
    main()
