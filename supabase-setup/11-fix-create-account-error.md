# Fix “Edge Function returned a non-2xx status code”

The website files alone cannot create Supabase Auth users. Deploy the included function once.

## With Supabase CLI
From the project folder, sign in and link the project, then run:

```bash
supabase functions deploy create-user --no-verify-jwt
```

The function validates that the signed-in caller has an active `admin` profile and accepts only lowercase roles: `admin`, `supervisor`, or `pharmacist`.

Do not place the service-role key in GitHub, `index.html`, or `supabase-config.js`.
