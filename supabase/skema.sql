-- =====================================================================
--  CKG Robot - login online (Supabase)
--
--  Tempel SELURUH isi berkas ini di Supabase > SQL Editor > New query,
--  lalu tekan Run. Aman dijalankan ulang (mis. sesudah ada pembaruan).
--
--  Yang disimpan di sini HANYA data petugas (nama, email, puskesmas, no HP)
--  dan komputer yang dipakainya. Data peserta CKG tidak pernah lewat sini.
--
--  Akun & kata sandi diurus Supabase Auth (auth.users). Tabel di bawah
--  menambahkan: status persetujuan, peran admin, dan batas komputer.
--
--  Semua tabel DIKUNCI (RLS menyala, tanpa policy): tidak ada yang bisa
--  membaca/mengubahnya langsung lewat REST. Satu-satunya pintu adalah
--  fungsi-fungsi di bawah, yang masing-masing memeriksa siapa pemanggilnya.
--  PENTING: bila berkas ini dijalankan ULANG, jalankan ulang juga
--  tambahan-pembaruan.sql sesudahnya - berkas itu memperbarui
--  periksa_izin/profil_saya yang ditimpa di sini.
-- =====================================================================

-- --------------------------------------------------------------- tabel
create table if not exists public.petugas (
  id              uuid primary key references auth.users(id) on delete cascade,
  email           text not null default '',
  nama            text not null default '',
  puskesmas       text not null default '',
  no_hp           text not null default '',
  peran           text not null default 'petugas' check (peran in ('petugas', 'admin')),
  status          text not null default 'menunggu' check (status in ('menunggu', 'aktif', 'nonaktif')),
  maks_perangkat  int,                       -- kosong = ikut pengaturan umum
  dibuat          timestamptz not null default now(),
  diubah          timestamptz not null default now(),
  terakhir_masuk  timestamptz
);

create table if not exists public.perangkat (
  id              bigint generated always as identity primary key,
  petugas_id      uuid not null references public.petugas(id) on delete cascade,
  kode            text not null,             -- sidik komputer (hash), bukan data pribadi
  nama_komputer   text not null default '',
  versi           text not null default '',
  pertama         timestamptz not null default now(),
  terakhir        timestamptz not null default now(),
  unique (petugas_id, kode)
);

create table if not exists public.pengaturan (
  id              int primary key default 1 check (id = 1),
  versi_minimal   text not null default '',  -- mis. 2026.10.07; kosong = semua versi boleh
  maks_perangkat  int  not null default 2,   -- 0 = tanpa batas
  pengumuman      text not null default ''   -- tampil di aplikasi semua petugas
);
insert into public.pengaturan (id) values (1) on conflict (id) do nothing;

alter table public.petugas    enable row level security;
alter table public.perangkat  enable row level security;
alter table public.pengaturan enable row level security;


-- ------------------------------------------- akun baru -> baris petugas
-- Data tambahan (nama, puskesmas, no HP) dikirim aplikasi saat mendaftar.
-- Status awal SELALU 'menunggu' - tidak bisa dipilih sendiri oleh pendaftar.
create or replace function public._petugas_baru()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.petugas (id, email, nama, puskesmas, no_hp)
  values (new.id,
          coalesce(new.email, ''),
          left(coalesce(new.raw_user_meta_data ->> 'nama', ''), 100),
          left(coalesce(new.raw_user_meta_data ->> 'puskesmas', ''), 100),
          left(coalesce(new.raw_user_meta_data ->> 'no_hp', ''), 30))
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists petugas_baru on auth.users;
create trigger petugas_baru after insert on auth.users
  for each row execute function public._petugas_baru();

-- Akun yang sudah ada SEBELUM skrip ini dijalankan ikut didaftarkan.
insert into public.petugas (id, email, nama)
select u.id, coalesce(u.email, ''), left(coalesce(u.raw_user_meta_data ->> 'nama', ''), 100)
from auth.users u
on conflict (id) do nothing;


