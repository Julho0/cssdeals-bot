import os, asyncio, requests
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

seen_ids       = set()
first_run      = True
last_total     = 0   # último total conhecido de itens

intents = discord.Intents.default()
client  = discord.Client(intents=intents)

def parse_item(rec: dict) -> dict:
    sku   = rec["skus"][0] if rec.get("skus") else {}
    pid   = str(rec.get("id", ""))
    return {
        "id":    pid,
        "title": rec.get("title", "Sem título"),
        "price": f"¥{sku.get('price', '?')}",
        "link":  f"{CSSDEALS_URL}/product-detail.html?itemid={pid}",
        "image": sku.get("image", ""),
    }

def fetch_page(page: int):
    try:
        r = requests.get(API_URL + str(page), headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return [], 0
        data    = r.json().get("data", {})
        total   = int(data.get("total", 0))
        records = data.get("records", [])
        return records, total
    except:
        return [], 0

def fetch_products() -> list:
    """
    Checa as primeiras 50 páginas sempre.
    Se o total de itens aumentou desde a última checagem,
    varre todas as páginas para garantir que não perde nada.
    """
    global last_total

    # Pega total atual
    _, current_total = fetch_page(1)
    total_pages = max(1, (current_total + 19) // 20)

    # Decide quantas páginas varrer
    if last_total > 0 and current_total > last_total:
        pages_to_scan = total_pages  # total aumentou — varre tudo
        print(f"  [API] Total aumentou ({last_total}→{current_total}), varrendo todas as {total_pages} páginas...")
    else:
        pages_to_scan = min(50, total_pages)  # normal — só primeiras 50
        print(f"  [API] Total: {current_total} | Checando {pages_to_scan} páginas...")

    last_total = current_total

    all_items = []
    for page in range(1, pages_to_scan + 1):
        records, _ = fetch_page(page)
        for rec in records:
            all_items.append(parse_item(rec))

    print(f"  [API] {len(all_items)} itens carregados")
    return all_items

async def post_item(channel, item: dict):
    embed = discord.Embed(
        title=item["title"][:256],
        url=item["link"],
        color=0xFF6B00,
    )
    embed.set_author(name="🔥 Novo no CSSDeals!")
    embed.add_field(name="💰 Preço",   value=item["price"],                        inline=True)
    embed.add_field(name="🛒 Comprar", value=f"[Ver no CSSDeals]({item['link']})", inline=True)
    if item.get("image") and item["image"].startswith("http"):
        embed.set_image(url=item["image"])
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
            items = await loop.run_in_executor(None, fetch_products)

            if first_run:
                seen_ids = {i["id"] for i in items}
                print(f"  → Primeira execução: {len(seen_ids)} itens registrados (sem postar).")
                first_run = False
            else:
                new_items = [i for i in items if i["id"] not in seen_ids]
                print(f"  → {len(new_items)} novos itens!")
                for item in new_items:
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