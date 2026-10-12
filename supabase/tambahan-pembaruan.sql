-- =====================================================================
--  CKG Robot - TAMBAHAN: pembaruan aplikasi dari dalam aplikasi
--
--  Jalankan SEKALI di Supabase > SQL Editor, SETELAH skema.sql dan
--  tambahan-website.sql. Aman dijalankan ulang.
--
--  Menyimpan paket yang sedang DITERBITKAN (versi, sidik SHA-256, ukuran,
--  catatan perubahan). Aplikasi petugas membandingkannya dengan versinya
--  sendiri; bila lebih baru, muncul tombol "Perbarui sekarang". Sidik
--  SHA-256 memastikan yang dipasang persis paket yang diterbitkan admin -
--  unduhan terputus/rusak ditolak.
-- =====================================================================

alter table public.pengaturan add column if not exists versi_terbaru   text   not null default '';
alter table public.pengaturan add column if not exists sha256_terbaru  text   not null default '';
alter table public.pengaturan add column if not exists ukuran_terbaru  bigint not null default 0;
alter table public.pengaturan add column if not exists catatan_terbaru text   not null default '';
alter table public.pengaturan add column if not exists diterbitkan     timestamptz;


-- Info pembaruan yang ikut di setiap jawaban izin.
create or replace function public._info_pembaruan()
returns jsonb language sql stable security definer set search_path = public as $$
  select jsonb_build_object('versi_terbaru', versi_terbaru, 'sha256_terbaru', sha256_terbaru,
                            'ukuran_terbaru', ukuran_terbaru, 'catatan_terbaru', catatan_terbaru,
                            'diterbitkan', diterbitkan)
  from public.pengaturan where id = 1;
$$;


-- periksa_izin: sama seperti di skema.sql, ditambah info pembaruan - JUGA
-- pada penolakan 'versi_lama', supaya aplikasi lama bisa langsung menawarkan
-- tombol "Perbarui sekarang" alih-alih menyuruh mengunduh ZIP.
create or replace function public.periksa_izin(p_kode text, p_nama_komputer text, p_versi text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  u       uuid := auth.uid();
  p       public.petugas;
  s       public.pengaturan;
  batas   int;
  jumlah  int;
begin
  if u is null then
    return public._gagal('belum_masuk', 'Sesi tidak sah. Silakan masuk lagi.');
  end if;
  select * into p from public.petugas where id = u;
  if not found then
    return public._gagal('akun_tidak_ada', 'Akun tidak terdaftar sebagai petugas. Hubungi admin.');
  end if;
  select * into s from public.pengaturan where id = 1;

  if p.status = 'menunggu' then
    return public._gagal('menunggu', 'Akun belum disetujui admin. Coba lagi setelah admin menyetujuinya.');
  elsif p.status = 'nonaktif' then
    return public._gagal('nonaktif', 'Akun ini dinonaktifkan admin.');
  end if;

  if coalesce(s.versi_minimal, '') <> '' and coalesce(p_versi, '') collate "C" < s.versi_minimal collate "C" then
    return public._gagal('versi_lama', format(
      'CKG Robot versi %s sudah tidak dipakai. Perbarui ke versi %s atau yang lebih baru.',
      coalesce(nullif(p_versi, ''), '?'), s.versi_minimal))
      || jsonb_build_object('nama', p.nama, 'peran', p.peran)
      || public._info_pembaruan();
  end if;

  p_kode := left(coalesce(p_kode, ''), 128);
  if p_kode = '' then
    return public._gagal('perangkat_kosong', 'Komputer ini tidak bisa dikenali.');
  end if;

  if exists (select 1 from public.perangkat where petugas_id = u and kode = p_kode) then
    update public.perangkat
       set terakhir = now(), versi = left(coalesce(p_versi, ''), 20),
           nama_komputer = left(coalesce(p_nama_komputer, ''), 100)
     where petugas_id = u and kode = p_kode;
  else
    batas := coalesce(p.maks_perangkat, s.maks_perangkat);
    select count(*) into jumlah from public.perangkat where petugas_id = u;
    if p.peran <> 'admin' and batas > 0 and jumlah >= batas then
      return public._gagal('perangkat_penuh', format(
        'Akun ini sudah dipakai di %s komputer (batas %s). Minta admin melepas komputer yang lama.',
        jumlah, batas));
    end if;
    insert into public.perangkat (petugas_id, kode, nama_komputer, versi)
    values (u, p_kode, left(coalesce(p_nama_komputer, ''), 100), left(coalesce(p_versi, ''), 20));
  end if;

  update public.petugas set terakhir_masuk = now() where id = u;
  return jsonb_build_object('ok', true, 'nama', p.nama, 'email', p.email, 'peran', p.peran,
                            'puskesmas', p.puskesmas, 'pengumuman', s.pengumuman)
         || public._info_pembaruan();
end $$;


-- profil_saya (website): ditambah versi yang sedang diterbitkan.
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
                            'pengumuman', (select pengumuman from public.pengaturan where id = 1))
         || public._info_pembaruan();
end $$;


-- Admin menerbitkan paket yang BARU SAJA diunggahnya ke bucket 'paket'.
create or replace function public.admin_terbitkan(p_versi text, p_sha256 text, p_ukuran bigint, p_catatan text)
returns jsonb language plpgsql security definer set search_path = public as $$
begin
  if not public._admin() then
    return public._gagal('bukan_admin', 'Hanya admin.');
  end if;
  if coalesce(p_versi, '') !~ '^\d{4}\.\d{2}\.\d{2}(\.\d{4})?$' then
    return public._gagal('versi_salah', 'Format versi tidak dikenal.');
  end if;
  if coalesce(p_sha256, '') !~ '^[0-9a-f]{64}$' then
    return public._gagal('sidik_salah', 'Sidik SHA-256 tidak sah.');
  end if;
  update public.pengaturan set
    versi_terbaru   = p_versi,
    sha256_terbaru  = p_sha256,
    ukuran_terbaru  = greatest(coalesce(p_ukuran, 0), 0),
    catatan_terbaru = left(coalesce(p_catatan, ''), 1000),
    diterbitkan     = now()
  where id = 1;
  return jsonb_build_object('ok', true);
end $$;


revoke all on function public._info_pembaruan() from public, anon;
revoke all on function public.periksa_izin(text, text, text) from public, anon;
revoke all on function public.profil_saya() from public, anon;
revoke all on function public.admin_terbitkan(text, text, bigint, text) from public, anon;
grant execute on function public._info_pembaruan() to authenticated;
grant execute on function public.periksa_izin(text, text, text) to authenticated;
grant execute on function public.profil_saya() to authenticated;
grant execute on function public.admin_terbitkan(text, text, bigint, text) to authenticated;
