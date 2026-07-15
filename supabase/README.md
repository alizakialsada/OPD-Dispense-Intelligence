# Dispense Intelligence Production v1.0.3 — Shared Dispensing Interval

Fixed:
- Admin interval is now stored centrally in Supabase.
- Every employee device receives the new interval immediately.
- Queue, Overview, Patient Registry, Smart Calendar, and Drug Demand refresh automatically.
- Supported operational intervals: 15, 20, 25, and 30 days.

One-time setup:
Run `supabase-setup/06-system-settings.sql` in Supabase SQL Editor.

Deployment:
Keep the current live `supabase-config.js`; this package does not include it.
