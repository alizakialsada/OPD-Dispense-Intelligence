-- Additive update only: keeps all users, profiles, workflow and audit data.
insert into public.system_settings (setting_key, setting_value, updated_at)
values ('dispensing_interval_days', '20', now())
on conflict (setting_key) do update
set setting_value = excluded.setting_value, updated_at = excluded.updated_at;
