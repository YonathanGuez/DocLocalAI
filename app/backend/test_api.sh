#!/bin/bash
# Quick API test script

BASE_URL="http://localhost:8000"

echo "Testing DocLocalAI API..."
echo

# 1. Health check
echo "1. Health Check:"
curl -s "$BASE_URL/health" | jq '.'
echo

# 2. List sessions
echo "2. List Sessions:"
curl -s "$BASE_URL/api/sessions" | jq '.'
echo

# 3. Send a chat message (creates new session)
SESSION_ID=$(uuidgen)
echo "3. Send Chat Message (Session: $SESSION_ID):"
curl -s -X POST "$BASE_URL/api/chat" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\",\"message\":\"How do I restart a pod?\"}" | jq '.'
echo

# 4. Get session messages
echo "4. Get Session Messages:"
curl -s "$BASE_URL/api/sessions/$SESSION_ID" | jq '.'
echo

# 5. Delete session
echo "5. Delete Session:"
curl -s -X DELETE "$BASE_URL/api/sessions/$SESSION_ID" | jq '.'
echo

# 6. Verify deletion
echo "6. Verify Deletion (should return 404):"
curl -s "$BASE_URL/api/sessions/$SESSION_ID" | jq '.'
echo

echo "✅ API tests complete!"
