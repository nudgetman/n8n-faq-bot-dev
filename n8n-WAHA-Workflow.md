# WhatsApp FAQ Chatbot Workflow - PRD for Claude Code & n8n

**Project**: Multi-language WhatsApp FAQ Bot via WAHA + n8n + Claude Haiku  
**Status**: Ready for Claude Code implementation  
**Date Created**: February 2026  

---

## Executive Summary

Build an n8n workflow that:
1. Receives WhatsApp messages via WAHA webhook
2. Validates users against PostgreSQL database
3. Loads FAQ knowledge base from JSON
4. Uses Claude Haiku with semantic matching to answer questions
5. Sends responses back to WhatsApp with multi-language support (EN, MS, ZH)
6. Stores conversation history and implements robust error handling

---

## Architecture Overview

```
WAHA Webhook
    ↓
[Trigger: Webhook Receive]
    ↓
[Extract: message, chatId, userNumber]
    ↓
[Database: Check if Known User]
    ↓
[Load: FAQ_answers.json]
    ↓
[AI Agent: Claude Haiku Semantic Matching]
    ├─→ [If FAQ match] → Craft Answer from KB
    └─→ [If No Match] → Generate Out-of-Scope Response
    ↓
[Store: Conversation in History Table]
    ↓
[Send: WAHA cURL with Retry Logic]
    ↓
[Log: Structured JSON to File + Database]
```

---

## Workflow Nodes & Configuration

### 1. **Webhook Trigger Node**
**Name**: `Webhook_WAHA_Incoming`

- **Trigger Type**: Webhook
- **HTTP Method**: POST
- **Path**: `/webhook/whatsapp-faq` (customize as needed)
- **Expected Payload**:
  ```json
  {
    "message": "Is trademark registration compulsory?",
    "chatId": "120XXXXXXXXX@c.us",
    "from": "120XXXXXXXXX",
    "timestamp": 1707200000
  }
  ```
- **Response**: 200 OK with acknowledgment

---

### 2. **Extract Data Node**
**Name**: `Extract_Message_Data`

**Type**: Set Variables or HTTP Request (pass-through)

**Extracts**:
- `userMessage` = `$json.message`
- `chatId` = `$json.chatId`
- `userNumber` = `$json.from`
- `incomingTimestamp` = `$json.timestamp`
- `language` = Auto-detect (handled in AI node)

**Output**: Pass to next node with structured data

---

### 3. **Database Query - Check Known User**
**Name**: `DB_Check_Known_User`

**Type**: Postgres (or your DB)

**Query**:
```sql
SELECT id, name, status, preferred_language 
FROM users 
WHERE phone_number = $1
LIMIT 1
```

**Parameters**: `userNumber`

**Expected Output**:
```json
{
  "id": "user_123",
  "name": "Ahmad",
  "status": "active",
  "preferred_language": "ms"
}
```

**Handle**: If no user found, set `isKnownUser = false`, `userId = null`

---

### 4. **Load FAQ Knowledge Base**
**Name**: `Load_FAQ_Answers`

**Type**: Read Files / HTTP Request to S3/GCS (or local file if self-hosted)

**Input**: Path to `FAQ_answers.json`

**Expected Structure**:
```json
{
  "faqs": [
    {
      "id": "faq_001",
      "category": "trademarks",
      "question": "Is trademark registration compulsory?",
      "answer": "No, trademark registration is not compulsory...",
      "relatedQuestions": ["What is a trademark?", "How long does registration take?"]
    },
    {
      "id": "faq_002",
      "category": "patents",
      "question": "What is a patent?",
      "answer": "A patent is an intellectual property right..."
    }
  ]
}
```

**Output**: Store as `faqDatabase` for AI agent reference

**Error Handling**: 
- If file not found → Log ERROR, trigger fallback (out-of-scope message)
- If JSON invalid → Log ERROR, trigger fallback

---

### 5. **Retrieve Conversation History**
**Name**: `DB_Get_Conversation_History`

**Type**: Postgres

**Query**:
```sql
SELECT id, user_message, agent_response, created_at, language_detected
FROM conversation_history
WHERE chat_id = $1
ORDER BY created_at DESC
LIMIT 5
```

**Parameters**: `chatId`

**Purpose**: Provide context window to Claude agent (last 5 exchanges)

**Output**: Array of conversation objects

---

### 6. **AI Agent - Claude Haiku with Semantic Matching**
**Name**: `AI_Agent_Claude_Haiku`

**Type**: n8n Claude Node (Anthropic integration)

**Model**: `claude-haiku-4-5-20251001`

