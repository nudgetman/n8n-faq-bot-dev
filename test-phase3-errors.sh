#!/bin/bash

# Phase 3 Error Handling Test Script
# Tests WAHA retry logic and failed message queue

set -e

WEBHOOK_URL="http://localhost:5678/webhook/whatsapp-listener-faq"
KNOWN_USER="60198775521@c.us"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Generate timestamped log file
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
LOG_DIR="/Users/najmie/n8n/test-logs"
LOG_FILE="$LOG_DIR/phase3-error-test-$TIMESTAMP.log"
mkdir -p "$LOG_DIR"

log() {
    echo -e "$1" | tee -a >(sed 's/\x1b\[[0-9;]*m//g' >> "$LOG_FILE")
}

echo "Phase 3 Error Handling Tests - $(date)" > "$LOG_FILE"

log "${BLUE}=========================================="
log "Phase 3: Error Handling & Resilience Tests"
log "==========================================${NC}"
log ""
log "${YELLOW}Log file: $LOG_FILE${NC}"
log ""

# ============================================================
# Test 1: Normal success (baseline with retry node)
# ============================================================
log "${BLUE}Test 1: Normal success (verifies retry node works)${NC}"
log "Expected: success, sent=true, retryCount=0"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "{\"event\":\"message\",\"payload\":{\"from\":\"$KNOWN_USER\",\"body\":\"What is a trademark?\",\"id\":{\"id\":\"phase3-test1\"},\"fromMe\":false,\"timestamp\":$(date +%s)},\"session\":\"default\"}")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)
log "Response: $BODY (HTTP $HTTP_CODE)"
log ""

# ============================================================
# Test 2: WAHA failure - stop WAHA, send message, verify failed_messages
# ============================================================
log "${BLUE}Test 2: WAHA failure with retry exhaustion${NC}"
log "Step 2a: Stopping WAHA container..."
docker stop waha 2>&1 | tee -a "$LOG_FILE" || true
sleep 2

log "Step 2b: Sending message (WAHA is down - will retry 3 times)..."
log "Expected: failed_after_retries, sent=false"
log "${YELLOW}(This will take ~14s due to retry delays: 2s + 4s + 8s)${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" --max-time 60 -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "{\"event\":\"message\",\"payload\":{\"from\":\"$KNOWN_USER\",\"body\":\"How much does registration cost?\",\"id\":{\"id\":\"phase3-test2\"},\"fromMe\":false,\"timestamp\":$(date +%s)},\"session\":\"default\"}")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)
log "Response: $BODY (HTTP $HTTP_CODE)"
log ""

# ============================================================
# Test 3: Verify failed_messages table
# ============================================================
log "${BLUE}Test 3: Check failed_messages table${NC}"
log "Expected: 1 record with retry_count >= 1"
docker exec postgres psql -U faqbot -d faqbot -c "
SELECT
  chat_id,
  LEFT(response_text, 60) as response,
  failure_reason,
  retry_count,
  created_at
FROM failed_messages
ORDER BY created_at DESC
LIMIT 3;
" 2>&1 | tee -a "$LOG_FILE"
log ""

# ============================================================
# Test 4: Verify execution_logs shows failed status
# ============================================================
log "${BLUE}Test 4: Check execution_logs for failed status${NC}"
log "Expected: 1 record with status='failed_after_retries'"
docker exec postgres psql -U faqbot -d faqbot -c "
SELECT
  status,
  chat_id,
  execution_data->>'retryCount' as retry_count,
  execution_data->>'errorReason' as error_reason,
  created_at
FROM execution_logs
WHERE status = 'failed_after_retries'
ORDER BY created_at DESC
LIMIT 3;
" 2>&1 | tee -a "$LOG_FILE"
log ""