-- ------------------------------------------------------------ pembantu
create or replace function public._admin()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.petugas
                 where id = auth.uid() and peran = 'admin' and status = 'aktif');
$$;

create or replace function public._gagal(alasan text, pesan text)
returns jsonb language sql immutable as $$
  select jsonb_build_object('ok', false, 'alasan', alasan, 'pesan', pesan);
$$;


-- ------------------------------------------------- PINTU UTAMA aplikasi
-- Dipanggil aplikasi setiap kali masuk dan setiap kali memulai pekerjaan.
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
      'CKG Robot versi %s sudah tidak dipakai. Unduh versi %s atau yang lebih baru.',
      coalesce(nullif(p_versi, ''), '?'), s.versi_minimal));
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
                            'puskesmas', p.puskesmas, 'pengumuman', s.pengumuman);
end $$;


-- ------------------------------------------------------- fungsi ADMIN
create or replace function public.admin_daftar()
returns jsonb language plpgsql security definer set search_path = public as $$
begin
  if not public._admin() then
    return public._gagal('bukan_admin', 'Hanya admin.');
  end if;
  return jsonb_build_object(
    'ok', true,
    'pengaturan', (select to_jsonb(s) - 'id' from public.pengaturan s where id = 1),
    'petugas', coalesce((
      select jsonb_agg(jsonb_build_object(
               'id', p.id, 'email', p.email, 'nama', p.nama, 'puskesmas', p.puskesmas,
               'no_hp', p.no_hp, 'peran', p.peran, 'status', p.status,
               'maks_perangkat', p.maks_perangkat, 'dibuat', p.dibuat,
               'terakhir_masuk', p.terakhir_masuk,
               'perangkat', coalesce((
                  select jsonb_agg(jsonb_build_object(
                           'id', d.id, 'nama_komputer', d.nama_komputer, 'versi', d.versi,
                           'pertama', d.pertama, 'terakhir', d.terakhir) order by d.terakhir desc)
                  from public.perangkat d where d.petugas_id = p.id), '[]'::jsonb))
             order by (p.status = 'menunggu') desc, p.dibuat desc)
      from public.petugas p), '[]'::jsonb));
end $$;

-- Ubah satu petugas. Isian yang dikirim null dibiarkan apa adanya.
create or replace function public.admin_ubah(p_id uuid, p_status text default null, p_peran text default null,
                                             p_nama text default null, p_puskesmas text default null,
                                             p_no_hp text default null, p_maks_perangkat int default null)
returns jsonb language plpgsql security definer set search_path = public as $$
begin
  if not public._admin() then
    return public._gagal('bukan_admin', 'Hanya admin.');
  end if;
  -- Admin tidak bisa mengunci dirinya sendiri keluar.
  if p_id = auth.uid() and (coalesce(p_status, 'aktif') <> 'aktif' or coalesce(p_peran, 'admin') <> 'admin') then
    return public._gagal('diri_sendiri', 'Tidak bisa menonaktifkan atau menurunkan peran akun sendiri.');
  end if;
  if p_status is not null and p_status not in ('menunggu', 'aktif', 'nonaktif') then
    return public._gagal('status_salah', 'Status tidak dikenal.');
  end if;
  if p_peran is not null and p_peran not in ('petugas', 'admin') then
    return public._gagal('peran_salah', 'Peran tidak dikenal.');
  end if;
  update public.petugas set
    status         = coalesce(p_status, status),
    peran          = coalesce(p_peran, peran),
    nama           = coalesce(left(p_nama, 100), nama),
    puskesmas      = coalesce(left(p_puskesmas, 100), puskesmas),
    no_hp          = coalesce(left(p_no_hp, 30), no_hp),
    -- -1 = kembalikan ke pengaturan umum
    maks_perangkat = case when p_maks_perangkat is null then maks_perangkat
                          when p_maks_perangkat < 0 then null else p_maks_perangkat end,
    diubah         = now()
  where id = p_id;
  if not found then
    return public._gagal('tidak_ada', 'Petugas tidak ditemukan.');
  end if;
  return jsonb_build_object('ok', true);
