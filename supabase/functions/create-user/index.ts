import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization, x-client-info, apikey, content-type"};
serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const url = Deno.env.get("SUPABASE_URL")!;
    const anon = Deno.env.get("SUPABASE_ANON_KEY")!;
    const service = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const authHeader = req.headers.get("Authorization") || "";
    const caller = createClient(url, anon, { global: { headers: { Authorization: authHeader } } });
    const { data: { user } } = await caller.auth.getUser();
    if (!user) throw new Error("Not authenticated");
    const admin = createClient(url, service);
    const { data: profile } = await admin.from("profiles").select("role,is_active").eq("id", user.id).single();
    if (profile?.role !== "admin" || profile?.is_active === false) throw new Error("Administrator access required");
    const body = await req.json();
    const username = String(body.username || "").trim().toLowerCase();
    const role = String(body.role || "pharmacist").trim().toLowerCase();
    if (!username || !body.password || String(body.password).length < 8) throw new Error("Invalid account details");
    if (!["pharmacist","supervisor","admin"].includes(role)) throw new Error("Invalid role");
    const email = `${username}@dispense.local`;
    const { data, error } = await admin.auth.admin.createUser({ email, password: body.password, email_confirm: true });
    if (error) throw error;
    const { error: profileError } = await admin.from("profiles").upsert({
      id: data.user.id, username, full_name: body.full_name, display_name: body.display_name, role, is_active: true
    });
    if (profileError) { await admin.auth.admin.deleteUser(data.user.id); throw profileError; }
    return new Response(JSON.stringify({ ok: true }), { headers: { ...cors, "Content-Type": "application/json" } });
  } catch (e) {
    return new Response(JSON.stringify({ error: e?.message || "Failed" }), { status: 400, headers: { ...cors, "Content-Type": "application/json" } });
  }
});
