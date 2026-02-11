#!/usr/bin/env python3
"""
Fix Phase 3: Move Prepare_Store_Data + DB_Store_Conversation BEFORE Check_Send_Status
so that conversation_history is always written (with sent=true or sent=false).

Old flow:
  Send_WAHA_With_Retry -> Check_Send_Status
    [output0/success] -> Prepare_Store_Data -> DB_Store_Conversation -> Build_Execution_Log
    [output1/failure] -> Prepare_Failed_Message -> DB_Store_Failed_Message -> Build_Error_Log

New flow:
  Send_WAHA_With_Retry -> Prepare_Store_Data -> DB_Store_Conversation -> Check_Send_Status
    [output0/success] -> Build_Execution_Log
    [output1/failure] -> Prepare_Failed_Message -> DB_Store_Failed_Message -> Build_Error_Log
"""

import json, os, sys, urllib.request, urllib.error

N8N_URL = "http://localhost:5678"
WORKFLOW_ID = "F3i-SoCq4WIvV5VTGOOMK"

def get_env():
    env = {}
    with open("/Users/najmie/n8n/.env") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

def api_request(method, path, data=None, api_key=None):
    url = N8N_URL + path
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("X-N8N-API-KEY", api_key)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()}")
        sys.exit(1)

def main():
    env = get_env()
    api_key = env.get("N8N_API_KEY")
    if not api_key:
        print("ERROR: N8N_API_KEY not found in .env")
        sys.exit(1)

    print("Fetching current workflow...")
    workflow = api_request("GET", f"/api/v1/workflows/{WORKFLOW_ID}", api_key=api_key)

    # Show current connections for verification
    conns = workflow["connections"]
    print("\nCurrent connections (relevant nodes):")
    for src in ["Send_WAHA_With_Retry", "Check_Send_Status", "DB_Store_Conversation", "Prepare_Store_Data"]:
        if src in conns:
            for out_type, out_list in conns[src].items():
                for idx, targets in enumerate(out_list):
                    for t in targets:
                        print(f"  {src}[{idx}] -> {t['node']}")

    print("\nApplying connection changes...")

    # 1. Remove: Send_WAHA_With_Retry -> Check_Send_Status
    #    Add:    Send_WAHA_With_Retry -> Prepare_Store_Data
    conns["Send_WAHA_With_Retry"] = {
        "main": [
            [{"node": "Prepare_Store_Data", "type": "main", "index": 0}]
        ]
    }
    print("  [1] Send_WAHA_With_Retry -> Prepare_Store_Data (was Check_Send_Status)")

    # Prepare_Store_Data -> DB_Store_Conversation already exists, no change needed
    print("  [2] Prepare_Store_Data -> DB_Store_Conversation (unchanged)")

    # 3. Remove: DB_Store_Conversation -> Build_Execution_Log
    #    Add:    DB_Store_Conversation -> Check_Send_Status
    conns["DB_Store_Conversation"] = {
        "main": [
            [{"node": "Check_Send_Status", "type": "main", "index": 0}]
        ]
    }
    print("  [3] DB_Store_Conversation -> Check_Send_Status (was Build_Execution_Log)")

    # 4. Change Check_Send_Status success path:
    #    Remove: Check_Send_Status[0] -> Prepare_Store_Data
    #    Add:    Check_Send_Status[0] -> Build_Execution_Log
    #    Keep:   Check_Send_Status[1] -> Prepare_Failed_Message
    conns["Check_Send_Status"] = {
        "main": [
            # output[0] = true/success
            [{"node": "Build_Execution_Log", "type": "main", "index": 0}],
            # output[1] = false/failure
            [{"node": "Prepare_Failed_Message", "type": "main", "index": 0}]
        ]
    }
    print("  [4] Check_Send_Status[0] -> Build_Execution_Log (was Prepare_Store_Data)")
    print("  [4] Check_Send_Status[1] -> Prepare_Failed_Message (unchanged)")

    # Prepare PUT payload (only allowed fields)
    payload = {
        "name": workflow["name"],
        "nodes": workflow["nodes"],
        "connections": conns,
        "settings": {"executionOrder": "v1"}
    }

    print("\nUploading updated workflow...")
    result = api_request("PUT", f"/api/v1/workflows/{WORKFLOW_ID}", data=payload, api_key=api_key)
    print(f"Success! Workflow updated: {result.get('name')}, nodes: {len(result.get('nodes', []))}")

    # Verify new connections
    print("\nNew connections (relevant nodes):")
    new_conns = result["connections"]
    for src in ["Send_WAHA_With_Retry", "Check_Send_Status", "DB_Store_Conversation", "Prepare_Store_Data"]:
        if src in new_conns:
            for out_type, out_list in new_conns[src].items():
                for idx, targets in enumerate(out_list):
                    for t in targets:
                        print(f"  {src}[{idx}] -> {t['node']}")

    print("\nDone! Export updated workflow for backup...")
    with open("/Users/najmie/n8n/whatsapp-faq-bot-phase3.json", "w") as f:
        json.dump(result, f, indent=2)
    print("Saved to whatsapp-faq-bot-phase3.json")

if __name__ == "__main__":
    main()