end $$;

-- Lepas satu komputer dari akun (mis. laptop diganti). Slotnya kosong lagi.
create or replace function public.admin_lepas_perangkat(p_id bigint)
returns jsonb language plpgsql security definer set search_path = public as $$
begin
  if not public._admin() then
    return public._gagal('bukan_admin', 'Hanya admin.');
  end if;
  delete from public.perangkat where id = p_id;
  return jsonb_build_object('ok', true);
end $$;

-- Ganti kata sandi petugas yang lupa. Tanpa email: pengiriman email bawaan
-- Supabase hanya sampai ke anggota tim proyek, bukan ke petugas.
create or replace function public.admin_ganti_sandi(p_id uuid, p_sandi text)
returns jsonb language plpgsql security definer set search_path = public, extensions as $$
begin
  if not public._admin() then
    return public._gagal('bukan_admin', 'Hanya admin.');
  end if;
  if length(coalesce(p_sandi, '')) < 8 then
    return public._gagal('sandi_pendek', 'Kata sandi minimal 8 karakter.');
  end if;
  update auth.users set encrypted_password = extensions.crypt(p_sandi, extensions.gen_salt('bf')),
                        updated_at = now()
   where id = p_id;
  if not found then
    return public._gagal('tidak_ada', 'Petugas tidak ditemukan.');
  end if;
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.admin_pengaturan(p_versi_minimal text default null,
                                                   p_maks_perangkat int default null,
                                                   p_pengumuman text default null)
returns jsonb language plpgsql security definer set search_path = public as $$
begin
  if not public._admin() then
    return public._gagal('bukan_admin', 'Hanya admin.');
  end if;
  update public.pengaturan set
    versi_minimal  = coalesce(left(p_versi_minimal, 20), versi_minimal),
    maks_perangkat = coalesce(greatest(p_maks_perangkat, 0), maks_perangkat),
    pengumuman     = coalesce(left(p_pengumuman, 500), pengumuman)
  where id = 1;
  return jsonb_build_object('ok', true);
end $$;


-- ----------------------------------------------------------- hak akses
-- Fungsi bawaan Supabase terbuka untuk anon secara default; dikunci di sini.
revoke all on function public._admin() from public, anon;
revoke all on function public._gagal(text, text) from public, anon;
revoke all on function public.periksa_izin(text, text, text) from public, anon;
revoke all on function public.admin_daftar() from public, anon;
revoke all on function public.admin_ubah(uuid, text, text, text, text, text, int) from public, anon;
revoke all on function public.admin_lepas_perangkat(bigint) from public, anon;
revoke all on function public.admin_ganti_sandi(uuid, text) from public, anon;
revoke all on function public.admin_pengaturan(text, int, text) from public, anon;

grant execute on function public._admin() to authenticated;
grant execute on function public._gagal(text, text) to authenticated;
grant execute on function public.periksa_izin(text, text, text) to authenticated;
grant execute on function public.admin_daftar() to authenticated;
grant execute on function public.admin_ubah(uuid, text, text, text, text, text, int) to authenticated;
grant execute on function public.admin_lepas_perangkat(bigint) to authenticated;
grant execute on function public.admin_ganti_sandi(uuid, text) to authenticated;
grant execute on function public.admin_pengaturan(text, int, text) to authenticated;


-- =====================================================================
--  ADMIN PERTAMA - jalankan SEKALI, terpisah, SETELAH kamu mendaftar
--  lewat aplikasi (ganti emailnya):
--
--    update public.petugas set peran = 'admin', status = 'aktif'
--     where email = 'emailmu@contoh.com';
--
--  Sesudah itu semua pengelolaan dilakukan dari halaman "Kelola Petugas"
--  di aplikasi.
-- =====================================================================
