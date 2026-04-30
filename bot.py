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

seen_in_memory = set()
first_run = True

intents = discord.Intents.default()
client  = discord.Client(intents=intents)

def item_id(item: dict) -> str:
    return hashlib.md5(str(item.get("id", "") or item.get("title", "")).encode()).hexdigest()

def get_platform_link(record: dict) -> str:
    """Gera link de compra baseado na plataforma."""
    platform = record.get("salePlatform")
    item_id_val = record.get("itemId") or record.get("id", "")
    sku = ""
    if record.get("skus"):
        sku = record["skus"][0].get("skuId", "")

    if platform == 1:  # Taobao
        link = f"https://item.taobao.com/item.htm?id={item_id_val}"
        if sku:
            link += f"&sku_id={sku}"
        return link
    elif platform == 2:  # Weidian
        return f"https://weidian.com/item.html?itemID={item_id_val}"
    elif platform == 3:  # 1688
        return f"https://detail.1688.com/offer/{item_id_val}.html"
    return f"{CSSDEALS_URL}/product-detail.html?itemid={item_id_val}"

def fetch_all_products() -> list:
    """Busca todos os produtos de todas as páginas."""
    all_items = []
    page = 1

    while True:
        try:
            r = requests.get(API_URL + str(page), headers=HEADERS, timeout=15)
            if r.status_code != 200:
                print(f"  [API] Página {page} retornou {r.status_code}, parando.")
                break

            data = r.json()
            records = data.get("data", {}).get("records", [])
            total   = data.get("data", {}).get("total", 0)

            if not records:
                break

            for rec in records:
                sku   = rec["skus"][0] if rec.get("skus") else {}
                image = sku.get("image", "")
                if image and "?" not in image:
                    image += "?x-oss-process=image/resize,w_500"

                price = sku.get("price", "?")
                title = rec.get("title", "Sem título")
                link  = get_platform_link(rec)

                all_items.append({
                    "id":    rec.get("id", ""),
                    "title": title,
                    "price": f"¥{price}",
                    "link":  link,
                    "image": image,
                    "platform": rec.get("salePlatform", 0),
                })

            total = int(total)
            total_pages = (total + 19) // 20
            print(f"  [API] Página {page}/{total_pages}: {len(records)} itens | Total: {total}")

            if page >= total_pages or page >= 5:
                break
            page += 1
            time.sleep(0.5)  # respeita o servidor

        except Exception as e:
            print(f"  [ERRO API página {page}] {e}")
            break

    return all_items

async def post_item(channel, item: dict):
    platform_names = {1: "Taobao", 2: "Weidian", 3: "1688"}
    platform = platform_names.get(item.get("platform", 0), "Ver site")

    embed = discord.Embed(
        title=f"🔥 Novo no CSSDeals!\n{item['title'][:250]}",
        url=item["link"],
        color=0xFF6B00,
    )
    embed.add_field(name="💰 Preço",    value=item["price"],                          inline=True)
    embed.add_field(name="🛍️ Plataforma", value=platform,                             inline=True)
    embed.add_field(name="🛒 Comprar",  value=f"[Clique aqui]({item['link']})",       inline=False)

    if item.get("image") and item["image"].startswith("http"):
        embed.set_image(url=item["image"])

    embed.set_footer(text=f"CSSDeals • {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    embed.timestamp = datetime.now(timezone.utc)
    await channel.send(embed=embed)

async def monitor_loop():
    global seen_in_memory, first_run
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    if not channel:
        print(f"❌ Canal {CHANNEL_ID} não encontrado!")
        return

    print(f"✅ Canal encontrado: #{channel.name}")

    while not client.is_closed():
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checando todas as páginas do CSSDeals...")
        try:
            loop  = asyncio.get_event_loop()
            items = await loop.run_in_executor(None, fetch_all_products)
            print(f"  → {len(items)} itens encontrados no total")

            current_ids = {item_id(i) for i in items}

            if first_run:
                seen_in_memory = current_ids.copy()
                print(f"  → Primeira execução: {len(seen_in_memory)} itens registrados (sem postar).")
                first_run = False
            else:
                new_items = [i for i in items if item_id(i) not in seen_in_memory]
                print(f"  → {len(new_items)} novos itens!")
                for item in reversed(new_items):
                    await post_item(channel, item)
                    print(f"  ✔ Postado: {item['title'][:60]}")
                    await asyncio.sleep(2)
                seen_in_memory = current_ids.copy()

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