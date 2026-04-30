import os, asyncio, requests
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import discord

load_dotenv()

BOT_TOKEN      = os.getenv("DISCORD_BOT_TOKEN", "")
CHANNEL_ID     = int(os.getenv("CHANNEL_ID", "0"))
CHECK_INTERVAL = 120
CSSDEALS_URL   = "https://cssdeals.com"
API_URL        = f"{CSSDEALS_URL}/api/product?fields=1&pageSize=20&page="
HEADERS        = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": f"{CSSDEALS_URL}/",
}
MAX_WORKERS = 5

seen_ids  = set()
first_run = True

intents = discord.Intents.default()
client  = discord.Client(intents=intents)

def parse_item(rec: dict) -> dict:
    sku   = rec["skus"][0] if rec.get("skus") else {}
    image = sku.get("image", "")
    price = sku.get("price", "?")
    title = rec.get("title", "Sem título")
    pid   = str(rec.get("id", ""))
    link  = f"{CSSDEALS_URL}/product-detail.html?itemid={pid}"
    return {"id": pid, "title": title, "price": f"¥{price}", "link": link, "image": image}

def fetch_page(page: int) -> list:
    try:
        r = requests.get(API_URL + str(page), headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        return r.json().get("data", {}).get("records", [])
    except:
        return []

def get_total_pages() -> int:
    try:
        r = requests.get(API_URL + "1", headers=HEADERS, timeout=15)
        total = int(r.json().get("data", {}).get("total", 0))
        return max(1, (total + 19) // 20)
    except:
        return 1

def fetch_all_products() -> list:
    total_pages = get_total_pages()
    print(f"  [API] Total de páginas: {total_pages}")
    all_records = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_page, p): p for p in range(1, total_pages + 1)}
        done = 0
        for future in as_completed(futures):
            all_records.extend(future.result())
            done += 1
            if done % 50 == 0:
                print(f"  [API] {done}/{total_pages} páginas processadas...")
    print(f"  [API] Varredura completa: {len(all_records)} itens")
    return [parse_item(r) for r in all_records if r.get("id")]

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
    # Sem set_footer e sem timestamp — só aparece a hora do Discord naturalmente
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
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iniciando varredura completa...")
        try:
            loop  = asyncio.get_event_loop()
            items = await loop.run_in_executor(None, fetch_all_products)

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