**System Prompt**:
```
You are a professional and concise FAQ assistant for a legal/IP services company.
Your knowledge base is a JSON file of frequently asked questions.

CRITICAL INSTRUCTIONS:
1. Use SEMANTIC MATCHING: Understand the user's question in intent/meaning, not just exact phrase matching.
2. Search the provided FAQ database for the BEST matching answer by topic and intent.
3. If you find a match (>70% confidence), answer using the FAQ answer and explicitly state: "Based on our FAQ:"
4. If no match found (<70% confidence), respond: "I don't have information about this in my knowledge base. Please contact our support team for assistance."
5. ALWAYS suggest related FAQs if available - even if the primary question matches, offer: "You might also find these helpful: [related question titles]"
6. Be aware of conversation history provided - use context from previous exchanges if relevant.
7. MULTI-LANGUAGE: Detect the language of the user's question and respond in the same language.
   - English (en), Malay (ms), Simplified Chinese (zh)
   - If unsure of language, ask for clarification politely.
8. If the question is ambiguous, request clarification rather than guessing.

Tone: Professional, helpful, concise, efficient. Keep responses under 150 words when possible.
```

**Input Variables**:
```json
{
  "faqDatabase": <output from Load_FAQ_Answers>,
  "userMessage": <output from Extract_Message_Data>,
  "conversationHistory": <output from DB_Get_Conversation_History>,
  "userLanguageDetected": "auto-detect from userMessage"
}
```

**Prompt Template**:
```
FAQ Knowledge Base:
{{$json.faqDatabase}}

Conversation History (last 5 messages):
{{$json.conversationHistory}}

User's Current Message (language will be auto-detected):
"{{$json.userMessage}}"

Please:
1. Detect the language of the user message
2. Search the FAQ database semantically for the best match
3. If found, provide the answer from the FAQ with the prefix "Based on our FAQ:"
4. If not found, provide an out-of-scope response in the same language
5. Respond ONLY with the message text to send to the user. Do NOT include metadata or reasoning.
```

**Expected Output**:
```json
{
  "response": "Based on our FAQ: No, trademark registration is not compulsory in Malaysia...",
  "language_detected": "en",
  "faq_match": "faq_001",
  "confidence": 0.92
}
```

**Error Handling**:
- Claude API timeout → Retry once, then log ERROR and send generic error message to user

---

### 7. **Store Conversation History**
**Name**: `DB_Store_Conversation`

**Type**: Postgres INSERT

**Query**:
```sql
INSERT INTO conversation_history 
(chat_id, user_id, user_message, agent_response, faq_matched, language_detected, created_at)
VALUES ($1, $2, $3, $4, $5, $6, NOW())
RETURNING id
```

**Parameters**:
- `$1`: `chatId`
- `$2`: `userId` (from step 3, or NULL if unknown user)
- `$3`: `userMessage`
- `$4`: AI response from step 6
- `$5`: `faq_match` from step 6 (or null)
- `$6`: `language_detected` from step 6

**Error Handling**: Log WARNING if insert fails, but don't block response send

---

### 8. **Send Response via WAHA (with Retry)**
**Name**: `Send_WAHA_With_Retry`

**Type**: HTTP Request with Retry Logic

**Retry Configuration**:
- Max Retries: 3
- Backoff Strategy: Exponential (2s, 4s, 8s)
- Retry on Status: 5xx, timeout

**HTTP Method**: POST (or cURL equivalent via Code node)

**URL**: `{{$env.WAHA_API_URL}}/messages/send`
- Store `WAHA_API_URL` in n8n credentials

**Headers**:
```
Content-Type: application/json
Authorization: Bearer {{$env.WAHA_API_KEY}}
```

**Body**:
```json
{
  "chatId": "{{$json.chatId}}",
  "text": "{{$json.agent_response}}"
}
```

**Expected Response**: 
```json
{
  "success": true,
  "messageId": "msg_12345"
}
```

**Success Handling**: 
- Log to structured logs: "Message sent successfully"
- Mark in conversation_history as `sent = true`

---

### 9. **Handle Send Failures (After Retries)**
**Name**: `Handle_WAHA_Send_Failure`

**Type**: Conditional (if retries exhausted and status != 2xx)

**Actions**:
1. Insert into `failed_messages` table:
   ```sql
   INSERT INTO failed_messages 
   (chat_id, user_id, user_message, agent_response, error_reason, retry_count, created_at)
   VALUES ($1, $2, $3, $4, $5, 3, NOW())
   ```
2. Log ERROR to structured logs with full context
3. Alert (optional: send to Slack/email)

**Note**: Do NOT retry further after this point

---

### 10. **Error Handling - Database Connection Failure**
**Name**: `Handle_DB_Connection_Error`

**Trigger**: On any Postgres query failure

