-- Allow authenticated active staff to see active team members in Team Performance.
drop policy if exists "active users read team profiles" on public.profiles;
create policy "active users read team profiles"
on public.profiles for select
to authenticated
using (
  is_active = true
  and exists (
    select 1 from public.profiles me
    where me.id = auth.uid() and me.is_active = true
  )
);
