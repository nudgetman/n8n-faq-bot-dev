#!/usr/bin/env python3
"""Diagnostic: Check what HTTP methods are available in n8n Code node sandbox."""
import json, os, requests

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
WORKFLOW_ID = "F3i-SoCq4WIvV5VTGOOMK"
HEADERS = {"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"}

resp = requests.get(f"{API_URL}/workflows/{WORKFLOW_ID}", headers=HEADERS)
w = resp.json()

diag_code = r"""// Diagnostic 2: check available HTTP methods
const available = [];

// Check this.helpers methods
try {
  const helperKeys = Object.keys(this.helpers).sort();
  available.push('this.helpers keys: ' + helperKeys.join(','));
} catch(e) {
  available.push('this.helpers keys error: ' + e.message);
}

// Check this.helpers.httpRequest
try {
  available.push('this.helpers.httpRequest: ' + typeof this.helpers.httpRequest);
} catch(e) {
  available.push('this.helpers.httpRequest error: ' + e.message);
}

// Check this.helpers.request
try {
  available.push('this.helpers.request: ' + typeof this.helpers.request);
} catch(e) {
  available.push('this.helpers.request error: ' + e.message);
}

// Check require('http')
try {
  const http = require('http');
  available.push('require(http): ' + typeof http);
  available.push('http.request: ' + typeof http.request);
} catch(e) {
  available.push('require(http) error: ' + e.message);
}

// Check require('https')
try {
  const https = require('https');
  available.push('require(https): ' + typeof https);
} catch(e) {
  available.push('require(https) error: ' + e.message);
}

const userContext = $node["Set_User_Context"].json;
const aiResponse = $node["Extract_AI_Response"].json;

return [{
  json: {
    ...userContext,
    responseText: aiResponse.responseText,
    sent: false,
    retryCount: 0,
    wahaMessageId: null,
    errorReason: 'DIAG2: ' + available.join(' | ')
  }
}];"""

for node in w["nodes"]:
    if node["name"] == "Send_WAHA_With_Retry":
        node["parameters"]["jsCode"] = diag_code
        break

payload = {
    "name": w["name"],
    "nodes": w["nodes"],
    "connections": w["connections"],
    "settings": {"executionOrder": "v1"},
}
resp = requests.put(f"{API_URL}/workflows/{WORKFLOW_ID}", headers=HEADERS, json=payload)
print(f"Push: {resp.status_code}")
resp = requests.post(f"{API_URL}/workflows/{WORKFLOW_ID}/activate", headers=HEADERS)
print(f"Activate: {resp.status_code}")
