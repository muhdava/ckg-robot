r"""
Buat halaman KELOLA PETUGAS untuk website (Website CKG Robot\kelola\index.html).

    python alat\buat_admin_web.py

Dibuat dari inti\admin.html yang ASLI: fungsi kirim('/api/admin/...') -
yang di aplikasi diteruskan server lokal ke Supabase - diganti panggilan
LANGSUNG ke fungsi admin_* di Supabase dengan sesi admin yang masuk di website.
Jadi admin bisa menyetujui petugas dari HP. Jalankan ulang skrip ini setiap
kali admin.html berubah, lalu commit & push repo website.

"Terbitkan pembaruan" tidak ada di website (butuh ZIP di komputer admin);
kartunya disembunyikan. Halaman hanya terbuka untuk akun ADMIN yang aktif.
"""
from __future__ import annotations

import re
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
SUMBER = AKAR / "inti" / "admin.html"
WEB = AKAR.parent / "Website CKG Robot"
TUJUAN = WEB / "kelola" / "index.html"

KIRIM_WEB = r"""// ------------------------------------------------------------ versi WEBSITE
// Panggilan /api/admin/* diteruskan LANGSUNG ke fungsi admin_* di Supabase
// (dibuat oleh alat/buat_admin_web.py dari admin.html aplikasi).
const SB_URL = '__URL__', SB_KUNCI = '__KUNCI__';
const sb = supabase.createClient(SB_URL, SB_KUNCI);
const SIAP = (async () => {
  const { data: { session } } = await sb.auth.getSession();
  if (!session){ location.replace('../'); return new Promise(() => {}); }
  const { data } = await sb.rpc('profil_saya');
  if (!(data && data.ok && data.status === 'aktif' && data.peran === 'admin')){
    document.documentElement.classList.add('boleh');      // halaman disembunyikan sampai dicek
    document.body.innerHTML = '<div style="max-width:420px;margin:80px auto;font:15px Segoe UI,sans-serif;'
      + 'text-align:center">Halaman ini hanya untuk <b>admin</b>.<br><br><a href="../">← Kembali ke website</a></div>';
    return new Promise(() => {});
  }
  document.documentElement.classList.add('boleh');
})();
const terjemahWeb = (m) => /already registered|already exists/i.test(m) ? 'Email ini sudah terdaftar.'
  : /password/i.test(m) ? 'Kata sandi terlalu lemah (minimal 8 karakter).' : m;

async function kirim(alamat, isi){
  await SIAP;
  isi = isi || {};
  const rpc = async (f, a) => {
    const { data, error } = await sb.rpc(f, a || {});
    if (error) return { ok: false, pesan: error.message };
    return data || { ok: false, pesan: 'Jawaban server kosong.' };
  };
  switch (alamat.replace('/api/admin/', '')){
    case 'daftar': return rpc('admin_daftar');
    case 'ubah': {
      const a = { p_id: isi.id };
      for (const k of ['status', 'peran', 'nama', 'puskesmas', 'no_hp']) if (isi[k] != null) a['p_' + k] = String(isi[k]);
      if (isi.maks_perangkat != null) a.p_maks_perangkat = parseInt(isi.maks_perangkat, 10);
      return rpc('admin_ubah', a);
    }
    case 'lepas-perangkat': return rpc('admin_lepas_perangkat', { p_id: Number(isi.id) });
    case 'ganti-sandi': return rpc('admin_ganti_sandi', { p_id: isi.id, p_sandi: String(isi.sandi || '') });
    case 'pengaturan': {
      const a = {};
      if (isi.versi_minimal != null) a.p_versi_minimal = String(isi.versi_minimal).trim();
      if (isi.maks_perangkat != null) a.p_maks_perangkat = parseInt(isi.maks_perangkat, 10) || 0;
      if (isi.pengumuman != null) a.p_pengumuman = String(isi.pengumuman);
      return rpc('admin_pengaturan', a);
    }
    case 'pemakaian': return rpc('admin_pemakaian', { p_hari: isi.hari || 14 });
    case 'buat-akun': {
      if (String(isi.sandi || '').length < 8) return { ok: false, pesan: 'Kata sandi minimal 8 karakter.' };
      // Klien TERPISAH tanpa penyimpanan sesi: mendaftarkan akun baru memberi
      // sesi untuk akun itu, dan sesi admin di halaman ini tidak boleh tertimpa.
      const lain = supabase.createClient(SB_URL, SB_KUNCI, { auth: { persistSession: false,
        autoRefreshToken: false, detectSessionInUrl: false, storageKey: 'ckg-buat-akun' } });
      const { data, error } = await lain.auth.signUp({ email: String(isi.email || '').trim(),
        password: String(isi.sandi), options: { data: { nama: String(isi.nama || '').trim(),
          puskesmas: String(isi.puskesmas || '').trim(), no_hp: String(isi.no_hp || '').trim() } } });
      if (error) return { ok: false, pesan: terjemahWeb(error.message) };
      const id = data && data.user && data.user.id;
      if (!id) return { ok: false, pesan: 'Akun dibuat, tetapi ID-nya tidak diterima. Setujui dari daftar.' };
      return rpc('admin_ubah', { p_id: id, p_status: 'aktif' });
    }
    default: return { ok: false, pesan: 'Hanya tersedia di aplikasi CKG Robot.' };
  }
}"""


def main() -> None:
    t = SUMBER.read_text(encoding="utf-8")
    web = (WEB / "index.html").read_text(encoding="utf-8")
    url = re.search(r"const SUPABASE_URL = '([^']+)'", web).group(1)
    kunci = re.search(r"const KUNCI_PUBLIK = '([^']+)'", web).group(1)

    def ganti(lama: str, baru: str, pola: bool = False) -> None:
        nonlocal t
        if pola:
            t, n = re.subn(lama, lambda _: baru, t, count=1, flags=re.S)
        else:
            n = t.count(lama)
            t = t.replace(lama, baru, 1)
        assert n == 1, f"{n}x {lama[:60]!r}"

    ganti(r"async function kirim\(alamat, isi\)\{.*?\n\}\n", KIRIM_WEB.replace("__URL__", url)
          .replace("__KUNCI__", kunci) + "\n", pola=True)
    ganti("<script>\nconst $", '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>\n'
                             "<script>\nconst $")
    ganti("</style>", "  html:not(.boleh) body{visibility:hidden}\n  #kartu-terbit{display:none}\n</style>")
    ganti('<a class="kembali" href="/">← Kembali ke aplikasi</a>', '<a class="kembali" href="../">← Kembali ke website</a>')
    ganti("<p>CKG Robot · login online</p>", "<p>CKG Robot · website (terbitkan pembaruan tetap dari aplikasi)</p>")
    ganti(r"fetch\('/api/awal'\).*?\.catch\(\(\) => \{\}\);\n", "", pola=True)
    ganti("muatPaket();\n", "")
    TUJUAN.parent.mkdir(parents=True, exist_ok=True)
    TUJUAN.write_text(t, encoding="utf-8")
    print(f"halaman admin web ditulis: {TUJUAN}  ({len(t) // 1024} KB)")


if __name__ == "__main__":
    main()
