#!/usr/bin/env python3
"""Phase 3: Deploy Error Handling & Resilience changes to n8n workflow.

Adds 5 new nodes, modifies 4 existing nodes, updates connections.
Pushes changes via n8n REST API.
"""

import json
import os
import requests

# Load API key from .env
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
env_vars = {}
with open(ENV_PATH) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env_vars[k] = v

API_URL = "http://localhost:5678/api/v1"
API_KEY = env_vars["N8N_API_KEY"]
WAHA_API_KEY = env_vars["WAHA_API_KEY"]
WORKFLOW_ID = "F3i-SoCq4WIvV5VTGOOMK"
HEADERS = {"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}

# ============================================================
# 1. Fetch current workflow
# ============================================================
print("1. Fetching current workflow...")
resp = requests.get(f"{API_URL}/workflows/{WORKFLOW_ID}", headers=HEADERS)
assert resp.status_code == 200, f"Failed to fetch workflow: {resp.status_code}"
workflow = resp.json()
print(f"   Got: {workflow['name']} ({len(workflow['nodes'])} nodes)")

nodes_by_name = {n["name"]: n for n in workflow["nodes"]}
connections = workflow["connections"]

# ============================================================
# 2. Remove Send_WAHA_Response node
# ============================================================
print("\n2. Removing Send_WAHA_Response (will be replaced)...")
workflow["nodes"] = [n for n in workflow["nodes"] if n["name"] != "Send_WAHA_Response"]
print("   Removed.")

# ============================================================
# 3. Add Send_WAHA_With_Retry (Code node)
# ============================================================
print("\n3. Adding Send_WAHA_With_Retry node...")

send_retry_code = f"""// Send WAHA response with exponential backoff retry
const userContext = $node["Set_User_Context"].json;
const aiResponse = $node["Extract_AI_Response"].json;

const wahaUrl = 'http://host.docker.internal:3000/api/sendText';
const wahaApiKey = '{WAHA_API_KEY}';
const payload = {{
  session: userContext.session || 'default',
  chatId: userContext.fromNumber,
  text: aiResponse.responseText
}};

const maxRetries = 3;
const backoffDelays = [2000, 4000, 8000]; // 2s, 4s, 8s
let lastError = null;
let retryCount = 0;

for (let attempt = 0; attempt <= maxRetries; attempt++) {{
  if (attempt > 0) {{
    await new Promise(r => setTimeout(r, backoffDelays[attempt - 1] || 8000));
  }}
  try {{
    const response = await $helpers.httpRequest({{
      method: 'POST',
      url: wahaUrl,
      headers: {{
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + wahaApiKey
      }},
      body: payload,
      json: true,
      timeout: 10000
    }});
    // Success
    const wahaMessageId = response.id || response.messageId || null;
    return [{{
      json: {{
        ...userContext,
        responseText: aiResponse.responseText,
        sent: true,
        retryCount: attempt,
        wahaMessageId,
        errorReason: null
      }}
    }}];
  }} catch (error) {{
    lastError = error.message || String(error);
    retryCount = attempt + 1;
    // Don't retry 4xx client errors
    if (error.statusCode && error.statusCode >= 400 && error.statusCode < 500) {{
      break;
    }}
  }}
}}

// All retries exhausted
return [{{
  json: {{
    ...userContext,
    responseText: aiResponse.responseText,
    sent: false,
    retryCount,
    wahaMessageId: null,
    errorReason: lastError
  }}
}}];"""

send_retry_node = {
    "parameters": {"jsCode": send_retry_code},
    "id": "send-waha-retry-001",
    "name": "Send_WAHA_With_Retry",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [1328, 128],
}
workflow["nodes"].append(send_retry_node)
print("   Added Send_WAHA_With_Retry at [1328, 128]")

# ============================================================
# 4. Add Check_Send_Status (If node)
# ============================================================
print("\n4. Adding Check_Send_Status node...")

check_send_node = {
    "parameters": {
        "conditions": {
            "options": {
                "caseSensitive": True,
                "leftValue": "",
                "typeValidation": "strict",
            },
            "conditions": [
                {
                    "id": "send-status",
                    "leftValue": "={{ $json.sent }}",
                    "rightValue": True,
                    "operator": {"type": "boolean", "operation": "equals"},
                }
            ],
            "combinator": "and",
        },
        "options": {},
    },
    "id": "check-send-status-001",
    "name": "Check_Send_Status",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.2,
    "position": [1552, 128],
}
workflow["nodes"].append(check_send_node)
print("   Added Check_Send_Status at [1552, 128]")

# ============================================================
# 5. Add Prepare_Failed_Message (Code node)
# ============================================================
print("\n5. Adding Prepare_Failed_Message node...")

prepare_failed_code = """// Prepare data for failed_messages table insert
const items = $input.all();
const item = items[0].json;

return [{
  json: {
    chat_id: item.fromNumber,
    user_id: item.userId || null,
    message_payload: JSON.stringify({
      session: item.session,
      chatId: item.fromNumber,
      userMessage: item.messageBody
    }),
    response_text: item.responseText,
    failure_reason: item.errorReason || 'Unknown error after retries',
    retry_count: item.retryCount || 3,
    last_retry_at: new Date().toISOString()
  }
}];"""

prepare_failed_node = {
    "parameters": {"jsCode": prepare_failed_code},
    "id": "prepare-failed-msg-001",
    "name": "Prepare_Failed_Message",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [1776, 384],
}
workflow["nodes"].append(prepare_failed_node)
print("   Added Prepare_Failed_Message at [1776, 384]")

# ============================================================
# 6. Add DB_Store_Failed_Message (Postgres insert node)
# ============================================================
print("\n6. Adding DB_Store_Failed_Message node...")

db_failed_node = {
    "parameters": {
        "operation": "insert",
        "schema": {"__rl": True, "mode": "name", "value": "public"},
        "table": {"__rl": True, "mode": "name", "value": "failed_messages"},
        "columns": {"mappingMode": "autoMapInputData", "value": None, "matchingColumns": []},
        "options": {},
    },
    "id": "db-store-failed-001",
    "name": "DB_Store_Failed_Message",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.6,
    "position": [2000, 384],
    "credentials": {"postgres": {"id": "3expq1dbaLHM9U77", "name": "PostgreSQL account"}},
    "alwaysOutputData": True,
    "onError": "continueRegularOutput",
}
workflow["nodes"].append(db_failed_node)
print("   Added DB_Store_Failed_Message at [2000, 384]")

# ============================================================
# 7. Add Build_Error_Log (Code node)
# ============================================================
print("\n7. Adding Build_Error_Log node...")

build_error_log_code = """// Build execution log entry for failed sends
const items = $input.all();
const userContext = $node["Set_User_Context"].json;
const sendResult = $node["Send_WAHA_With_Retry"].json;
const faqData = $node["Merge_History_Context"].json;

for (const item of items) {
  item.json = {
    execution_id: $execution.id,
    workflow_name: 'whatsapp-faq-bot',
    chat_id: userContext.fromNumber,
    user_id: userContext.userId || null,
    phone_number: userContext.fromNumber,
    status: 'failed_after_retries',
    execution_data: JSON.stringify({
      isKnownUser: userContext.isKnownUser,
      userName: userContext.userName,
      userPreferredLanguage: userContext.userPreferredLanguage,
      faqLoaded: faqData.faqLoaded,
      historyCount: faqData.historyCount,
      retryCount: sendResult.retryCount,
      errorReason: sendResult.errorReason,
      executionTime: new Date().toISOString()
    })
  };
}
return items;"""

build_error_log_node = {
    "parameters": {"jsCode": build_error_log_code},
    "id": "build-error-log-001",
    "name": "Build_Error_Log",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [2224, 384],
}
workflow["nodes"].append(build_error_log_node)
print("   Added Build_Error_Log at [2224, 384]")

# ============================================================
# 8. Modify Extract_AI_Response (Set → Code node)
# ============================================================
print("\n8. Converting Extract_AI_Response to Code node with error fallback...")

extract_ai_code = """// Extract AI response with error fallback
const items = $input.all();
const item = items[0];

let responseText = '';
let aiFailed = false;

try {
  responseText = item.json.text || item.json.response || '';
  if (!responseText || responseText.trim() === '') {
    throw new Error('Empty AI response');
  }
} catch (e) {
  aiFailed = true;
  responseText = "I'm sorry, I'm experiencing a temporary issue processing your request. Please try again in a moment, or contact MyIPO at ipmalaysia@myipo.gov.my for assistance.";
}

const userContext = $node["Set_User_Context"].json;

return [{
  json: {
    responseText,
    aiFailed,
    session: userContext.session || 'default',
    chatId: userContext.fromNumber
  }
}];"""

# Find and replace Extract_AI_Response node
for i, node in enumerate(workflow["nodes"]):
    if node["name"] == "Extract_AI_Response":
        workflow["nodes"][i] = {
            "parameters": {"jsCode": extract_ai_code},
            "id": node["id"],
            "name": "Extract_AI_Response",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": node["position"],
        }
        print("   Converted to Code node with AI error fallback")
        break

# ============================================================
# 9. Modify AI_FAQ_Matcher - add onError
# ============================================================
print("\n9. Adding onError to AI_FAQ_Matcher...")

for node in workflow["nodes"]:
    if node["name"] == "AI_FAQ_Matcher":
        node["onError"] = "continueRegularOutput"
        print("   Set onError: continueRegularOutput")
        break

# ============================================================
# 10. Modify Build_Execution_Log - include retry info
# ============================================================
print("\n10. Updating Build_Execution_Log with retry info...")

build_exec_log_code = """// Build execution log object with retry info
const items = $input.all();
const userContext = $node["Set_User_Context"].json;
const faqData = $node["Merge_History_Context"].json;
const aiResponse = $node["Extract_AI_Response"].json;
const sendResult = $node["Send_WAHA_With_Retry"].json;

for (const item of items) {
  item.json = {
    execution_id: $execution.id,
    workflow_name: 'whatsapp-faq-bot',
    chat_id: userContext.fromNumber,
    user_id: userContext.userId || null,
    phone_number: userContext.fromNumber,
    status: 'success',
    execution_data: JSON.stringify({
      isKnownUser: userContext.isKnownUser,
      userName: userContext.userName,
      userPreferredLanguage: userContext.userPreferredLanguage,
      faqLoaded: faqData.faqLoaded,
      historyCount: faqData.historyCount,
      messageLength: userContext.messageBody ? userContext.messageBody.length : 0,
      responseLength: aiResponse.responseText ? aiResponse.responseText.length : 0,
      aiFailed: aiResponse.aiFailed || false,
      retryCount: sendResult.retryCount || 0,
      wahaMessageId: sendResult.wahaMessageId || null,
      executionTime: new Date().toISOString()
    })
  };
}
return items;"""

for node in workflow["nodes"]:
    if node["name"] == "Build_Execution_Log":
        node["parameters"]["jsCode"] = build_exec_log_code
        print("   Updated with retry info fields")
        break

# ============================================================
# 11. Modify Prepare_Store_Data - dynamic sent field
# ============================================================
print("\n11. Updating Prepare_Store_Data with dynamic sent field...")

prepare_store_code = """// Prepare data for DB_Store_Conversation
const items = $input.all();
const userContext = $node["Set_User_Context"].json;
const aiResponse = $node["Extract_AI_Response"].json;
const sendResult = $node["Send_WAHA_With_Retry"].json;

for (const item of items) {
  item.json = {
    chat_id: userContext.fromNumber,
    user_id: userContext.userId || null,
    user_message: userContext.messageBody,
    bot_response: aiResponse.responseText,
    detected_language: 'en',
    faq_matched: true,
    sent: sendResult.sent || false
  };
}
return items;"""

for node in workflow["nodes"]:
    if node["name"] == "Prepare_Store_Data":
        node["parameters"]["jsCode"] = prepare_store_code
        print("   Updated with dynamic sent field")
        break

# ============================================================
# 12. Update connections
# ============================================================
print("\n12. Updating connections...")

# Remove old Send_WAHA_Response connections
if "Send_WAHA_Response" in connections:
    del connections["Send_WAHA_Response"]

# Extract_AI_Response → Send_WAHA_With_Retry
connections["Extract_AI_Response"] = {
    "main": [[{"node": "Send_WAHA_With_Retry", "type": "main", "index": 0}]]
}

# Send_WAHA_With_Retry → Check_Send_Status
connections["Send_WAHA_With_Retry"] = {
    "main": [[{"node": "Check_Send_Status", "type": "main", "index": 0}]]
}

# Check_Send_Status → [TRUE] Prepare_Store_Data, [FALSE] Prepare_Failed_Message
connections["Check_Send_Status"] = {
    "main": [
        [{"node": "Prepare_Store_Data", "type": "main", "index": 0}],
        [{"node": "Prepare_Failed_Message", "type": "main", "index": 0}],
    ]
}

# Prepare_Failed_Message → DB_Store_Failed_Message
connections["Prepare_Failed_Message"] = {
    "main": [[{"node": "DB_Store_Failed_Message", "type": "main", "index": 0}]]
}

# DB_Store_Failed_Message → Build_Error_Log
connections["DB_Store_Failed_Message"] = {
    "main": [[{"node": "Build_Error_Log", "type": "main", "index": 0}]]
}

# Build_Error_Log → DB_Log_Execution
connections["Build_Error_Log"] = {
    "main": [[{"node": "DB_Log_Execution", "type": "main", "index": 0}]]
}

# Keep existing: Prepare_Store_Data → DB_Store_Conversation → Build_Execution_Log → DB_Log_Execution → Webhook_Response
print("   Connections updated:")
print("   Extract_AI_Response → Send_WAHA_With_Retry → Check_Send_Status")
print("   Check_Send_Status [TRUE] → Prepare_Store_Data (existing success path)")
print("   Check_Send_Status [FALSE] → Prepare_Failed_Message → DB_Store_Failed_Message → Build_Error_Log → DB_Log_Execution")

# ============================================================
# 13. Shift existing nodes right to make room
# ============================================================
print("\n13. Adjusting node positions...")

# Prepare_Store_Data needs to shift right (was at [1440, 128])
for node in workflow["nodes"]:
    if node["name"] == "Prepare_Store_Data":
        node["position"] = [1776, 128]
        print(f"   Prepare_Store_Data → [1776, 128]")
    elif node["name"] == "DB_Store_Conversation":
        node["position"] = [2000, 128]
        print(f"   DB_Store_Conversation → [2000, 128]")
    elif node["name"] == "Build_Execution_Log":
        node["position"] = [2224, 128]
        print(f"   Build_Execution_Log → [2224, 128]")
    elif node["name"] == "DB_Log_Execution":
        node["position"] = [2448, 128]
        print(f"   DB_Log_Execution → [2448, 128]")
    elif node["name"] == "Send_Fallback_Error":
        node["position"] = [2448, 512]
        print(f"   Send_Fallback_Error → [2448, 512]")
    elif node["name"] == "Webhook_Response":
        node["position"] = [2672, 256]
        print(f"   Webhook_Response → [2672, 256]")

# ============================================================
# 14. Push updated workflow
# ============================================================
print(f"\n14. Pushing updated workflow ({len(workflow['nodes'])} nodes)...")

update_payload = {
    "name": workflow["name"],
    "nodes": workflow["nodes"],
    "connections": connections,
    "settings": {"executionOrder": "v1"},
}

resp = requests.put(
    f"{API_URL}/workflows/{WORKFLOW_ID}",
    headers=HEADERS,
    json=update_payload,
)

if resp.status_code == 200:
    result = resp.json()
    print(f"   SUCCESS! Updated: {result['name']} ({len(result['nodes'])} nodes)")
else:
    print(f"   FAILED! Status: {resp.status_code}")
    print(f"   Response: {resp.text[:1000]}")
    exit(1)

# ============================================================
# 15. Activate workflow
# ============================================================
print("\n15. Activating workflow...")
resp = requests.post(f"{API_URL}/workflows/{WORKFLOW_ID}/activate", headers=HEADERS)
if resp.status_code == 200:
    print("   Workflow activated!")
else:
    print(f"   Status: {resp.status_code} - {resp.text[:200]}")

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 60)
print("PHASE 3 DEPLOYMENT COMPLETE")
print("=" * 60)
print("New nodes added (5):")
print("  1. Send_WAHA_With_Retry - Retry logic with exponential backoff")
print("  2. Check_Send_Status - Routes success/failure paths")
print("  3. Prepare_Failed_Message - Prepares failed_messages data")
print("  4. DB_Store_Failed_Message - Stores in failed_messages table")
print("  5. Build_Error_Log - Builds error execution log")
print("Modified nodes (4):")
print("  1. Extract_AI_Response - Now handles AI errors with fallback")
print("  2. AI_FAQ_Matcher - Added onError: continueRegularOutput")
print("  3. Build_Execution_Log - Includes retry info")
print("  4. Prepare_Store_Data - Dynamic sent field")
print("=" * 60)
