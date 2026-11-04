#!/usr/bin/env bash
# End-to-end API walkthrough against a locally running gateway.
#
#   uvicorn nexushub_api.main:app --port 8000 &
#   bash apps/api/examples/api_flow.sh
#
# The script bootstraps a key, creates an agent, opens a session and runs
# one synchronous plus one streaming request.
set -euo pipefail

BASE="${NEXUS_BASE_URL:-http://127.0.0.1:8000}"

echo "== bootstrap key =="
KEY_JSON=$(curl -fsS -X POST "$BASE/v1/api-keys" -H 'Content-Type: application/json' -d '{"name": "demo"}')
KEY=$(echo "$KEY_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["key"])')
AUTH="Authorization: Bearer $KEY"
echo "key prefix: ${KEY:0:11}..."

echo "== create agent =="
AGENT_JSON=$(curl -fsS -X POST "$BASE/v1/agents" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name": "demo-agent", "system_prompt": "You are terse.", "model": "gpt-4o-mini"}')
AGENT_ID=$(echo "$AGENT_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "agent: $AGENT_ID"

echo "== open session =="
SESSION_JSON=$(curl -fsS -X POST "$BASE/v1/agents/$AGENT_ID/sessions" -H "$AUTH" -H 'Content-Type: application/json' -d '{}')
SESSION_ID=$(echo "$SESSION_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "session: $SESSION_ID"

echo "== synchronous run =="
curl -fsS -X POST "$BASE/v1/agents/$AGENT_ID/runs" -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"input\": \"Give me one fact about octopuses.\", \"session_id\": \"$SESSION_ID\"}" | python3 -m json.tool

echo "== streaming run (SSE) =="
curl -fsS -N -X POST "$BASE/v1/agents/$AGENT_ID/runs/stream" -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"input\": \"And one about axolotls?\", \"session_id\": \"$SESSION_ID\"}"

echo
echo "== stored transcript =="
curl -fsS "$BASE/v1/sessions/$SESSION_ID/messages" -H "$AUTH" | python3 -m json.tool
