"""
CSSDeals Discord Bot - Versão Final (requests + BeautifulSoup)
==============================================================
Leve, sem Playwright, funciona em qualquer servidor gratuito.

SETUP LOCAL:
  python -m pip install requests beautifulsoup4 discord.py python-dotenv
  python bot.py

DEPLOY RAILWAY:
  1. Sobe essa pasta no GitHub
  2. Conecta no Railway.app
  3. Adiciona as variáveis de ambiente DISCORD_BOT_TOKEN e CHANNEL_ID
"""

import os, json, time, hashlib, asyncio, requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import discord

load_dotenv()

# ─────────────────────────────────────────────
BOT_TOKEN      = os.getenv("DISCORD_BOT_TOKEN", "")
CHANNEL_ID     = int(os.getenv("CHANNEL_ID", "0"))
CHECK_INTERVAL = 90
SEEN_FILE      = "seen_items.json"
CSSDEALS_URL   = "https://cssdeals.com/"
HEADERS        = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
# ─────────────────────────────────────────────

intents = discord.Intents.default()
client  = discord.Client(intents=intents)

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def item_id(item: dict) -> str:
    key = item.get("link", "") or item.get("title", "")
    return hashlib.md5(key.encode()).hexdigest()

def scrape_items() -> list:
    items = []
    try:
        r = requests.get(CSSDEALS_URL, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Salva HTML pra debug na primeira vez
        if not os.path.exists("debug_page.html"):
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(r.text)
            print("  [DEBUG] HTML salvo em debug_page.html")

        # Tenta seletores comuns
        selectors = [
            "div.product-item", "div.product-card", "div.product",
            "li.product", "article.product", "article",
            "[class*='product-item']", "[class*='product-card']",
            "[class*='product_item']", "[class*='deal']",
        ]

        cards = []
        used  = None
        for sel in selectors:
            found = soup.select(sel)
            if len(found) >= 3:
                cards = found
                used  = sel
                break

        print(f"  [SCRAPER] Seletor: '{used}' — {len(cards)} cards")

        for card in cards:
            try:
                # Título
                title_el = (
                    card.select_one("h1,h2,h3,h4,h5") or
                    card.select_one("[class*='title'],[class*='name'],[class*='product-name']")
                )
                title = title_el.get_text(strip=True) if title_el else ""

                # Link
                a_el = card.select_one("a")
                link = a_el["href"] if a_el and a_el.get("href") else ""
                if link and not link.startswith("http"):
                    link = CSSDEALS_URL.rstrip("/") + "/" + link.lstrip("/")

                # Preço
                price_el = card.select_one(
                    ".price,.amount,ins,[class*='price'],[class*='amount']"
                )
                price = price_el.get_text(strip=True).replace("\n", " ") if price_el else "Ver no site"

                # Imagem
                img_el = card.select_one("img")
                image  = None
                if img_el:
                    image = (img_el.get("src") or img_el.get("data-src")
                             or img_el.get("data-lazy-src") or img_el.get("data-original"))
                if image:
                    image = image.split(" ")[0]
                    if image.startswith("//"):
                        image = "https:" + image
                    if not image.startswith("http"):
                        image = None

                if title and len(title) > 2 and link:
                    items.append({"title": title, "price": price, "link": link, "image": image})
            except:
                continue

        # Fallback: links com imagem
        if not items:
            print("  [SCRAPER] Nenhum card encontrado, tentando fallback...")
            for a in soup.select("a"):
                img = a.select_one("img")
                if not img:
                    continue
                href = a.get("href", "")
                if not href or href in ("#", "/"):
                    continue
                alt = img.get("alt", "").strip() or a.get_text(strip=True)
                if len(alt) < 4:
                    continue
                src = img.get("src") or img.get("data-src")
                if src and src.startswith("//"):
                    src = "https:" + src
                if not href.startswith("http"):
                    href = CSSDEALS_URL.rstrip("/") + "/" + href.lstrip("/")
                items.append({"title": alt, "price": "Ver no site", "link": href, "image": src})
            print(f"  [SCRAPER] Fallback: {len(items)} itens")

    except Exception as e:
        print(f"  [ERRO SCRAPER] {e}")

    return items

async def post_item(channel, item: dict):
    safe_title = (item.get("title") or "Nova Oferta")[:250]
    safe_link  = item.get("link", CSSDEALS_URL)
    safe_price = (item.get("price") or "Ver no site")[:100]
    if not safe_link.startswith("http"):
        safe_link = CSSDEALS_URL

    embed = discord.Embed(
        title=f"🔥 Novo no CSSDeals!\n{safe_title}",
        url=safe_link,
        color=0xFF6B00,
    )
    embed.add_field(name="💰 Preço",   value=safe_price,                              inline=True)
    embed.add_field(name="🛒 Comprar", value=f"[Clique aqui]({safe_link})",            inline=True)
    if item.get("image") and str(item["image"]).startswith("http"):
        embed.set_image(url=item["image"])
    embed.set_footer(text=f"CSSDeals • {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    embed.timestamp = datetime.now(timezone.utc)
    await channel.send(embed=embed)

async def monitor_loop():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    if not channel:
        print(f"❌ Canal {CHANNEL_ID} não encontrado! Verifique o ID e as permissões.")
        return

    print(f"✅ Canal encontrado: #{channel.name}")
    seen      = load_seen()
    first_run = not bool(seen)

    while not client.is_closed():
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checando CSSDeals...")
        try:
            loop  = asyncio.get_event_loop()
            items = await loop.run_in_executor(None, scrape_items)
            print(f"  → {len(items)} itens encontrados")

            new_found = 0
            for item in items:
                iid = item_id(item)
                if iid not in seen:
                    seen.add(iid)
                    new_found += 1
                    if not first_run:
                        await post_item(channel, item)
                        print(f"  ✔ Postado: {item['title'][:60]}")
                        await asyncio.sleep(2)

            save_seen(seen)

            if first_run:
                print(f"  → Primeira execução: {len(seen)} itens salvos (sem postar).")
                first_run = False
            else:
                print(f"  → {new_found} novos itens postados.")

        except Exception as e:
            print(f"  [ERRO] {e}")

        print(f"  Próxima checagem em {CHECK_INTERVAL}s...")
        await asyncio.sleep(CHECK_INTERVAL)

@client.event
async def on_ready():
    print(f"🚀 Bot conectado como: {client.user} (ID: {client.user.id})")
    client.loop.create_task(monitor_loop())

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("❌ DISCORD_BOT_TOKEN não encontrado no .env!")
    elif not CHANNEL_ID:
        print("❌ CHANNEL_ID não encontrado no .env!")
    else:
        client.run(BOT_TOKEN)
