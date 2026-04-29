# 🤖 CSSDeals Discord Bot

Bot que monitora o CSSDeals e posta automaticamente novos itens no Discord.

---

## 📦 Instalação

### 1. Instale o Python
Baixe em: https://python.org/downloads  
Marque ✅ "Add to PATH" durante a instalação.

### 2. Instale as dependências
Abra o terminal (CMD ou PowerShell) na pasta do bot e rode:

```bash
pip install playwright discord-webhook python-dotenv
playwright install chromium
```

### 3. Configure o Webhook do Discord

1. Abra o servidor Discord onde quer receber os deals
2. Clique com direito no canal → **Editar Canal**
3. Vá em **Integrações** → **Webhooks** → **Novo Webhook**
4. Dê um nome (ex: "CSSDeals Bot") e copie a URL

### 4. Configure o arquivo .env

Renomeie `.env.example` para `.env` e cole sua URL do webhook:

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123456/abcdef...
```

### 5. Rode o bot

```bash
python bot.py
```

Na **primeira execução**, o bot vai registrar todos os itens da página sem postar (para não spammar). Nas próximas execuções, ele vai postar apenas os itens novos.

---

## 🖥️ Opções de Hospedagem (para ficar 24h online)

### Opção A — Seu próprio PC (grátis, mas fica offline quando desligar)
Simplesmente deixe o `python bot.py` rodando. Funciona bem para testes.

### Opção B — Railway.app (recomendado, gratuito até certo limite)
1. Crie conta em https://railway.app
2. Crie um novo projeto → "Deploy from GitHub Repo"
3. Suba os arquivos do bot no GitHub e conecte
4. Adicione a variável de ambiente `DISCORD_WEBHOOK_URL` nas configurações
5. Pronto — fica online 24h

### Opção C — VPS barato (mais controle, ~$4/mês)
- **Hostinger VPS** ou **Contabo** são boas opções no Brasil
- Sobe os arquivos via SFTP, instala Python e roda com `screen` ou `pm2`

### Opção D — Oracle Cloud (grátis para sempre com conta verificada)
- Oracle oferece VPS grátis permanente (Always Free tier)
- Mais trabalhoso de configurar mas 100% gratuito

---

## ⚙️ Personalização

No arquivo `bot.py`, você pode editar no topo:

| Variável | Descrição |
|----------|-----------|
| `CHECK_INTERVAL` | Segundos entre checagens (padrão: 90) |
| `embed color` | Cor do embed no Discord (hex, ex: `0xFF6B00`) |

---

## ⚠️ Aviso importante

O CSSDeals pode mudar a estrutura HTML do site a qualquer momento.
Se o bot parar de capturar itens, os **seletores CSS** no código precisarão
ser atualizados para refletir a nova estrutura da página.

Para inspecionar os seletores: abra o CSSDeals no Chrome → F12 → clique em um produto.
