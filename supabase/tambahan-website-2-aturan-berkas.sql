-- =====================================================================
--  CKG Robot - TAMBAHAN website, BAGIAN 2: aturan akses bucket 'paket'
--
--  Jalankan SETELAH tambahan-website.sql berhasil.
--  Bila SQL Editor menolak dengan pesan 'must be owner of table objects',
--  buat empat aturan ini lewat Dashboard > Storage > Policies (lihat
--  PANDUAN SUPABASE.md, bagian 9) - isinya sama persis.
-- =====================================================================

drop policy if exists "paket: petugas aktif boleh unduh" on storage.objects;
create policy "paket: petugas aktif boleh unduh" on storage.objects
  for select to authenticated
  using (bucket_id = 'paket' and public._petugas_aktif());

drop policy if exists "paket: admin boleh unggah" on storage.objects;
create policy "paket: admin boleh unggah" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'paket' and public._admin());

drop policy if exists "paket: admin boleh ganti" on storage.objects;
create policy "paket: admin boleh ganti" on storage.objects
  for update to authenticated
  using (bucket_id = 'paket' and public._admin())
  with check (bucket_id = 'paket' and public._admin());

drop policy if exists "paket: admin boleh hapus" on storage.objects;
create policy "paket: admin boleh hapus" on storage.objects
  for delete to authenticated
  using (bucket_id = 'paket' and public._admin());
