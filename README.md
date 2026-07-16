# Dispense Intelligence v2.02 — Live Progress

Added only to the stable v2.01.1 base:
- Live Scheduled, Dispensed, Others, In Progress, Remaining, and Completion.
- Remaining decreases after Dispensed or Others.
- Undo immediately restores the counters.
- Queue summary includes Others and Remaining.
- Realtime Supabase changes refresh all devices automatically.
- No changes to Smart Calendar, Drug Demand, authentication, or database schema.

Deployment: keep the existing live `supabase-config.js`. No new SQL is required.
