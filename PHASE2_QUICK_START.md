# Phase 2 Quick Start Guide

**Goal**: Get the Phase 2 WhatsApp FAQ Bot workflow running in 10 minutes.

---

## Prerequisites Checklist

Before starting, ensure you have:

- ✅ Docker and Docker Compose installed
- ✅ n8n container running (`docker ps | grep n8n`)
- ✅ PostgreSQL container running (`docker ps | grep postgres`)
- ✅ Database tables created (`docker exec postgres psql -U faqbot -d faqbot -c "\dt"`)
- ✅ FAQ file mounted at `/home/node/FAQ_answers.json` in n8n container
- ✅ WAHA running and accessible at `http://localhost:3000`

---

## Step 1: Import Workflow (2 minutes)

1. Open n8n UI in browser:
   ```
   http://localhost:5678
   ```

2. Login credentials:
   - Username: `choowie`
   - Password: `Nudget01?`

3. Navigate to **Workflows** → **Import from File**

4. Select file:
   ```
   /Users/najmie/n8n/whatsapp-faq-bot-phase2.json
   ```

5. Click **Import**

6. Workflow should now appear as "WhatsApp FAQ Bot - Phase 2 (Database Integration)"

---

## Step 2: Configure PostgreSQL Credential (3 minutes)

1. In n8n UI, go to **Credentials** (left sidebar)

2. Click **Add Credential**

3. Search for "Postgres" and select **Postgres**

4. Fill in the form:
   | Field | Value |
   |-------|-------|
   | **Name** | `PostgreSQL account` |
   | **Host** | `postgres` |
   | **Port** | `5432` |
   | **Database** | `faqbot` |
   | **User** | `faqbot` |
   | **Password** | (from your `.env` file) |
   | **SSL** | Off |

5. Click **Create** (or **Save**)

6. Verify the credential is created successfully

---

## Step 3: Verify Other Credentials (1 minute)

Ensure these credentials exist from Phase 1:

### Anthropic Account
- Go to **Credentials** → Search "Anthropic"
- Should see "Anthropic account"
- If missing, create with your Anthropic API key

### WAHA API Key
- Go to **Credentials** → Search "Header"
- Should see "WAHA API Key"
- If missing, create Header Auth credential:
  - Header Name: `X-Api-Key`
  - Header Value: Your WAHA API key

---

## Step 4: Seed Test User in Database (2 minutes)

1. Connect to PostgreSQL:
   ```bash
   docker exec -it postgres psql -U faqbot -d faqbot
   ```

2. Insert test user:
   ```sql
   INSERT INTO users (phone_number, name, preferred_language, status)
   VALUES ('60198775521@c.us', 'Test User', 'en', 'active')
   ON CONFLICT (phone_number) DO NOTHING;
   ```

3. Verify user was created:
   ```sql
   SELECT * FROM users;
   ```

   Should show:
   ```
   id | phone_number       | name      | status | preferred_language | created_at
   ---|-------------------|-----------|--------|-------------------|------------
   1  | 60198775521@c.us  | Test User | active | en                | 2026-02-09...
   ```

4. Exit PostgreSQL:
   ```sql
   \q
   ```

---

## Step 5: Activate Workflow (1 minute)

1. Open the imported workflow in n8n UI

2. Check that all nodes are showing correctly (no red error icons)

3. Click the **Active** toggle in the top-right corner

4. Workflow should now be active (green toggle)

---

## Step 6: Test the Workflow (1 minute)

### Test 1: Basic FAQ Question (English)

```bash
curl -X POST http://localhost:5678/webhook/whatsapp-faq \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "60198775521@c.us",
      "fromMe": false,
      "body": "What is a trademark?",
      "timestamp": 1707200001
    }
  }'
```

**Expected Response**:
- User receives WhatsApp message with FAQ answer
- Response includes "Based on our FAQ:" prefix
- Check n8n execution log (should show success)

### Test 2: Follow-up Question (Multi-turn)

Wait 5 seconds, then send:

```bash
curl -X POST http://localhost:5678/webhook/whatsapp-faq \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "60198775521@c.us",
      "fromMe": false,
      "body": "How much does it cost?",
      "timestamp": 1707200002
    }
  }'
```

**Expected Response**:
- User receives answer about trademark registration fees
- AI should reference previous question about trademarks
- Check conversation history in database

---

## Step 7: Verify Database Records (Optional)

### Check Conversation History

```bash
docker exec postgres psql -U faqbot -d faqbot -c "SELECT chat_id, user_message, bot_response, created_at FROM conversation_history ORDER BY created_at DESC LIMIT 5;"
```

