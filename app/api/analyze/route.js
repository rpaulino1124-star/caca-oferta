import {NextResponse} from "next/server";
import {timingSafeEqual} from "node:crypto";
export const runtime="nodejs";
function matches(a,b){const x=Buffer.from(String(a||"")),y=Buffer.from(String(b||""));return x.length>0&&x.length===y.length&&timingSafeEqual(x,y);}
export async function POST(req){
 try{
  const {product:p}=await req.json();
  if(!p||typeof p.name!=="string"||!p.name.trim()||p.name.length>140)return NextResponse.json({error:"Produto inválido"},{status:400});
  const rating=Number(p.rating)||0,sales=Number(p.sales)||0,rate=Number(p.commission_pct)||0;
  const reason="Avaliação informada: "+rating.toFixed(1)+"/5; vendas informadas: "+sales+"; comissão informada: "+rate+"%. Isto não prevê vendas.";
  const fallback=p.name.slice(0,130)+". Confira as imagens e características do anúncio. Consulte o preço e as condições no link de afiliado.";
  const key=process.env.GEMINI_API_KEY,guard=process.env.ADMIN_API_KEY;
  if(!key||!guard||!matches(req.headers.get("x-ofertiva-admin"),guard))return NextResponse.json({mode:"regras",reason,script:fallback});
  const prompt="Escreva uma narração comercial natural de até 55 palavras em português brasileiro para um vídeo sobre produto. Nunca invente recursos, urgência, desconto, garantia ou experiência pessoal; use SOMENTE fatos: "+JSON.stringify({name:p.name,price:p.price,rating,sales});
  const r=await fetch("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key="+encodeURIComponent(key),{
   method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({contents:[{parts:[{text:prompt}]}],generationConfig:{temperature:0.4,maxOutputTokens:300}}),signal:AbortSignal.timeout(14000)
  });
  if(!r.ok)return NextResponse.json({mode:"regras",reason,script:fallback});
  const data=await r.json();
  const script=(data?.candidates?.[0]?.content?.parts||[]).map(x=>x.text||"").join(" ").slice(0,520)||fallback;
  return NextResponse.json({mode:"ai",reason,script});
 }catch{return NextResponse.json({error:"Falha de análise. Confira os dados informados."},{status:400});}
}