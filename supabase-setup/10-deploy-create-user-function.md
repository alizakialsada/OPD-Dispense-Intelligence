# Enable user creation from the platform

The Admin page already includes **Create Account**. Deploy the included Edge Function once:

```bash
supabase functions deploy create-user --no-verify-jwt
```

Supabase automatically supplies `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` to the function. Do not put the service-role key in `index.html` or `supabase-config.js`.
