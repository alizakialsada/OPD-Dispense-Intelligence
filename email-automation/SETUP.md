# Gmail automatic update setup

1. Create a Gmail label named `Dispense Update` and apply it to the Medica Cloud messages.
2. Open Google Apps Script and paste `Code.gs`.
3. Fill `githubOwner`, `githubRepo`, and optionally sender/subject filters.
4. Add a Script Property named `GITHUB_TOKEN` containing a fine-grained GitHub token with **Contents: Read and write** for this repository only.
5. Run `importLatestMedicaAttachment` once and approve access.
6. Create a time-driven trigger (for example, hourly).

The script replaces only `incoming/medica-latest.xlsx`. GitHub Actions then rebuilds the platform data. Supabase workflow/history is not deleted.
