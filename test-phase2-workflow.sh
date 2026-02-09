#!/bin/bash

# Phase 2 WhatsApp FAQ Bot - Test Suite
# Tests: User validation, conversation history, database logging

set -e

WEBHOOK_URL="http://localhost:5678/webhook/whatsapp-listener-faq"
KNOWN_USER="60198775521@c.us"
UNKNOWN_USER="60123445521@c.us"

# Generate timestamped log file
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
LOG_DIR="/Users/najmie/n8n/test-logs"
LOG_FILE="$LOG_DIR/phase2-workflow-test-$TIMESTAMP.log"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log to both console and file (without color codes in file)
log() {
    echo -e "$1" | tee -a >(sed 's/\x1b\[[0-9;]*m//g' >> "$LOG_FILE")
}

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Initialize log file
echo "======================================" > "$LOG_FILE"
echo "Phase 2 WhatsApp FAQ Bot - Test Suite" >> "$LOG_FILE"
echo "Timestamp: $(date)" >> "$LOG_FILE"
echo "Webhook URL: $WEBHOOK_URL" >> "$LOG_FILE"
echo "======================================" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

log "======================================"
log "Phase 2 WhatsApp FAQ Bot - Test Suite"
log "Timestamp: $(date)"
log "======================================"
log ""
log "${YELLOW}Log file: $LOG_FILE${NC}"
log ""

# Test 1: Known User - First Message
log "${BLUE}Test 1: Known user - First FAQ question${NC}"
log "Testing: User validation + FAQ match"
log ""
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "'"$KNOWN_USER"'",
      "fromMe": false,
      "body": "Is trademark registration compulsory?",
      "timestamp": 1707400001
    }
  }' -w "\nHTTP Status: %{http_code}\n\n" 2>&1 | tee -a "$LOG_FILE"

sleep 3

# Test 2: Known User - Follow-up Message (tests conversation history)
log "${BLUE}Test 2: Known user - Follow-up question (conversation history test)${NC}"
log "Testing: Multi-turn conversation with history context"
log ""
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "'"$KNOWN_USER"'",
      "fromMe": false,
      "body": "How much does it cost?",
      "timestamp": 1707400002
    }
  }' -w "\nHTTP Status: %{http_code}\n\n" 2>&1 | tee -a "$LOG_FILE"

sleep 3

# Test 3: Known User - Third Message (tests full history)
log "${BLUE}Test 3: Known user - Third message (full history test)${NC}"
log "Testing: Last 5 messages history retrieval"
log ""
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "'"$KNOWN_USER"'",
      "fromMe": false,
      "body": "How long will the process take?",
      "timestamp": 1707400003
    }
  }' -w "\nHTTP Status: %{http_code}\n\n" 2>&1 | tee -a "$LOG_FILE"

sleep 3

# Test 4: Unknown User - FAQ Question
log "${BLUE}Test 4: Unknown user - FAQ question${NC}"
log "Testing: Workflow continues normally for unknown users"
log ""
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "'"$UNKNOWN_USER"'",
      "fromMe": false,
      "body": "What is a trademark?",
      "timestamp": 1707400004
    }
  }' -w "\nHTTP Status: %{http_code}\n\n" 2>&1 | tee -a "$LOG_FILE"

sleep 3

# Test 5: Multi-language - Malay (tests language detection)
log "${BLUE}Test 5: Multi-language - Malay question${NC}"
log "Testing: Language detection + user context"
log ""
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "'"$KNOWN_USER"'",
      "fromMe": false,
      "body": "Apakah kos untuk pendaftaran tanda dagangan?",
      "timestamp": 1707400005
    }
  }' -w "\nHTTP Status: %{http_code}\n\n" 2>&1 | tee -a "$LOG_FILE"

sleep 3

# Test 6: Out-of-scope Question
log "${BLUE}Test 6: Out-of-scope question${NC}"
log "Testing: Fallback response for non-FAQ questions"
log ""
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "'"$KNOWN_USER"'",
      "fromMe": false,
      "body": "What is the weather today?",
      "timestamp": 1707400006
    }
  }' -w "\nHTTP Status: %{http_code}\n\n" 2>&1 | tee -a "$LOG_FILE"

log ""
log "${GREEN}======================================"
log "All tests completed!"
log "======================================${NC}"
log ""
log "${YELLOW}Next steps:${NC}"
log "1. Check n8n Executions tab to verify all 6 tests ran successfully"
log "2. Run the database verification script: ./verify-phase2-database.sh"
log "3. Verify conversation history in execution #3 (should show previous 2 messages)"
log ""
log "${GREEN}📁 Full log saved to: $LOG_FILE${NC}"
log ""
