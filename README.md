# RedTrack Rules Engine v2 — Hybrid Automation

Sistema de automação de regras para campanhas de tráfego pago.

**Arquitetura Híbrida:**
- **Dados** → RedTrack API (cost, revenue, ROI, purchases, etc.)
- **Ações** → Direto na plataforma (Meta Graph API / Google Ads API)
- **Por membro** → Cada media buyer tem seus próprios tokens e regras

---

## Fluxo de Uso

```
1. TEAM & TOKENS    →  Cadastra membros (Renato, Pedro, Vini) com seus tokens
2. CREATE RULES     →  Define regras por membro/canal com condições e ações
3. RUN MONITORING   →  RedTrack puxa métricas → regras avaliam → plataforma executa
4. DASHBOARD        →  Vê resultados, logs, status de cada campanha
```

### Passo 1: Adicionar Membros (Team & Tokens)

Cada membro precisa de:
- **RedTrack API Key** — para puxar dados de campanhas
- **Facebook Access Token + Ad Account ID** — para pausar/escalar no Meta
- **Google Ads tokens** (Developer Token, OAuth, Customer ID) — para pausar no Google

### Passo 2: Criar Regras

Cada regra é vinculada a um membro e define:
- **Traffic Channel**: Facebook ou Google
- **Rule Object**: Campaign, Ad Set, Ad (depende do canal)
- **Filtro**: texto contido no nome da campanha (ex: "[Renato]")
- **Ações** (até 5): Pause, Pause & Restart, Notification, Scale Up/Down
- **Condições** (até 5 por ação): Cost ≥ 100 + Purchase = 0 + ROI < -30, etc.

### Passo 3: Executar

- **Manual**: botão "Run Now" no dashboard
- **Automático**: Scheduler configurável (5min a 1h)
- **DRY RUN**: modo seguro que simula sem executar

### Passo 4: Monitorar

Dashboard mostra por campanha: membro, canal, métricas, regra que bateu, ação executada, status.

---

## Setup

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Acesse: http://localhost:8000

### Variáveis de Ambiente (opcionais)

```bash
# RedTrack
export REDTRACK_BASE_URL="https://api.redtrack.io"

# SMTP para notificações
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="user@gmail.com"
export SMTP_PASS="app_password"
```

### Sem tokens configurados?

O sistema usa **dados mock automaticamente** (8 campanhas FB + 4 Google, distribuídas entre os membros cadastrados) para você testar toda a interface e lógica.

---

## Estrutura

```
rules-rt-v2/
├── app.py                    # FastAPI — rotas, monitoring engine, scheduler
├── database.py               # SQLite schema com team_members, rules, actions, conditions
├── models.py                 # Data classes + constantes (channels, métricas, operators)
├── requirements.txt
├── services/
│   ├── members.py            # CRUD de membros da equipe
│   ├── platforms.py          # Executores: Meta Graph API + Google Ads API
│   ├── redtrack.py           # Cliente RedTrack + mock data
│   ├── rules.py              # CRUD de regras + motor de avaliação de condições
│   ├── notify.py             # Email SMTP + Webhook
│   └── scheduler.py          # Background thread scheduler
├── templates/
│   ├── base.html             # Layout com sidebar
│   ├── index.html            # Dashboard
│   ├── team.html             # Membros + tokens + flow explainer
│   ├── rules.html            # Builder de regras dinâmico
│   └── logs.html             # Histórico de execução
└── static/
    ├── style.css             # Dark industrial theme
    └── app.js                # Monitoring, scheduler, pause
```

## Plataformas suportadas

| Canal | Dados (RedTrack) | Pause/Restart | Scale Budget |
|-------|:-:|:-:|:-:|
| Facebook / Meta Ads | ✅ | ✅ Graph API v21 | ✅ daily_budget |
| Google Ads | ✅ | ✅ REST API v18 | ⚠️ estrutura pronta |

## Métricas disponíveis para condições

Cost, Revenue, Profit, Purchases, Clicks, Impressions, ROI%, ROAS%, CPA, CPC, CTR%, CR%, EPC, InitiateCheckout, AddToCart, Frequency
