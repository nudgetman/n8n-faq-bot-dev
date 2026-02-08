# n8n WhatsApp FAQ Bot (Development)

A multi-language WhatsApp FAQ chatbot built with n8n, WAHA (WhatsApp HTTP API), and Claude Haiku AI for semantic question matching.

## Features

- 🤖 **AI-Powered Semantic Matching** - Uses Claude Haiku for intelligent FAQ matching beyond keyword search
- 🌍 **Multi-Language Support** - Responds in English, Malay, and Simplified Chinese
- 📊 **PostgreSQL Integration** - User management, conversation history, and execution logging
- 🔄 **Robust Error Handling** - Retry logic, fallback responses, and failed message queue
- 📝 **Comprehensive Logging** - Structured JSONB logs for debugging and analytics

## Architecture

```
WhatsApp (via WAHA) → n8n Webhook → User Validation → FAQ Loading
                                    ↓
                              Claude Haiku Semantic Match
                                    ↓
                              Response Generation → WAHA Send
                                    ↓
                            Database Logging & History
```

## Prerequisites

- Docker and Docker Compose
- WAHA instance (WhatsApp HTTP API)
- Anthropic API key (for Claude Haiku)
- PostgreSQL 16+

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/nudgetman/n8n-faq-bot-dev.git
   cd n8n-faq-bot-dev
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

3. **Start the services**
   ```bash
   docker compose up -d
   ```

4. **Access n8n**
   - URL: http://localhost:5678
   - Import the workflow from `whatsapp-faq-bot-phase1.json`

5. **Configure n8n credentials**
   - Anthropic API (Claude Haiku)
   - WAHA Header Auth (`X-Api-Key`)
   - PostgreSQL connection

## Project Structure

```
.
├── docker-compose.yaml          # Docker services (n8n + PostgreSQL)
├── init.sql                     # Database schema initialization
├── FAQ_answers.json             # FAQ knowledge base
├── whatsapp-faq-bot-phase1.json # n8n workflow export
├── n8n-WAHA-Workflow.md         # Complete technical specification
├── fix-extract-node.md          # Troubleshooting guide
└── fix-faq-loading.md           # FAQ loading solution
```

## Database Schema

The application uses PostgreSQL with 4 main tables:
- `users` - User profiles and language preferences
- `conversation_history` - Chat logs with FAQ matching results
- `failed_messages` - Failed message queue for retry
- `execution_logs` - Structured JSONB logs for debugging

## Configuration

### Environment Variables

See `.env.example` for all required environment variables.

### FAQ Knowledge Base

The FAQ database is stored in `FAQ_answers.json` with the following structure:

```json
{
  "categories": [
    {
      "category": "TRADEMARK",
      "faqs": [
        {
          "question": "What is a Trademark?",
          "answer": "..."
        }
      ]
    }
  ]
}
```

## Development

### Testing the Workflow

Use curl to test the webhook:

```bash
curl -X POST http://localhost:5678/webhook-test/whatsapp-faq \
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

### Viewing Logs

```bash
# n8n logs
docker compose logs -f n8n

# PostgreSQL execution logs
docker exec postgres psql -U faqbot -d faqbot -c "SELECT * FROM execution_logs ORDER BY created_at DESC LIMIT 10;"
```

## Documentation

- [n8n-WAHA-Workflow.md](n8n-WAHA-Workflow.md) - Complete PRD with node configurations
- [fix-extract-node.md](fix-extract-node.md) - Webhook data extraction guide
- [fix-faq-loading.md](fix-faq-loading.md) - FAQ file loading solution

## Security Notes

⚠️ **Important Security Practices:**
- Never commit `.env` files with actual credentials
- Use environment variables for all sensitive configuration
- The `n8n_data/` directory contains encryption keys - never commit it
- WAHA API keys should be stored in n8n credentials manager

## License

This is a development project for learning and testing purposes.

## Support

For issues and questions, please open a GitHub issue.
