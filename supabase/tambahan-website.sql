-- =====================================================================
--  CKG Robot - TAMBAHAN untuk website (ckg-robot.netlify.app)
--
--  Jalankan SEKALI di Supabase > SQL Editor, SETELAH skema.sql.
--  Aman dijalankan ulang. Aturan akses berkas ada di bagian 2
--  (tambahan-website-2-aturan-berkas.sql).
--
--  1. profil_saya()   : website menanyakan status akun yang sedang masuk
--                       (tanpa mendaftarkan komputer seperti periksa_izin).
--  2. bucket 'paket'  : tempat ZIP aplikasi & PDF panduan. PRIVAT - hanya
--                       petugas AKTIF yang bisa membuat tautan unduhnya,
--                       hanya ADMIN yang bisa mengunggah/mengganti.
--  PENTING: bila berkas ini dijalankan ULANG, jalankan ulang juga
--  tambahan-pembaruan.sql sesudahnya - berkas itu memperbarui
--  periksa_izin/profil_saya yang ditimpa di sini.
-- =====================================================================

create or replace function public.profil_saya()
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare
  p public.petugas;
begin
  if auth.uid() is null then
    return public._gagal('belum_masuk', 'Silakan masuk.');
  end if;
  select * into p from public.petugas where id = auth.uid();
  if not found then
    return public._gagal('akun_tidak_ada', 'Akun tidak terdaftar sebagai petugas. Hubungi admin.');
  end if;
  return jsonb_build_object('ok', true, 'status', p.status, 'peran', p.peran, 'nama', p.nama,
                            'email', p.email, 'puskesmas', p.puskesmas,
                            'pengumuman', (select pengumuman from public.pengaturan where id = 1));
end $$;

revoke all on function public.profil_saya() from public, anon;
grant execute on function public.profil_saya() to authenticated;


-- ------------------------------------------------------- penyimpanan berkas
insert into storage.buckets (id, name, public, file_size_limit)
values ('paket', 'paket', false, 52428800)          -- 50 MB per berkas
on conflict (id) do update set public = false;

create or replace function public._petugas_aktif()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.petugas where id = auth.uid() and status = 'aktif');
$$;
revoke all on function public._petugas_aktif() from public, anon;
grant execute on function public._petugas_aktif() to authenticated;
