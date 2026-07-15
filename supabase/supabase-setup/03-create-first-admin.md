# Create the first administrator

The first administrator must be created once from the Supabase Dashboard:

1. Authentication → Users → Add user.
2. Email: `ali@dispense.local`
3. Set a strong password and mark the email as confirmed.
4. After creation, run this SQL using the generated user UUID:

```sql
update public.profiles
set username='ali',
    full_name='Ali Alsada',
    display_name='Ali Alsada',
    role='admin',
    is_active=true
where id='PASTE_USER_UUID_HERE';
```

Then sign in to the platform with:
- Username: `ali`
- Password: the password you created.

Deploy the Edge Function:

```bash
supabase functions deploy create-user
```

The service-role key remains stored only in Supabase function secrets and is never placed in the website.