**Actions**:
1. Log CRITICAL error to structured logs
2. Send generic "Service temporarily unavailable" message via WAHA (if connection exists)
3. Store failed message in memory/cache for later processing

**Recovery**: Use exponential backoff for DB reconnection

---

### 11. **Error Handling - FAQ Load Failure**
**Name**: `Handle_FAQ_Load_Error`

**Trigger**: If FAQ file read fails

**Actions**:
1. Log ERROR to structured logs
2. Bypass semantic matching
3. Send user: "I'm experiencing a temporary issue. Please try again in a moment."
4. Alert admin to check FAQ file

---

### 12. **Structured Logging to Database**
**Name**: `Log_Execution_Structured`

**Type**: Postgres INSERT

**Query**:
```sql
INSERT INTO execution_logs 
(execution_id, chat_id, user_id, status, faq_matched, language_detected, total_time_ms, error_count, log_data)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
RETURNING id
```

**Log Data Structure** (JSONB):
```json
{
  "timestamp": "2026-02-07T10:30:45Z",
  "executionId": "exec_12345",
  "webhook": {
    "chatId": "120XXXXXXXXX@c.us",
    "userNumber": "120XXXXXXXXX"
  },
  "database": {
    "userFound": true,
    "userId": "user_123",
    "connectionStatus": "success"
  },
  "faq": {
    "loaded": true,
    "totalQuestions": 45,
    "loadTime_ms": 123
  },
  "ai": {
    "model": "claude-haiku-4-5-20251001",
    "languageDetected": "en",
    "faqMatch": "faq_001",
    "confidence": 0.92,
    "relatedFaqsSuggested": ["faq_003", "faq_007"],
    "responseTime_ms": 850
  },
  "send": {
    "status": "success",
    "wahaMessageId": "msg_12345",
    "retries": 0,
    "totalTime_ms": 1500
  },
  "errors": []
}
```

**Parameters**:
- `$1`: `executionId` (n8n execution ID)
- `$2`: `chatId`
- `$3`: `userId` (null for unknown users)
- `$4`: `status` (success, failed_after_retries, error)
- `$5`: `faq_matched` (FAQ ID or null)
- `$6`: `language_detected` (en, ms, zh, or null)
- `$7`: `total_time_ms` (total execution time)
- `$8`: `error_count` (0 if no errors, 1+ if errors occurred)
- `$9`: `log_data` (JSONB object with detailed info above)

**Error Handling**: Log WARNING if insert fails, but don't block workflow completion

**Note**: This replaces file-based logging. All logs are now queryable from PostgreSQL.

---

## Database Schema Requirements

### Table: `users`
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  phone_number VARCHAR(20) UNIQUE NOT NULL,
  name VARCHAR(100),
  status VARCHAR(20) DEFAULT 'active',
  preferred_language VARCHAR(5),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

### Table: `conversation_history`
```sql
CREATE TABLE conversation_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id VARCHAR(50) NOT NULL,
  user_id UUID REFERENCES users(id),
  user_message TEXT NOT NULL,
  agent_response TEXT NOT NULL,
  faq_matched VARCHAR(50),
  language_detected VARCHAR(5),
  sent BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_conversation_chat_id ON conversation_history(chat_id);
CREATE INDEX idx_conversation_created_at ON conversation_history(created_at);
```

### Table: `failed_messages`
```sql
CREATE TABLE failed_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id VARCHAR(50) NOT NULL,
  user_id UUID REFERENCES users(id),
  user_message TEXT NOT NULL,
  agent_response TEXT NOT NULL,
  error_reason TEXT,
  retry_count INT DEFAULT 0,
  resolved BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT NOW(),
  resolved_at TIMESTAMP
);

CREATE INDEX idx_failed_messages_unresolved ON failed_messages(resolved);
```

### Table: `execution_logs`
```sql
CREATE TABLE execution_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  execution_id VARCHAR(100),
  chat_id VARCHAR(50),
  user_id UUID REFERENCES users(id),
  status VARCHAR(20),
  total_time_ms INT,
  error_count INT DEFAULT 0,
  log_data JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_execution_logs_status ON execution_logs(status);
CREATE INDEX idx_execution_logs_created_at ON execution_logs(created_at);
```

---

## Environment Variables & Credentials

**Store in n8n as Credentials**:
```
WAHA_API_URL=https://your-waha-instance.com/api
WAHA_API_KEY=your_waha_bearer_token (REQUIRED for send authentication)
DB_HOST=your-postgres-host
DB_PORT=5432
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
FAQ_FILE_PATH=/path/to/FAQ_answers.json
CLAUDE_API_KEY=your_anthropic_api_key
```

