# n8n WhatsApp FAQ Bot

A production-ready, multi-language WhatsApp FAQ chatbot built with **n8n**, **WAHA** (WhatsApp HTTP API), **Claude Haiku** AI, and **PostgreSQL**.

## Features

- **AI-Powered Semantic Matching** - Claude Haiku matches questions by intent, not just keywords
- **Multi-Language Support** - Detects and responds in English, Malay, and Simplified Chinese
- **PostgreSQL Integration** - User management, conversation history, and structured execution logging
- **Robust Error Handling** - 3-retry exponential backoff, failed message queue, all failure paths recorded
- **Persistent WhatsApp Session** - WAHA with Docker volume; no QR re-scan on container restart
- **Live Webhook Triggering** - WAHA auto-posts incoming WhatsApp messages to n8n

## Architecture

```
WhatsApp message
      │
      ▼
WAHA (webhook) → n8n Webhook Trigger
                        │
                        ▼
               Extract Message Data
                        │
                        ▼
               DB: User Validation ──► Unknown user path
                        │
                        ▼
               Load FAQ Knowledge Base
                        │
                        ▼
            Claude Haiku Semantic Match
                        │
                        ▼
             Generate Formatted Response
                        │
                        ▼
          Send via WAHA (3x retry + backoff)
                        │
               ┌────────┴────────┐
            Success            Failure
               │                  │
               ▼                  ▼
        Store History      Store History
        (sent=true)        (sent=false)
               │                  │
               └────────┬─────────┘
                        ▼
               Check Send Status
                        │
               ┌────────┴────────┐
            Success            Failure
               │                  │
               ▼                  ▼
        Log: success      Queue failed_messages
                          Log: failed_after_retries
```

**Workflow**: 24 nodes, `whatsapp-faq-bot-phase3.json`

## Prerequisites