# ============================================================
# Test 5: Verify conversation_history has sent=false
# ============================================================
log "${BLUE}Test 5: Check conversation_history for unsent messages${NC}"
log "Expected: At least 1 record with sent=false"
docker exec postgres psql -U faqbot -d faqbot -c "
SELECT
  chat_id,
  sent,
  LEFT(user_message, 40) as message,
  LEFT(bot_response, 40) as response,
  created_at
FROM conversation_history
WHERE sent = false
ORDER BY created_at DESC
LIMIT 3;
" 2>&1 | tee -a "$LOG_FILE"
log ""

# ============================================================
# Test 6: Restart WAHA and verify recovery
# ============================================================
log "${BLUE}Test 6: Restart WAHA and verify normal operation resumes${NC}"
log "Step 6a: Starting WAHA container..."
docker run -d --name waha -p 3000:3000 -e WHATSAPP_API_KEY=06db31514cc34e11a51b556678ba03c2 devlikeapro/waha:arm 2>&1 | tee -a "$LOG_FILE" || true
log "Waiting 15 seconds for WAHA to initialize..."
sleep 15
# Start WAHA session
curl -s -X POST http://localhost:3000/api/sessions/start -H "Content-Type: application/json" -H "X-Api-Key: 06db31514cc34e11a51b556678ba03c2" -d '{"name":"default"}' > /dev/null 2>&1
sleep 10

log "Step 6b: Sending message (WAHA should be back up)..."
RESPONSE=$(curl -s -w "\n%{http_code}" --max-time 30 -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "{\"event\":\"message\",\"payload\":{\"from\":\"$KNOWN_USER\",\"body\":\"What documents do I need?\",\"id\":{\"id\":\"phase3-test6\"},\"fromMe\":false,\"timestamp\":$(date +%s)},\"session\":\"default\"}")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)
log "Response: $BODY (HTTP $HTTP_CODE)"
log ""

# ============================================================
# Summary
# ============================================================
log "${GREEN}=========================================="
log "Phase 3 Error Test Summary"
log "==========================================${NC}"
log ""

CONV_COUNT=$(docker exec postgres psql -U faqbot -d faqbot -t -c "SELECT COUNT(*) FROM conversation_history;")
LOG_COUNT=$(docker exec postgres psql -U faqbot -d faqbot -t -c "SELECT COUNT(*) FROM execution_logs;")
FAILED_COUNT=$(docker exec postgres psql -U faqbot -d faqbot -t -c "SELECT COUNT(*) FROM failed_messages;")
SENT_TRUE=$(docker exec postgres psql -U faqbot -d faqbot -t -c "SELECT COUNT(*) FROM conversation_history WHERE sent = true;")
SENT_FALSE=$(docker exec postgres psql -U faqbot -d faqbot -t -c "SELECT COUNT(*) FROM conversation_history WHERE sent = false;")
SUCCESS_LOGS=$(docker exec postgres psql -U faqbot -d faqbot -t -c "SELECT COUNT(*) FROM execution_logs WHERE status = 'success';")
FAILED_LOGS=$(docker exec postgres psql -U faqbot -d faqbot -t -c "SELECT COUNT(*) FROM execution_logs WHERE status = 'failed_after_retries';")

log "Database Records:"
log "  conversation_history: $CONV_COUNT (sent=true: $SENT_TRUE, sent=false: $SENT_FALSE)"
log "  execution_logs: $LOG_COUNT (success: $SUCCESS_LOGS, failed: $FAILED_LOGS)"
log "  failed_messages: $FAILED_COUNT"
log ""
log "${YELLOW}What to verify:${NC}"
log "  Test 1: Response=success, conversation sent=true"
log "  Test 2: Response=failed_after_retries"
log "  Test 3: failed_messages has 1+ record"
log "  Test 4: execution_logs has failed_after_retries status"
log "  Test 5: conversation_history has sent=false record"
log "  Test 6: Response=success (WAHA recovered)"
log ""
log "${GREEN}Log saved to: $LOG_FILE${NC}"
