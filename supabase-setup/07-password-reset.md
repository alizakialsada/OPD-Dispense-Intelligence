# Password reset

Employees can change their own password from the top bar without extra SQL.

For administrator resets, deploy:

```bash
supabase functions deploy admin-reset-password
```

Keep the service-role key only inside Supabase Edge Function secrets.
