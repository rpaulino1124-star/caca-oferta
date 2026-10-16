import {NextResponse} from "next/server";
import {timingSafeEqual} from "node:crypto";
export const runtime="nodejs";
function verified(value,secret){const a=Buffer.from(String(value||"")),b=Buffer.from(String(secret||""));return a.length>0&&a.length===b.length&&timingSafeEqual(a,b);}
const escape=s=>String(s||"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
export async function POST(req){
 if(!process.env.ADMIN_API_KEY||!verified(req.headers.get("x-ofertiva-admin"),process.env.ADMIN_API_KEY))return NextResponse.json({error:"Esta operação exige ADMIN_API_KEY no servidor e autenticação no cabeçalho."},{status:401});
 try{
  const form=await req.formData(),name=String(form.get("title")||"").trim().slice(0,125);
  const price=String(form.get("price")||"").trim().slice(0,40);
  const url=new URL(String(form.get("link")||""));
  if(!name||url.protocol!=="https:"||!["shopee.com.br","s.shopee.com.br","shope.ee"].includes(url.hostname))return NextResponse.json({error:"Nome e link Shopee válidos obrigatórios"},{status:400});
  const token=process.env.TELEGRAM_BOT_TOKEN,chat=process.env.TELEGRAM_CHANNEL;
  if(!token||!chat)return NextResponse.json({error:"Telegram não configurado"},{status:503});
  const caption="🛍️ <b>"+escape(name)+"</b>\n💰 "+escape(price)+"\n🔗 <a href=\""+escape(url.href)+"\">Conferir na Shopee</a>\n\nPublicidade / link de afiliado. Preços sujeitos a alteração.";
  const r=await fetch("https://api.telegram.org/bot"+token+"/sendMessage",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({chat_id:chat,text:caption,parse_mode:"HTML"})});
  if(!r.ok||(await r.json()).ok!==true)return NextResponse.json({error:"Telegram recusou publicação"},{status:502});
  return NextResponse.json({ok:true});
 }catch{return NextResponse.json({error:"Requisição inválida"},{status:400});}
}