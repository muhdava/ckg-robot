-- =====================================================================
--  CKG Robot - TAMBAHAN: admin mengubah EMAIL akun petugas
--
--  Jalankan SEKALI di Supabase > SQL Editor, SETELAH skema.sql.
--  Aman dijalankan ulang.
--
--  Nama, puskesmas, dan no. HP sudah bisa diubah lewat admin_ubah
--  (skema.sql). Email berbeda: email adalah nama masuk akun, disimpan di
--  auth.users - jadi perlu fungsi sendiri, seperti admin_ganti_sandi.
--  Email baru langsung berlaku tanpa konfirmasi (pengiriman email bawaan
--  Supabase memang tidak dipakai). Petugas masuk dengan email baru;
--  kata sandinya tetap.
-- =====================================================================

create or replace function public.admin_ganti_email(p_id uuid, p_email text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  e text := lower(trim(coalesce(p_email, '')));
begin
  if not public._admin() then
    return public._gagal('bukan_admin', 'Hanya admin.');
  end if;
  if e !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' or length(e) > 254 then
    return public._gagal('email_salah', 'Format email tidak sah.');
  end if;
  if exists (select 1 from auth.users where lower(email) = e and id <> p_id) then
    return public._gagal('email_dipakai', 'Email ini sudah dipakai akun lain.');
  end if;

  update auth.users
     set email = e,
         email_confirmed_at = coalesce(email_confirmed_at, now()),
         updated_at = now()
   where id = p_id;
  if not found then
    return public._gagal('tidak_ada', 'Petugas tidak ditemukan.');
  end if;
  -- Data identitas masuk-dengan-email ikut disamakan (kolom email-nya
  -- diturunkan dari identity_data).
  update auth.identities
     set identity_data = identity_data || jsonb_build_object('email', e),
         updated_at = now()
   where user_id = p_id and provider = 'email';
  update public.petugas set email = e, diubah = now() where id = p_id;
  return jsonb_build_object('ok', true);
end $$;

revoke all on function public.admin_ganti_email(uuid, text) from public, anon;
grant execute on function public.admin_ganti_email(uuid, text) to authenticated;