**WAHA Authentication**:
- Bearer token stored in `WAHA_API_KEY`
- Used in HTTP Authorization header: `Authorization: Bearer {{$env.WAHA_API_KEY}}`
- Credentials stored securely in n8n credentials manager

---

## Multi-Language Support Strategy

**Language Detection**: Use Claude Haiku's built-in language detection in the system prompt

**Supported Languages**:
1. **English (en)**: Respond in English
2. **Malay (ms)**: Respond in Malay (বাংলা not supported, but Malay yes)
3. **Simplified Chinese (zh)**: Respond in Simplified Chinese

**Fallback**: If language cannot be detected, ask user: "I detected your message may be in [detected language]. Is that correct?"

**Note**: FAQ answers are in English only; AI agent handles translation in responses.

---

## Error Handling & Resilience

| Error Scenario | Handling | Logging |
|---|---|---|
| WAHA send fails (3 retries) | Store in `failed_messages` table, log ERROR, alert admin | CRITICAL |
| PostgreSQL connection fails | Retry with backoff, send generic error to user | CRITICAL |
| FAQ file load fails | Skip semantic matching, send error to user | ERROR |
| Claude API timeout | Retry once, send generic error, log ERROR | ERROR |
| Unknown user | Continue normally, log WARNING | WARNING |
| Invalid JSON in FAQ | Log ERROR, trigger fallback behavior | ERROR |

---

## Success Criteria

✅ Webhook receives and parses WAHA message correctly  
✅ User validation works (known vs unknown)  
✅ FAQ loads and semantic matching functions  
✅ Claude Haiku generates contextual responses  
✅ Multi-language detection works for EN/MS/ZH  
✅ Conversation history stored in PostgreSQL  
✅ WAHA send succeeds with retry logic  
✅ All errors logged to structured JSON files and database  
✅ Failed messages stored for manual review  
✅ No user-facing errors; graceful fallbacks for all scenarios  

---

## Testing Checklist

- [ ] Test webhook with sample WAHA payload
- [ ] Test with known user (verify DB lookup)
- [ ] Test with unknown user (verify graceful handling)
- [ ] Test with FAQ match question (EN, MS, ZH)
- [ ] Test with out-of-scope question
- [ ] Test with ambiguous question (agent asks for clarification)
- [ ] Test WAHA send success path
- [ ] Test WAHA send failure → retry → success
- [ ] Test WAHA send failure → retries exhausted → fallback
- [ ] Test PostgreSQL connection failure scenario
- [ ] Test FAQ file missing scenario
- [ ] Test Claude API timeout
- [ ] Verify conversation history stored correctly
- [ ] Verify structured logs written correctly
- [ ] Verify failed messages table populated on send failure
- [ ] Test multi-language responses (EN, MS, ZH)

---

## Deployment Checklist

- [ ] Configure all environment variables in n8n
- [ ] Create all PostgreSQL tables
- [ ] Upload FAQ_answers.json to correct location
- [ ] Test webhook URL is accessible from WAHA
- [ ] Set up log file rotation (optional: daily or by size)
- [ ] Configure alert/notification for failed messages
- [ ] Enable n8n workflow error notifications
- [ ] Do a full end-to-end test with real WAHA instance
- [ ] Monitor first 50 executions for errors
- [ ] Set up monitoring dashboard for key metrics

---

## Future Enhancements

- [ ] Add conversation feedback mechanism (user thumbs up/down)
- [ ] Implement vector embeddings for even better semantic matching
- [ ] Add analytics dashboard for FAQ usage patterns
- [ ] Auto-learn new FAQs from frequent out-of-scope questions
- [ ] Support for file attachments in WhatsApp
- [ ] Handoff to human support queue for complex questions
- [ ] Multi-agent architecture (specialized agents per category)

---

## Notes for Claude Code

When building this workflow:

1. **Start with the trigger** - test WAHA webhook connectivity first
2. **Add database queries early** - verify all DB connections before proceeding
3. **Load FAQ and test with Claude** - use n8n Claude node; test semantic matching with 5-10 sample questions
4. **Implement retry logic carefully** - use n8n's native retry or a Code node for exponential backoff
5. **Logging is critical** - implement structured logging EARLY so you can debug issues
6. **Test error paths** - artificially trigger each error scenario to verify fallback behavior
7. **Keep it modular** - consider using n8n sub-workflows for complex logic (DB queries, AI agent, logging)

---

## Contact & Questions

If Claude Code needs clarification on:
- Specific node configuration
- Database schema
- Claude Haiku system prompt refinement
- n8n-specific syntax or node parameters

Ask directly in the workflow comments or create a detailed issue log.

Good luck building! 🚀