-- =====================================================================
--  CKG Robot - TAMBAHAN: rekap pemakaian + penjaga server
--
--  Jalankan SEKALI di Supabase > SQL Editor, SETELAH berkas-berkas
--  sebelumnya. Aman dijalankan ulang.
--
--  1. pemakaian      : JUMLAH peserta per petugas per hari (tuntas, beres di
--                      tempat lain, data salah, gagal). HANYA ANGKA - tidak
--                      ada NIK, nama, atau data peserta apa pun.
--  2. catat_pemakaian: dipanggil aplikasi petugas (akun aktif) tiap menit
--                      selama robot bekerja.
--  3. admin_pemakaian: rekap untuk halaman Kelola Petugas, termasuk tanda
--                      bila kegagalan melonjak (tanda portal berubah).
--  4. ping           : dipanggil penjaga harian (GitHub Actions) supaya
--                      proyek gratis tidak tertidur karena sepi.
-- =====================================================================

create table if not exists public.pemakaian (
  petugas_id   uuid not null references public.petugas(id) on delete cascade,
  tanggal      date not null,
  tuntas       int  not null default 0,
  beres_lain   int  not null default 0,     -- sudah dilayani / diperiksa di tempat lain
  data_salah   int  not null default 0,     -- tidak_valid, tidak_ditemukan, sekolah/kelas berbeda
  gagal        int  not null default 0,     -- gagal sementara (portal lambat/berubah)
  versi        text not null default '',
  diubah       timestamptz not null default now(),
  primary key (petugas_id, tanggal)
);
alter table public.pemakaian enable row level security;


-- Tambah (atau kurangi - hasil yang diulang bisa pindah dari gagal ke tuntas)
-- hitungan hari itu. Tiap angka dibatasi supaya satu panggilan aneh tidak
-- merusak rekap.
create or replace function public.catat_pemakaian(p_tanggal date, p_tuntas int, p_beres_lain int,
                                                  p_data_salah int, p_gagal int, p_versi text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  u uuid := auth.uid();
  batas constant int := 5000;
begin
  if u is null or not exists (select 1 from public.petugas where id = u and status = 'aktif') then
    return public._gagal('bukan_petugas_aktif', 'Hanya petugas aktif.');
  end if;
  if p_tanggal is null or p_tanggal < current_date - 7 or p_tanggal > current_date + 1 then
    return public._gagal('tanggal_salah', 'Tanggal di luar rentang.');
  end if;
  insert into public.pemakaian as t (petugas_id, tanggal, tuntas, beres_lain, data_salah, gagal, versi)
  values (u, p_tanggal,
          greatest(0, least(batas, coalesce(p_tuntas, 0))),
          greatest(0, least(batas, coalesce(p_beres_lain, 0))),
          greatest(0, least(batas, coalesce(p_data_salah, 0))),
          greatest(0, least(batas, coalesce(p_gagal, 0))),
          left(coalesce(p_versi, ''), 20))
  on conflict (petugas_id, tanggal) do update set
    tuntas     = greatest(0, t.tuntas     + greatest(-batas, least(batas, coalesce(p_tuntas, 0)))),
    beres_lain = greatest(0, t.beres_lain + greatest(-batas, least(batas, coalesce(p_beres_lain, 0)))),
    data_salah = greatest(0, t.data_salah + greatest(-batas, least(batas, coalesce(p_data_salah, 0)))),
    gagal      = greatest(0, t.gagal      + greatest(-batas, least(batas, coalesce(p_gagal, 0)))),
    versi      = left(coalesce(p_versi, t.versi), 20),
    diubah     = now();
  return jsonb_build_object('ok', true);
end $$;


create or replace function public.admin_pemakaian(p_hari int default 14)
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare
  dari date := current_date - greatest(1, least(coalesce(p_hari, 14), 90)) + 1;
begin
  if not public._admin() then
    return public._gagal('bukan_admin', 'Hanya admin.');
  end if;
  return jsonb_build_object(
    'ok', true,
    'dari', dari,
    'per_hari', coalesce((
      select jsonb_agg(jsonb_build_object(
               'tanggal', tanggal, 'tuntas', sum_t, 'beres_lain', sum_b, 'data_salah', sum_d,
               'gagal', sum_g, 'petugas', n) order by tanggal desc)
      from (select tanggal, sum(tuntas) sum_t, sum(beres_lain) sum_b, sum(data_salah) sum_d,
                   sum(gagal) sum_g, count(*) n
            from public.pemakaian where tanggal >= dari group by tanggal) x), '[]'::jsonb),
    'per_petugas', coalesce((
      select jsonb_agg(jsonb_build_object(
               'nama', p.nama, 'email', p.email, 'puskesmas', p.puskesmas,
               'tuntas', x.sum_t, 'beres_lain', x.sum_b, 'data_salah', x.sum_d, 'gagal', x.sum_g,
               'hari_aktif', x.n, 'terakhir', x.akhir, 'versi', x.versi) order by x.sum_t desc)
      from (select petugas_id, sum(tuntas) sum_t, sum(beres_lain) sum_b, sum(data_salah) sum_d,
                   sum(gagal) sum_g, count(*) n, max(tanggal) akhir,
                   (array_agg(versi order by tanggal desc))[1] versi
            from public.pemakaian where tanggal >= dari group by petugas_id) x
      join public.petugas p on p.id = x.petugas_id), '[]'::jsonb));
end $$;


-- Penjaga: cukup menyentuh database. Boleh dipanggil tanpa login, tidak
-- membuka data apa pun.
create or replace function public.ping()
returns jsonb language sql stable as $$
  select jsonb_build_object('ok', true, 'waktu', now());
$$;


revoke all on function public.catat_pemakaian(date, int, int, int, int, text) from public, anon;
revoke all on function public.admin_pemakaian(int) from public, anon;
grant execute on function public.catat_pemakaian(date, int, int, int, int, text) to authenticated;
grant execute on function public.admin_pemakaian(int) to authenticated;
grant execute on function public.ping() to anon, authenticated;
