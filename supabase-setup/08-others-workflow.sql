alter table public.dispense_workflow
  add column if not exists reason text,
  add column if not exists note text;

create index if not exists dispense_workflow_status_date_idx
on public.dispense_workflow(work_date,status);
