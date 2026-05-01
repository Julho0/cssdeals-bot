import os, json, asyncio, requests, re
from datetime import datetime
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
SEEN_FILE = "seen_ids.json"

seen_ids = set()

intents = discord.Intents.default()
client  = discord.Client(intents=intents)

# ── Persistência ──────────────────────────────────────────
def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
        except:
            pass
    return set()

def save_seen():
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_ids), f)

# ── Utilitários ───────────────────────────────────────────
URL_RE = re.compile(r'^https?://[^\s<>"{}|\\^`\[\]]+$')

def valid_url(url: str) -> bool:
    return bool(url and URL_RE.match(url))

def parse_item(rec: dict) -> dict:
    sku   = rec["skus"][0] if rec.get("skus") else {}
    pid   = str(rec.get("id", ""))
    image = sku.get("image", "")
    return {
        "id":    pid,
        "title": rec.get("title", "Sem título"),
        "price": f"¥{sku.get('price', '?')}",
        "link":  f"{CSSDEALS_URL}/product-detail.html?itemid={pid}",
        "image": image if valid_url(image) else "",
    }

def fetch_page(page: int):
    try:
        r = requests.get(API_URL + str(page), headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return [], 0
        data = r.json().get("data", {})
        return data.get("records", []), int(data.get("total", 0))
    except:
        return [], 0

# ── Varredura completa (só na primeira vez) ───────────────
def full_index() -> set:
    """Varre todas as páginas e retorna set de todos os IDs."""
    _, total = fetch_page(1)
    total_pages = max(1, (total + 19) // 20)
    print(f"  [ÍNDICE] Indexando {total_pages} páginas ({total} itens)...")

    all_ids = set()
    for page in range(1, total_pages + 1):
        records, _ = fetch_page(page)
        for rec in records:
            pid = str(rec.get("id", ""))
            if pid:
                all_ids.add(pid)
        if page % 100 == 0:
            print(f"  [ÍNDICE] {page}/{total_pages} páginas...")

    print(f"  [ÍNDICE] Concluído: {len(all_ids)} IDs salvos.")
    return all_ids

# ── Checagem normal (50 páginas) ──────────────────────────
def fetch_recent() -> list:
    """Busca as 50 primeiras páginas e retorna itens."""
    records_p1, total = fetch_page(1)
    total_pages = max(1, (total + 19) // 20)
    pages = min(50, total_pages)

    all_items = [parse_item(r) for r in records_p1]
    for page in range(2, pages + 1):
        records, _ = fetch_page(page)
        all_items.extend(parse_item(r) for r in records)

    print(f"  [API] {len(all_items)} itens nas primeiras {pages} páginas")
    return all_items

# ── Discord ───────────────────────────────────────────────
async def post_item(channel, item: dict):
    embed = discord.Embed(
        title=item["title"][:256],
        url=item["link"],
        color=0xFF6B00,
    )
    embed.set_author(name="🔥 Novo no CSSDeals!")
    embed.add_field(name="💰 Preço",   value=item["price"],                        inline=True)
    embed.add_field(name="🛒 Comprar", value=f"[Ver no CSSDeals]({item['link']})", inline=True)
    if item.get("image"):
        embed.set_image(url=item["image"])
    await channel.send(embed=embed)

async def monitor_loop():
    global seen_ids
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    if not channel:
        print(f"❌ Canal {CHANNEL_ID} não encontrado!")
        return

    print(f"✅ Canal encontrado: #{channel.name}")

    # ── Primeira execução: carrega ou cria o índice ──
    seen_ids = load_seen()

    if not seen_ids:
        print("  📂 Nenhum índice encontrado — fazendo varredura completa...")
        loop = asyncio.get_event_loop()
        seen_ids = await loop.run_in_executor(None, full_index)
        save_seen()
        print(f"  ✅ Índice salvo com {len(seen_ids)} IDs. Monitoramento iniciado!")
    else:
        print(f"  📂 Índice carregado: {len(seen_ids)} IDs conhecidos.")

    # ── Loop de monitoramento ──
    while not client.is_closed():
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checando CSSDeals...")
        try:
            loop  = asyncio.get_event_loop()
            items = await loop.run_in_executor(None, fetch_recent)

            new_items = [i for i in items if i["id"] not in seen_ids]
            print(f"  → {len(new_items)} novos itens!")

            for item in new_items:
                try:
                    await post_item(channel, item)
                    print(f"  ✔ Postado: {item['title'][:60]}")
                    seen_ids.add(item["id"])
                    save_seen()
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"  ✘ Erro ao postar: {e}")
                    seen_ids.add(item["id"])
                    save_seen()

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