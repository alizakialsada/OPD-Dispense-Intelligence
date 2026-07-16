# Dispense Intelligence v2.01.1 — Dynamic Team Profiles

Fixes:
- Team cards are loaded automatically from Supabase `profiles`.
- Any new active account appears in Team without editing the code.
- Work is matched using the real profile username, with display-name fallback for older records.
- Rabab and Hassan activity is counted under their own accounts.
- Others remains separate from Dispensed.

One-time Supabase step:
Run `supabase-setup/09-team-profiles.sql`.

Keep the existing live `supabase-config.js` when deploying.
