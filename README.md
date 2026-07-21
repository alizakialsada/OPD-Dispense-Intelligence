# Dispense Intelligence Platform v2 — Final Trial

Included:
- Live Scheduled / Dispensed / Others / In Progress / Remaining / Completion.
- Personal live achievement strip for the signed-in employee.
- Live timer on every In Progress patient.
- Others reason workflow with Undo for 5 minutes.
- Others is excluded from Dispensed and productivity.
- Supervisor live monitor.
- Team Analytics by Today / Week / Month / Custom and employee.
- Password change and admin password reset support.
- Shared dispensing interval.
- Smart Calendar, Drug Demand, and Excel exports.

One-time database update:
Run `supabase-setup/08-final-trial-others.sql`.

Deployment:
Keep the current live `supabase-config.js`; this package intentionally does not include it.


## v2.1 additive update
- Existing features, users, workflow records, and audit history are preserved.
- Patient cards now show Last Dispense and copyable name, MRN, National ID, mobile, and national address.
- Personal motivational messages appear after completed cases.
- Admin user creation remains available; deploy the included `create-user` Edge Function if it is not already deployed.
- Canonical preparation interval is 20 days. Run `09-set-preparation-interval-20.sql` once.

## v2.2 recurring preparation schedule
- Uses the latest dispense for each MRN + medication.
- First preparation date is latest dispense + the selected preparation interval (default 20 days).
- Following preparation dates repeat every 30 days and stop at the calculated prescription end date.
- A new source Excel rebuilds and replaces future schedules without changing Supabase users or historical workflow records.
