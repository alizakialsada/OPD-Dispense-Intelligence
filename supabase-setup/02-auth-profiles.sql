
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text unique not null,
  full_name text not null,
  display_name text not null,
  role text not null default 'pharmacist'
    check (role in ('pharmacist','supervisor','admin')),
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles(id,username,full_name,display_name,role)
  values(
    new.id,
    coalesce(new.raw_user_meta_data->>'username',split_part(new.email,'@',1)),
    coalesce(new.raw_user_meta_data->>'full_name',split_part(new.email,'@',1)),
    coalesce(new.raw_user_meta_data->>'display_name',split_part(new.email,'@',1)),
    coalesce(new.raw_user_meta_data->>'role','pharmacist')
  );
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();

create or replace function public.is_admin()
returns boolean
language sql stable security definer set search_path=public
as $$
  select exists(select 1 from public.profiles where id=auth.uid() and role='admin' and is_active=true);
$$;

drop policy if exists "users read own profile" on public.profiles;
create policy "users read own profile" on public.profiles
for select to authenticated using (id=auth.uid() or public.is_admin());

drop policy if exists "admins update profiles" on public.profiles;
create policy "admins update profiles" on public.profiles
for update to authenticated using (public.is_admin()) with check (public.is_admin());

-- Tighten workflow access to authenticated active users.
drop policy if exists "pilot read" on public.dispense_workflow;
drop policy if exists "pilot insert" on public.dispense_workflow;
drop policy if exists "pilot update" on public.dispense_workflow;

create policy "active users read workflow" on public.dispense_workflow
for select to authenticated
using (exists(select 1 from public.profiles p where p.id=auth.uid() and p.is_active=true));

create policy "active users insert workflow" on public.dispense_workflow
for insert to authenticated
with check (exists(select 1 from public.profiles p where p.id=auth.uid() and p.is_active=true));

create policy "active users update workflow" on public.dispense_workflow
for update to authenticated
using (exists(select 1 from public.profiles p where p.id=auth.uid() and p.is_active=true))
with check (exists(select 1 from public.profiles p where p.id=auth.uid() and p.is_active=true));