Should show your test messages.

### Check Execution Logs

```bash
docker exec postgres psql -U faqbot -d faqbot -c "SELECT chat_id, status, metadata->>'faqLoaded' as faq_loaded, metadata->>'historyCount' as history_count, created_at FROM execution_logs ORDER BY created_at DESC LIMIT 5;"
```

Should show execution metadata with `faq_loaded=true` and `history_count` increasing.

---

## Troubleshooting

### Issue: Workflow import fails

**Solution**:
- Ensure JSON file is valid (check for syntax errors)
- Try importing as a new workflow instead of updating existing

### Issue: PostgreSQL credential not connecting

**Solution**:
1. Verify PostgreSQL container is running:
   ```bash
   docker ps | grep postgres
   ```
2. Test connection from n8n container:
   ```bash
   docker exec n8n nc -zv postgres 5432
   ```
3. Check `docker-compose.yaml` has correct network configuration

### Issue: "FAQ file not found" error

**Solution**:
1. Verify FAQ file is mounted:
   ```bash
   docker exec n8n ls -la /home/node/FAQ_answers.json
   ```
2. If missing, add volume mount to `docker-compose.yaml`:
   ```yaml
   volumes:
     - ./FAQ_answers.json:/home/node/FAQ_answers.json:ro
   ```
3. Restart n8n:
   ```bash
   docker compose restart n8n
   ```

### Issue: No response received from WAHA

**Solution**:
1. Check WAHA is running:
   ```bash
   curl http://localhost:3000/api/health
   ```
2. Verify WAHA API key in Header Auth credential
3. Check WAHA logs for errors:
   ```bash
   docker logs waha
   ```

### Issue: Execution shows errors in database nodes

**Solution**:
- All database nodes have `onError: "continueRegularOutput"`
- User should still receive responses even if DB fails
- Check PostgreSQL logs:
  ```bash
  docker logs postgres
  ```

---

## Success Criteria

Your Phase 2 workflow is working correctly if:

- ✅ User receives FAQ responses via WhatsApp
- ✅ Follow-up questions reference previous conversation
- ✅ `conversation_history` table is populated
- ✅ `execution_logs` table is populated
- ✅ Execution logs show `faqLoaded=true` and `historyCount` > 0
- ✅ No errors in n8n execution log
- ✅ Unknown users still receive responses (graceful degradation)

---

## Next Steps

### Configure WAHA Webhook (for production)

Update WAHA to send webhooks to n8n:

```bash
curl -X PUT "http://localhost:3000/api/sessions/default" \
  -H "X-Api-Key: <YOUR_WAHA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "default",
    "config": {
      "webhooks": [{
        "url": "http://host.docker.internal:5678/webhook/whatsapp-faq",
        "events": ["message"]
      }]
    }
  }'
```

### Monitor Database Growth

Set up periodic cleanup:

```sql
-- Delete conversation history older than 90 days
DELETE FROM conversation_history
WHERE created_at < NOW() - INTERVAL '90 days';

-- Delete execution logs older than 30 days
DELETE FROM execution_logs
WHERE created_at < NOW() - INTERVAL '30 days';
```

### Add More Users

Insert additional users to database:

```sql
INSERT INTO users (phone_number, name, preferred_language, status)
VALUES ('60123456789@c.us', 'John Doe', 'en', 'active');
```

### Phase 3 Implementation

When ready for retry logic and advanced error handling:
- Read `IMPLEMENTATION_PLAN.md` Section "Phase 3"
- Phase 3 adds 4 more nodes for exponential backoff and failed message storage

---

## Quick Reference

| Resource | Location |
|----------|----------|
| Workflow JSON | `/Users/najmie/n8n/whatsapp-faq-bot-phase2.json` |
| Full Documentation | `/Users/najmie/n8n/PHASE2_COMPLETION_SUMMARY.md` |
| Comparison with Phase 1 | `/Users/najmie/n8n/PHASE2_NODE_COMPARISON.md` |
| Implementation Plan | `/Users/najmie/n8n/IMPLEMENTATION_PLAN.md` |
| Database Schema | `/Users/najmie/n8n/init.sql` |

| Command | Purpose |
|---------|---------|
| `docker compose up -d` | Start all containers |
| `docker compose logs -f n8n` | View n8n logs |
| `docker exec postgres psql -U faqbot -d faqbot` | Connect to database |
| `docker compose restart n8n` | Restart n8n after config changes |

---

**Estimated Total Setup Time**: 10 minutes

**Status**: ✅ Phase 2 is production-ready for deployment
