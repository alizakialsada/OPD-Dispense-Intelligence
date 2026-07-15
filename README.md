# Dispense Intelligence — Production v1.0

Fixed:
- Drug Demand now reads a small precomputed file for the selected date.
- Smart Calendar now reads one compact precomputed monthly source.
- No repeated full-data scanning in the browser.
- Automatic Excel updates regenerate all prepared files.

Deployment:
Keep your existing live `supabase-config.js`.
This package intentionally does not include it, so your working Supabase connection is not overwritten.

Current production interval: 25 days.
