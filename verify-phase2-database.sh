#!/bin/bash

# Phase 2 Database Verification Script
# Verifies that conversation_history and execution_logs are being populated

set -e

KNOWN_USER="60198775521@c.us"

# Generate timestamped log file
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
LOG_DIR="/Users/najmie/n8n/test-logs"
LOG_FILE="$LOG_DIR/phase2-verification-$TIMESTAMP.log"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log to both console and file (without color codes in file)
log() {
    echo -e "$1" | tee -a >(sed 's/\x1b\[[0-9;]*m//g' >> "$LOG_FILE")
}

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Initialize log file
echo "=========================================" > "$LOG_FILE"
echo "Phase 2 Database Verification" >> "$LOG_FILE"
echo "Timestamp: $(date)" >> "$LOG_FILE"
echo "=========================================" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

log "=========================================="
log "Phase 2 Database Verification"
log "Timestamp: $(date)"
log "=========================================="
log ""
log "${YELLOW}Log file: $LOG_FILE${NC}"
log ""

# Check 1: User lookup
log "${BLUE}Check 1: User in database${NC}"
docker exec postgres psql -U faqbot -d faqbot -c "
SELECT id, name, phone_number, status, preferred_language
FROM users
WHERE phone_number = '$KNOWN_USER';
" 2>&1 | tee -a "$LOG_FILE"
log ""

# Check 2: Conversation history count
log "${BLUE}Check 2: Conversation history records${NC}"
log "Expected: 5 records (tests 1, 2, 3, 5, 6 for known user)"
docker exec postgres psql -U faqbot -d faqbot -c "
SELECT COUNT(*) as total_conversations,
       COUNT(CASE WHEN faq_matched = true THEN 1 END) as faq_matched,
       COUNT(CASE WHEN faq_matched = false THEN 1 END) as no_match
FROM conversation_history
WHERE chat_id = '$KNOWN_USER';
" 2>&1 | tee -a "$LOG_FILE"
log ""

# Check 3: Last 5 conversations
log "${BLUE}Check 3: Last 5 conversation messages (ordered by time)${NC}"
docker exec postgres psql -U faqbot -d faqbot -c "
SELECT
  id,
  LEFT(user_message, 50) as message,
  faq_matched,
  detected_language,
  created_at
FROM conversation_history
WHERE chat_id = '$KNOWN_USER'
ORDER BY created_at DESC
LIMIT 5;
" 2>&1 | tee -a "$LOG_FILE"
log ""

# Check 4: Execution logs count
log "${BLUE}Check 4: Execution logs${NC}"
log "Expected: 6 records (one for each test)"
docker exec postgres psql -U faqbot -d faqbot -c "
SELECT COUNT(*) as total_executions,
       COUNT(CASE WHEN status = 'success' THEN 1 END) as successful,
       COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
FROM execution_logs;
" 2>&1 | tee -a "$LOG_FILE"
log ""

# Check 5: Execution log details (latest 3)
log "${BLUE}Check 5: Latest 3 execution logs (with metadata)${NC}"
docker exec postgres psql -U faqbot -d faqbot -c "
SELECT
  id,
  workflow_name,
  status,
  execution_data->>'from_number' as from_number,
  execution_data->>'user_name' as user_name,
  execution_data->>'is_known_user' as is_known_user,
  execution_data->>'faq_matched' as faq_matched,
  created_at
FROM execution_logs
ORDER BY created_at DESC
LIMIT 3;
" 2>&1 | tee -a "$LOG_FILE"
log ""

# Check 6: Verify JSONB structure of execution log
log "${BLUE}Check 6: Sample execution log JSONB structure${NC}"
docker exec postgres psql -U faqbot -d faqbot -c "
SELECT
  jsonb_pretty(execution_data) as execution_data_sample
FROM execution_logs
ORDER BY created_at DESC
LIMIT 1;
" 2>&1 | tee -a "$LOG_FILE"
log ""

# Check 7: Unknown user conversation (should exist but with no user context)
log "${BLUE}Check 7: Unknown user conversation${NC}"
log "Expected: 1 record for unknown user (60123445521@c.us)"
docker exec postgres psql -U faqbot -d faqbot -c "
SELECT
  chat_id,
  LEFT(user_message, 50) as message,
  faq_matched,
  detected_language
FROM conversation_history
WHERE chat_id = '60123445521@c.us';
" 2>&1 | tee -a "$LOG_FILE"
log ""

log "${GREEN}=========================================="
log "Database verification complete!"
log "==========================================${NC}"
log ""
log "${YELLOW}What to look for:${NC}"
log "✅ Known user found in 'users' table"
log "✅ 5+ conversation_history records for known user"
log "✅ 6+ execution_logs records (one per test)"
log "✅ JSONB structure includes: from_number, user_name, is_known_user, faq_matched"
log "✅ detected_language: en, ms (Malay test)"
log "✅ Unknown user has conversation record but no user context"
log ""
log "${GREEN}📁 Full log saved to: $LOG_FILE${NC}"
log ""
