#!/bin/bash

# Test script for WhatsApp FAQ Bot - Phase 1

echo "=== WhatsApp FAQ Bot - Test Suite ==="
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Webhook URL
WEBHOOK_URL="http://localhost:5678/webhook/whatsapp-faq"

echo -e "${YELLOW}Test 1: English FAQ Question${NC}"
echo "Question: Is trademark registration compulsory?"
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "60123445521@c.us",
      "fromMe": false,
      "body": "Is trademark registration compulsory?",
      "timestamp": 1707200000
    }
  }'
echo -e "\n"

sleep 2

echo -e "${YELLOW}Test 2: Malay FAQ Question${NC}"
echo "Question: Apakah kos untuk pendaftaran tanda dagangan?"
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "60123445521@c.us",
      "fromMe": false,
      "body": "Apakah kos untuk pendaftaran tanda dagangan?",
      "timestamp": 1707200100
    }
  }'
echo -e "\n"

sleep 2

echo -e "${YELLOW}Test 3: Chinese FAQ Question${NC}"
echo "Question: 商标注册需要多长时间？"
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "60123445521@c.us",
      "fromMe": false,
      "body": "商标注册需要多长时间？",
      "timestamp": 1707200200
    }
  }'
echo -e "\n"

sleep 2

echo -e "${YELLOW}Test 4: Out-of-scope Question${NC}"
echo "Question: What is the weather today?"
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "60123445521@c.us",
      "fromMe": false,
      "body": "What is the weather today?",
      "timestamp": 1707200300
    }
  }'
echo -e "\n"

sleep 2

echo -e "${YELLOW}Test 5: Self-message (should be filtered)${NC}"
echo "Question: This is my own message"
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "60123445521@c.us",
      "fromMe": true,
      "body": "This is my own message",
      "timestamp": 1707200400
    }
  }'
echo -e "\n"

sleep 2

echo -e "${YELLOW}Test 6: Empty message (should be filtered)${NC}"
echo "Question: (empty)"
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "session": "default",
    "payload": {
      "from": "60123445521@c.us",
      "fromMe": false,
      "body": "",
      "timestamp": 1707200500
    }
  }'
echo -e "\n"

echo -e "${GREEN}=== Test Suite Complete ===${NC}"
echo "Check n8n executions at: http://localhost:5678"
echo "Username: choowie"
echo "Password: Nudget01?"
