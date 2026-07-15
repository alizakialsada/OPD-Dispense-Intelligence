
create table if not exists public.system_settings (
  setting_key text primary key,
  setting_value text not null,
  updated_by uuid references auth.users(id),
  updated_at timestamptz not null default now()
);

alter table public.system_settings enable row level security;

drop policy if exists "active users read settings" on public.system_settings;
create policy "active users read settings"
on public.system_settings for select
to authenticated
using (
  exists(select 1 from public.profiles p where p.id=auth.uid() and p.is_active=true)
);

drop policy if exists "admins insert settings" on public.system_settings;
create policy "admins insert settings"
on public.system_settings for insert
to authenticated
with check (public.is_admin());

drop policy if exists "admins update settings" on public.system_settings;
create policy "admins update settings"
on public.system_settings for update
to authenticated
using (public.is_admin())
with check (public.is_admin());

insert into public.system_settings(setting_key,setting_value)
values('dispensing_interval_days','25')
on conflict(setting_key) do nothing;

do $$
begin
  alter publication supabase_realtime add table public.system_settings;
exception
  when duplicate_object then null;
end $$;
