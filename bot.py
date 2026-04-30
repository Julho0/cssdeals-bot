import os, json, time, hashlib, asyncio, requests
from datetime import datetime, timezone
from dotenv import load_dotenv
import discord

load_dotenv()

BOT_TOKEN      = os.getenv("DISCORD_BOT_TOKEN", "")
CHANNEL_ID     = int(os.getenv("CHANNEL_ID", "0"))
CHECK_INTERVAL = 90
CSSDEALS_URL   = "https://cssdeals.com"
API_URL        = f"{CSSDEALS_URL}/api/product?fields=1&pageSize=20&page="
HEADERS        = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": f"{CSSDEALS_URL}/",
}

seen_ids      = set()   # IDs já vistos
first_run     = True

intents = discord.Intents.default()
client  = discord.Client(intents=intents)

def parse_item(rec: dict) -> dict:
    sku   = rec["skus"][0] if rec.get("skus") else {}
    image = sku.get("image", "")
    price = sku.get("price", "?")
    title = rec.get("title", "Sem título")
    pid   = str(rec.get("id", ""))

    # Link forçado apenas para a página do CSSDeals
    cssdeals_link = f"{CSSDEALS_URL}/product-detail.html?itemid={pid}"

    platform_map = {1: "Taobao", 2: "Weidian", 3: "1688", 99: "CSSDeals"}
    platform = platform_map.get(rec.get("salePlatform", 0), "Ver site")

    return {
        "id":       pid,
        "title":    title,
        "price":    f"¥{price}",
        "link":     cssdeals_link,   # link do título do embed
        "buy_link": cssdeals_link,   # link do campo "Comprar"
        "image":    image,
        "platform": platform,
    }

def fetch_new_products() -> list:
    """
    Busca páginas até encontrar apenas IDs já conhecidos.
    Na primeira execução, registra tudo sem postar.
    """
    new_items = []
    page = 1
    max_pages = 50  # segurança: nunca passa de 50 páginas por ciclo

    while page <= max_pages:
        try:
            r = requests.get(API_URL + str(page), headers=HEADERS, timeout=15)
            if r.status_code != 200:
                print(f"  [API] Página {page} retornou {r.status_code}, parando.")
                break

            data    = r.json()
            records = data.get("data", {}).get("records", [])
            total   = int(data.get("data", {}).get("total", 0))

            if not records:
                break

            total_pages = (total + 19) // 20
            print(f"  [API] Página {page}/{total_pages}: {len(records)} itens")

            found_known = False
            for rec in records:
                pid = str(rec.get("id", ""))
                if pid in seen_ids:
                    found_known = True
                    # Não para imediatamente — continua o loop da página
                    # mas marca que já achou conhecido
                else:
                    new_items.append(parse_item(rec))

            # Se achou pelo menos um ID conhecido nessa página,
            # todos os próximos também são conhecidos — pode parar
            if found_known and not first_run:
                print(f"  [API] IDs conhecidos encontrados na página {page}, parando busca.")
                break

            if page >= total_pages:
                break

            page += 1
            time.sleep(0.3)

        except Exception as e:
            print(f"  [ERRO API página {page}] {e}")
            break

    return new_items

async def post_item(channel, item: dict):
    embed = discord.Embed(
        title=f"🔥 Novo no CSSDeals!\n{item['title'][:250]}",
        url=item["link"],
        color=0xFF6B00,
    )
    embed.add_field(name="💰 Preço",      value=item["price"],                              inline=True)
    embed.add_field(name="🛍️ Plataforma", value=item["platform"],                           inline=True)
    embed.add_field(name="🛒 Comprar",    value=f"[Clique aqui]({item['buy_link']})",        inline=False)

    if item.get("image") and item["image"].startswith("http"):
        embed.set_image(url=item["image"])

    embed.set_footer(text=f"CSSDeals • {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    embed.timestamp = datetime.now(timezone.utc)
    await channel.send(embed=embed)

async def monitor_loop():
    global seen_ids, first_run
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    if not channel:
        print(f"❌ Canal {CHANNEL_ID} não encontrado!")
        return

    print(f"✅ Canal encontrado: #{channel.name}")

    while not client.is_closed():
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checando CSSDeals...")
        try:
            loop  = asyncio.get_event_loop()
            items = await loop.run_in_executor(None, fetch_new_products)

            if first_run:
                # Registra todos os IDs existentes sem postar
                for item in items:
                    seen_ids.add(item["id"])
                print(f"  → Primeira execução: {len(seen_ids)} itens registrados (sem postar).")
                first_run = False
            else:
                print(f"  → {len(items)} novos itens!")
                for item in reversed(items):  # mais antigo primeiro
                    await post_item(channel, item)
                    print(f"  ✔ Postado: {item['title'][:60]}")
                    seen_ids.add(item["id"])
                    await asyncio.sleep(2)

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
