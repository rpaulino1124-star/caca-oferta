#!/usr/bin/env python3
"""Ofertiva AI: descoberta autorizada da Shopee, análise, vídeo e Telegram.

Sem credenciais, não simula publicação nem comissão. Nenhuma operação na Shopee Vídeo.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
API = "https://open-api.affiliate.shopee.com.br/graphql"
POSTED = ROOT / "data" / "posted.json"
PRODUCTS = ROOT / "data" / "products.json"
USER_AGENT = "OfertivaAI/1.0 (affiliate automation, authorized API)"
IMAGE_HOSTS = ("susercontent.com", "shopee.com.br", "shopee.com", "shopee.sg")
LINK_HOSTS = ("shopee.com.br", "s.shopee.com.br", "shope.ee", "shopee.com")


def host_is(host, suffixes):
    host = (host or "").lower().rstrip(".")
    return any(host == x or host.endswith("." + x) for x in suffixes)


def allowed_url(value, suffixes):
    try:
        u = urlparse(str(value or "").strip())
        return u.scheme == "https" and not u.username and not u.password and host_is(u.hostname, suffixes)
    except ValueError:
        return False


def score(p):
    """Heurística transparente: classificação, NÃO previsão de vendas."""
    rating = max(0, min(5, float(p.get("rating") or 0)))
    sales = max(0, float(p.get("sales") or 0))
    rate = max(0, min(100, float(p.get("commission_pct") or 0)))
    price = max(0, float(p.get("price") or 0))
    points = min(30, rating * 6) + min(25, sales / 20) + min(30, rate * 2)
    points += min(15, price * rate / 100 / 2)
    return round(points, 1)


def shopee_graphql(query):
    app_id = os.getenv("SHOPEE_APP_ID", "").strip()
    secret = os.getenv("SHOPEE_APP_SECRET", "").strip()
    if not app_id or not secret:
        raise RuntimeError("SHOPEE_APP_ID/SHOPEE_APP_SECRET ausentes")
    payload = json.dumps({"query": query}, ensure_ascii=False, separators=(",", ":"))
    stamp = str(int(time.time()))
    sign = hashlib.sha256((app_id + stamp + payload + secret).encode()).hexdigest()
    auth = "SHA256 Credential=" + app_id + ", Timestamp=" + stamp + ", Signature=" + sign
    r = requests.post(API, data=payload.encode(), headers={
        "Authorization": auth, "Content-Type": "application/json", "User-Agent": USER_AGENT
    }, timeout=30)
    r.raise_for_status()
    obj = r.json()
    if obj.get("errors"):
        raise RuntimeError("A API Shopee retornou erro: " + json.dumps(obj["errors"], ensure_ascii=False)[:500])
    return obj.get("data") or {}


def discover():
    if not os.getenv("SHOPEE_APP_ID") or not os.getenv("SHOPEE_APP_SECRET"):
        print("Shopee API ainda não configurada; usando apenas produtos autorizados no JSON.")
        return []
    query = """{ productOfferV2(listType: 2, sortType: 2, page: 1, limit: 30) {
      nodes { itemId productName productLink offerLink imageUrl priceMin
        sales ratingStar commissionRate shopId shopName }
    } }"""
    nodes = (shopee_graphql(query).get("productOfferV2") or {}).get("nodes") or []
    result = []
    for n in nodes:
        try:
            rate = float(n.get("commissionRate") or 0) * 100
            p = {
                "id": str(n.get("shopId") or "") + "-" + str(n.get("itemId") or ""),
                "name": n.get("productName") or "",
                "price": float(n.get("priceMin") or 0),
                "rating": float(n.get("ratingStar") or 0),
                "sales": float(n.get("sales") or 0),
                "commission_pct": rate,
                "affiliate_url": n.get("offerLink") or "",
                "product_url": n.get("productLink") or "",
                "images": [n["imageUrl"]] if n.get("imageUrl") else []
            }
            if p["name"] and allowed_url(p["affiliate_url"], LINK_HOSTS) and p["rating"] >= 4.3 and p["sales"] >= 100:
                result.append(p)
        except (ValueError, TypeError, KeyError):
            continue
    return result


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def validate_product(p):
    p = dict(p)
    p["name"] = re.sub(r"\s+", " ", str(p.get("name") or "")).strip()[:130]
    p["affiliate_url"] = str(p.get("affiliate_url") or "").strip()
    p["images"] = p.get("images") or []
    if isinstance(p["images"], str):
        p["images"] = [v.strip() for v in p["images"].replace("\n", ",").split(",") if v.strip()]
    p["images"] = [u for u in p["images"][:5] if allowed_url(u, IMAGE_HOSTS)]
    if not p["name"] or not allowed_url(p["affiliate_url"], LINK_HOSTS):
        raise ValueError("Produto inválido: nome ou link de afiliado Shopee ausente")
    if not p["images"]:
        raise ValueError("Faltam imagens em HTTPS do CDN Shopee/susercontent, autorizadas para promoção")
    p["price"] = max(0, float(p.get("price") or 0))
    p["rating"] = max(0, min(5, float(p.get("rating") or 0)))
    p["sales"] = max(0, float(p.get("sales") or 0))
    p["commission_pct"] = max(0, min(100, float(p.get("commission_pct") or 0)))
    p["id"] = str(p.get("id") or hashlib.sha256(p["affiliate_url"].encode()).hexdigest()[:16])[:80]
    return p


def issue_product():
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path:
        raise ValueError("Este modo requer um evento real de issue do GitHub")
    event = json.loads(Path(event_path).read_text(encoding="utf8"))
    body = (event.get("issue") or {}).get("body") or ""
    match = re.search(r"\x60{3}ofertiva\s*([\s\S]*?)\x60{3}", body)
    if not match:
        raise ValueError("Issue sem bloco JSON ofertiva")
    return validate_product(json.loads(match.group(1)))


def choose(mode):
    if mode == "issue":
        return issue_product()
    posted = set(load_json(POSTED, []))
    candidates = load_json(PRODUCTS, [])
    if not isinstance(candidates, list):
        raise ValueError("data/products.json deve conter uma lista")
    candidates += discover()
    ok = []
    for raw in candidates:
        try:
            p = validate_product(raw)
            if p["id"] not in posted:
                ok.append(p)
        except (ValueError, TypeError):
            continue
    ok.sort(key=score, reverse=True)
    return ok[0] if ok else None


def product_script(p):
    price = ("R$ " + format(p["price"], ".2f").replace(".", ",")) if p["price"] else "o preço atualizado"
    fallback = (p["name"] + ". Confira as imagens e as características do anúncio. "
                + "Veja " + price + " e todas as condições no link da oferta. "
                + "Preços, estoque e comissões podem mudar.")
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        print("GEMINI_API_KEY ausente: roteiro factual por modelo fixo, sem alegar IA.")
        return fallback
    prompt = ("Escreva narração comercial curta (até 55 palavras), natural em português do Brasil. "
              "Use SOMENTE os dados abaixo. Não invente características, desconto, avaliações, "
              "urgência, garantia, uso pessoal ou benefícios. Termine convidando a consultar o link. "
              "Dados: " + json.dumps({"nome": p["name"], "preco": p["price"],
                "avaliacao": p["rating"], "vendas": p["sales"]}, ensure_ascii=False))
    try:
        endpoint = ("https://generativelanguage.googleapis.com/v1beta/models/"
                    "gemini-2.5-flash:generateContent")
        r = requests.post(endpoint, params={"key": key}, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 300}
        }, timeout=40)
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return re.sub(r"\s+", " ", text)[:480] or fallback
    except (requests.RequestException, KeyError, IndexError, TypeError) as exc:
        print("IA indisponível; usando roteiro factual:", str(exc)[:160])
        return fallback


def download_image(url):
    if not allowed_url(url, IMAGE_HOSTS):
        raise ValueError("Domínio de imagem não permitido")
    r = requests.get(url, timeout=25, headers={"User-Agent": USER_AGENT}, stream=True, allow_redirects=False)
    r.raise_for_status()
    if not (r.headers.get("Content-Type") or "").lower().startswith("image/"):
        raise ValueError("Resposta não é imagem")
    raw = bytearray()
    for chunk in r.iter_content(65536):
        raw.extend(chunk)
        if len(raw) > 8_000_000:
            raise ValueError("Imagem ultrapassa 8MB")
    from io import BytesIO
    im = Image.open(BytesIO(raw))
    im.verify()
    im = Image.open(BytesIO(raw)).convert("RGB")
    if im.width > 4000 or im.height > 4000:
        im.thumbnail((4000, 4000))
    return im


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + name, size)


def wrap(draw, title, face, max_width, max_lines=4):
    words = title.split()
    lines = []
    line = ""
    for word in words:
        trial = (line + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=face)[2] > max_width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines[:max_lines]


def poster(img, p, idx, path):
    w, h = 720, 1280
    canvas = Image.new("RGB", (w, h), (251, 249, 247))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, w, 120), fill=(255, 87, 34))
    draw.text((40, 35), "OFERTIVA AI", font=font(43, True), fill="white")
    photo = ImageOps.contain(img, (650, 750), Image.Resampling.LANCZOS)
    canvas.paste(photo, ((w - photo.width)//2, 135 + (750-photo.height)//2))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((22, 897, 698, 1248), radius=30, fill=(25, 28, 39))
    lines = wrap(draw, p["name"], font(35, True), 614, 3)
    for i, line in enumerate(lines):
        draw.text((53, 920 + i*48), line, font=font(35, True), fill=(255, 255, 255))
    price = "R$ " + ("%.2f" % p["price"]).replace(".", ",") if p["price"] else "Confira o valor"
    draw.text((53, 1090), price, font=font(48, True), fill=(255, 182, 56))
    hints = ["VEJA OS DETALHES", "CONHEÇA A OFERTA", "PRODUTO NO LINK"]
    draw.text((55, 1188), hints[idx % len(hints)], font=font(25, True), fill=(245, 245, 245))
    canvas.save(path)


def make_video(p, script):
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg não encontrado")
    imgs = []
    for url in p["images"][:3]:
        try:
            imgs.append(download_image(url))
        except (ValueError, requests.RequestException, OSError) as exc:
            print("Falha em imagem:", str(exc)[:180])
    if not imgs:
        raise ValueError("Não foi possível baixar imagens válidas da Shopee")
    workspace = OUT / "tmp"
    workspace.mkdir(exist_ok=True)
    clips = []
    for i in range(3):
        png = workspace / ("card" + str(i) + ".png")
        clip = workspace / ("clip" + str(i) + ".mp4")
        poster(imgs[i % len(imgs)], p, i, png)
        effect = "zoompan=z='min(zoom+0.0009,1.11)':d=100:s=720x1280:fps=25,format=yuv420p"
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1",
                        "-i", str(png), "-vf", effect, "-frames:v", "100",
                        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                        str(clip)], check=True, timeout=180)
        clips.append(clip)
    txt = workspace / "concat.txt"
    txt.write_text("".join("file '" + str(f.resolve()) + "'\n" for f in clips), encoding="utf8")
    base = workspace / "base.mp4"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat",
                    "-safe", "0", "-i", str(txt), "-c", "copy", str(base)], check=True, timeout=120)
    voice = workspace / "voice.mp3"
    try:
        import asyncio
        import edge_tts
        asyncio.run(edge_tts.Communicate(script, "pt-BR-FranciscaNeural").save(str(voice)))
    except Exception as exc:
        print("Narração indisponível, produzindo vídeo sem áudio:", str(exc)[:180])
    target = OUT / ("ofertiva-" + re.sub(r"[^a-zA-Z0-9_-]", "-", p["id"])[:55] + ".mp4")
    if voice.exists() and voice.stat().st_size > 100:
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(base),
                        "-i", str(voice), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                        "-c:a", "aac", "-t", "12", "-movflags", "+faststart",
                        str(target)], check=True, timeout=100)
    else:
        shutil.copy2(base, target)
    return target


def send_telegram(p, video):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    channel = os.getenv("TELEGRAM_CHANNEL", "").strip()
    if not token or not channel:
        print("Telegram não configurado: vídeo disponível somente nos artefatos do GitHub Actions")
        return False
    caption = ("🛍️ " + p["name"][:110] + "\n\n"
               + ("💰 R$ " + ("%.2f" % p["price"]).replace(".", ",") + "\n" if p["price"] else "")
               + "🔗 Confira o produto: " + p["affiliate_url"] + "\n\n"
               + "Publicidade / link de afiliado • Verifique preço e condições na Shopee.")
    with video.open("rb") as f:
        r = requests.post("https://api.telegram.org/bot" + token + "/sendVideo",
            data={"chat_id": channel, "caption": caption[:1024],
                  "supports_streaming": "true"},
            files={"video": (video.name, f, "video/mp4")}, timeout=120)
    r.raise_for_status()
    result = r.json()
    if not result.get("ok"):
        raise RuntimeError("Telegram rejeitou publicação: " + str(result.get("description"))[:250])
    print("Telegram: vídeo publicado no canal configurado.")
    return True


def main():
    mode = "issue" if "--issue" in sys.argv else "scheduled"
    p = choose(mode)
    if not p:
        print("Nenhum produto novo com link/imagem válidos. Nada será divulgado.")
        return
    print("Selecionado:", p["name"], "pontuação heurística:", score(p))
    script = product_script(p)
    video = make_video(p, script)
    record = {**p, "score": score(p), "script": script,
              "video": video.name, "created_at": datetime.now(timezone.utc).isoformat(),
              "status": "gerado; publicação Shopee Vídeo não automatizada"}
    (OUT / "resultado.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8")
    sent = send_telegram(p, video)
    if sent and mode == "scheduled":
        posted = load_json(POSTED, [])
        if p["id"] not in posted:
            posted.append(p["id"])
            POSTED.write_text(json.dumps(posted, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("Finalizado; arquivo:", video.name)


if __name__ == "__main__":
    main()
