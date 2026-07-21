import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
Deno.serve(async(req)=>{
 const cors={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization, x-client-info, apikey, content-type"};
 if(req.method==="OPTIONS")return new Response("ok",{headers:cors});
 try{
  const url=Deno.env.get("SUPABASE_URL")!,anon=Deno.env.get("SUPABASE_ANON_KEY")!,service=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const caller=createClient(url,anon,{global:{headers:{Authorization:req.headers.get("Authorization")??""}}});
  const {data:{user}}=await caller.auth.getUser();if(!user)throw new Error("Unauthorized");
  const {data:p}=await caller.from("profiles").select("role,is_active").eq("id",user.id).single();
  if(!p||p.role!=="admin"||!p.is_active)throw new Error("Administrator access required");
  const b=await req.json();if(!b.user_id||String(b.new_password||"").length<8)throw new Error("Invalid request");
  const admin=createClient(url,service);const {error}=await admin.auth.admin.updateUserById(b.user_id,{password:b.new_password});if(error)throw error;
  return new Response(JSON.stringify({success:true}),{headers:{...cors,"Content-Type":"application/json"}});
 }catch(e){return new Response(JSON.stringify({error:e.message}),{status:400,headers:{...cors,"Content-Type":"application/json"}})}
});