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
