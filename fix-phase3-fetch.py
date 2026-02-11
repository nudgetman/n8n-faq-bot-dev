#!/usr/bin/env python3
"""Fix Send_WAHA_With_Retry to use fetch() instead of $helpers.httpRequest()."""

import json
import os
import requests

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

# 1. Fetch workflow
print("1. Fetching workflow...")
resp = requests.get(f"{API_URL}/workflows/{WORKFLOW_ID}", headers=HEADERS)
workflow = resp.json()
print(f"   Got {len(workflow['nodes'])} nodes")

# 2. Update Send_WAHA_With_Retry code to use fetch()
print("2. Updating Send_WAHA_With_Retry to use fetch()...")

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
const helpers = this.helpers;

for (let attempt = 0; attempt <= maxRetries; attempt++) {{
  if (attempt > 0) {{
    await new Promise(r => setTimeout(r, backoffDelays[attempt - 1] || 8000));
  }}
  try {{
    const response = await helpers.httpRequest({{
      method: 'POST',
      url: wahaUrl,
      headers: {{
        'Content-Type': 'application/json',
        'X-Api-Key': wahaApiKey
      }},
      body: payload,
      json: true,
      timeout: 10000
    }});

    // Success - httpRequest returns parsed JSON directly
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
    const statusCode = error.statusCode || error.httpCode || 0;
    if (statusCode >= 400 && statusCode < 500) {{
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

for node in workflow["nodes"]:
    if node["name"] == "Send_WAHA_With_Retry":
        node["parameters"]["jsCode"] = send_retry_code
        print("   Updated code to use fetch()")
        break

# 3. Push
print("3. Pushing updated workflow...")
update_payload = {
    "name": workflow["name"],
    "nodes": workflow["nodes"],
    "connections": workflow["connections"],
    "settings": {"executionOrder": "v1"},
}
resp = requests.put(f"{API_URL}/workflows/{WORKFLOW_ID}", headers=HEADERS, json=update_payload)
if resp.status_code == 200:
    print(f"   SUCCESS! {len(resp.json()['nodes'])} nodes")
else:
    print(f"   FAILED: {resp.status_code} - {resp.text[:500]}")
    exit(1)

# 4. Activate
print("4. Activating...")
resp = requests.post(f"{API_URL}/workflows/{WORKFLOW_ID}/activate", headers=HEADERS)
print(f"   {'Activated!' if resp.status_code == 200 else f'Status: {resp.status_code}'}")
print("\nDone! Send_WAHA_With_Retry now uses fetch() API.")