- Docker and Docker Compose
- WAHA instance ([devlikeapro/waha](https://github.com/devlikeapro/waha))
- Anthropic API key (Claude Haiku)
- PostgreSQL 16+

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/nudgetman/n8n-faq-bot-dev.git
cd n8n-faq-bot-dev
cp .env.example .env
# Edit .env with your credentials
```

### 2. Start n8n and PostgreSQL

```bash
docker compose up -d
```

### 3. Initialise the database

```bash
docker exec -i postgres psql -U faqbot -d faqbot < init.sql
```

### 4. Start WAHA

```bash
docker run -d \
  --name waha \
  -p 3000:3000 \
  -v waha_data:/app/.wwebjs_auth \
  -e WHATSAPP_API_KEY=<your_waha_api_key> \
  -e WHATSAPP_DEFAULT_ENGINE=WEBJS \
  -e WHATSAPP_HOOK_URL=http://host.docker.internal:5678/webhook/whatsapp-listener-faq \
  -e WHATSAPP_HOOK_EVENTS=message \
  devlikeapro/waha:arm   # or devlikeapro/waha for x86

# Start the WhatsApp session (scan QR on first run)
curl -X POST http://localhost:3000/api/sessions/start \
  -H "X-Api-Key: <your_waha_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"name": "default"}'
```

On first run, scan the QR code at `GET http://localhost:3000/api/default/auth/qr`. The session is persisted in the `waha_data` Docker volume — subsequent restarts do not require re-scanning.

### 5. Import the workflow

1. Open n8n at `http://localhost:5678`
2. Go to **Workflows → Import from file**
3. Select `whatsapp-faq-bot-phase3.json`
4. Configure credentials (see below)
5. **Activate** the workflow

### 6. Configure n8n credentials

| Credential | Type | Notes |
|---|---|---|
| Anthropic (Claude Haiku) | Anthropic API | Model: `claude-haiku-4-5` |
| WAHA | Header Auth | Header: `X-Api-Key`, Value: your WAHA API key |
| PostgreSQL | Postgres | Host: `postgres`, Port: `5432`, DB: `faqbot` |

## Project Structure

```
.
├── docker-compose.yaml              # Docker services: n8n + PostgreSQL
├── init.sql                         # Database schema (4 tables)
├── FAQ_answers.json                 # FAQ knowledge base (JSON)
├── whatsapp-faq-bot-phase3.json     # n8n workflow export (current, 24 nodes)
├── whatsapp-faq-bot-phase2-final.json  # Phase 2 snapshot
├── whatsapp-faq-bot-phase1-validated.json  # Phase 1 snapshot
├── .env.example                     # Environment variable template
├── n8n-WAHA-Workflow.md             # Full technical specification / PRD
├── deploy-phase3.py                 # Phase 3 deployment helper script
├── fix-phase3-fetch.py              # Phase 3 WAHA fetch fix script
├── fix-phase3-connections.py        # Phase 3 connection repair script
├── test-phase2-workflow.sh          # 6 regression tests (Phase 2)
├── test-phase3-errors.sh            # 6 error-handling tests (Phase 3)
├── test-workflow.sh                 # Basic smoke tests
├── verify-phase2-database.sh        # DB verification script
└── test-logs/                       # Saved test execution logs
```

## Database Schema

Four tables in PostgreSQL (`init.sql`):

| Table | Purpose |
|---|---|
| `users` | Known users, language preferences, first/last seen timestamps |
| `conversation_history` | Every message: question, AI response, FAQ match, `sent` flag |
| `failed_messages` | Messages that failed all retries; includes `retry_count` and `failure_reason` |
| `execution_logs` | Structured JSONB logs per execution for debugging and analytics |

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|---|---|
| `N8N_BASIC_AUTH_USER` | n8n UI login username |
| `N8N_BASIC_AUTH_PASSWORD` | n8n UI login password |
| `CLAUDE_API_KEY` | Anthropic API key |
| `WAHA_API_KEY` | WAHA API key (also set as `WHATSAPP_API_KEY` in WAHA container) |
| `DB_PASSWORD` | PostgreSQL `faqbot` user password |

## FAQ Knowledge Base

`FAQ_answers.json` uses a category/FAQ structure:

```json
{
  "categories": [
    {
      "category": "TRADEMARK",
      "faqs": [
        {
          "question": "What is a Trademark?",
          "answer": "A trademark is a sign capable of distinguishing..."
        }
      ]
    }
  ]
}
```

Claude Haiku performs semantic matching against this file. The FAQ content is English-only; the AI translates responses to match the user's detected language (EN / MS / ZH).

## Testing

### Smoke test via curl

```bash
curl -X POST http://localhost:5678/webhook/whatsapp-listener-faq \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "60123456789@c.us",
      "fromMe": false,
      "body": "What is a trademark?",
      "timestamp": 1707200000
    }
  }'
```

### Regression tests

```bash
# Phase 2 regression (6 tests)
./test-phase2-workflow.sh

# Phase 3 error-handling (6 tests)
./test-phase3-errors.sh
```

### Query logs

```bash
# Recent execution logs
docker exec postgres psql -U faqbot -d faqbot \
  -c "SELECT status, created_at, details FROM execution_logs ORDER BY created_at DESC LIMIT 10;"

# Failed messages pending retry
docker exec postgres psql -U faqbot -d faqbot \
  -c "SELECT * FROM failed_messages WHERE resolved = false;"
```

## Development Phases

| Phase | Description | Status |
|---|---|---|
| 0 | Infrastructure: Docker, PostgreSQL, n8n | Complete |
| 1 | Core flow: webhook → Claude Haiku → WAHA reply | Complete |
| 2 | Database integration: users, history, logging | Complete |
| 3 | Error handling, retry logic, failure recording, live triggering | Complete |

## Security Notes

- Never commit `.env` — it is listed in `.gitignore`
- `n8n_data/` contains the encryption key — never commit it
- All API keys are stored in the n8n credentials manager, not hardcoded in nodes
- WAHA authenticates via `X-Api-Key` header (not `Authorization: Bearer`)
- PostgreSQL credentials use a least-privilege `faqbot` user

## License

Development project for learning and testing purposes.
