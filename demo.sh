#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# demo.sh  –  Live curl-based demo (requires server to be running)
# Usage:
#   Terminal 1:  bash setup.sh
#   Terminal 2:  bash demo.sh
# ─────────────────────────────────────────────────────────────────────────────

BASE="http://127.0.0.1:8000"
BOLD='\033[1m'
RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[0;33m'
RST='\033[0m'

hr() { echo -e "\n${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"; }
title() { hr; echo -e "${BOLD}  $1${RST}"; hr; }

wait_for_server() {
    echo -n "Waiting for server..."
    for i in $(seq 1 20); do
        if curl -s "$BASE/health" > /dev/null 2>&1; then
            echo " ready!"
            return
        fi
        sleep 1; echo -n "."
    done
    echo -e "\n${RED}Server not responding. Run 'bash setup.sh' first.${RST}"
    exit 1
}

wait_for_server

# ─── Check X-Student-ID header ───────────────────────────────────────────────
title "MIDDLEWARE – X-Student-ID Header"
echo "Every response must carry X-Student-ID:"
HEADER=$(curl -s -I "$BASE/health" | grep -i "x-student-id")
echo -e "${GRN}  $HEADER${RST}"


# ─── Problem 1: Optimistic Locking ───────────────────────────────────────────
title "PROBLEM 1 – Optimistic Locking (Lost-Update Prevention)"

echo -e "\n${BOLD}Creating a shared document...${RST}"
DOC=$(curl -s -X POST "$BASE/documents/?title=SharedDoc&content=Initial+content")
DOC_ID=$(echo $DOC | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
VERSION=$(echo $DOC | python3 -c "import sys,json; print(json.load(sys.stdin)['version'])")
echo "  Doc ID  : $DOC_ID"
echo "  Version : $VERSION"

echo -e "\n${BOLD}[BEFORE FIX - naive overwrite] Alice and Bob both read version $VERSION${RST}"
echo -e "${YLW}  (In the old code, the second write would silently overwrite the first)${RST}"

echo -e "\n${BOLD}[WITH FIX] Alice writes first (correct version=$VERSION)...${RST}"
R_ALICE=$(curl -s -X PUT "$BASE/documents/$DOC_ID?content=Alice%27s+changes&expected_version=$VERSION")
echo "  Alice: $(echo $R_ALICE | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'status=200  new version={d[\"version\"]}')")"

echo -e "\n${BOLD}Bob tries to write with the SAME stale version=$VERSION...${RST}"
R_BOB=$(curl -s -o /tmp/bob_response.json -w "%{http_code}" -X PUT "$BASE/documents/$DOC_ID?content=Bob%27s+changes&expected_version=$VERSION")
echo -e "  Bob: HTTP $R_BOB  →  $(cat /tmp/bob_response.json | python3 -c "import sys,json; print(json.load(sys.stdin)['detail'])")"

if [ "$R_BOB" = "409" ]; then
    echo -e "${GRN}  ✔ Lost-Update PREVENTED – 409 Conflict returned!${RST}"
else
    echo -e "${RED}  ✗ BUG: write should have been rejected${RST}"
fi


# ─── Problem 2: Idempotent Webhook ───────────────────────────────────────────
title "PROBLEM 2 – Idempotent Webhook (Dropped Event Prevention)"

PAYLOAD='{"type":"subscription.cancelled","data":{"id":"user_xyz"}}'
KEY="svix-evt-demo-001"

echo -e "\n${BOLD}First delivery of webhook (Svix-Id: $KEY)...${RST}"
R1=$(curl -s -X POST "$BASE/webhooks/clerk" \
    -H "Content-Type: application/json" \
    -H "svix-id: $KEY" \
    -d "$PAYLOAD")
echo "  Result: $(echo $R1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])")"

echo -e "\n${BOLD}[BEFORE FIX] Network blip – Clerk retries the SAME event...${RST}"
echo -e "${YLW}  (In the old code, the cancellation would be applied twice)${RST}"

echo -e "\n${BOLD}[WITH FIX] Second delivery of same webhook...${RST}"
R2=$(curl -s -X POST "$BASE/webhooks/clerk" \
    -H "Content-Type: application/json" \
    -H "svix-id: $KEY" \
    -d "$PAYLOAD")
STATUS=$(echo $R2 | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
echo "  Result: $STATUS"

if [ "$STATUS" = "duplicate" ]; then
    echo -e "${GRN}  ✔ Duplicate webhook safely deduplicated – no double cancellation!${RST}"
else
    echo -e "${RED}  ✗ BUG: duplicate should have been skipped${RST}"
fi


# ─── Problem 3: Circuit Breaker ──────────────────────────────────────────────
title "PROBLEM 3 – Circuit Breaker (LLM Fault Tolerance)"

echo -e "\n${BOLD}[BEFORE FIX] LLM is healthy – normal call...${RST}"
R=$(curl -s -X POST "$BASE/ai/summarise?prompt=hello")
echo "  Source: $(echo $R | python3 -c "import sys,json; print(json.load(sys.stdin)['source'])")"
echo "  Circuit: $(echo $R | python3 -c "import sys,json; print(json.load(sys.stdin)['circuit_state'])")"

echo -e "\n${BOLD}Simulating 3 LLM failures (threshold = 3)...${RST}"
for i in 1 2 3; do
    R=$(curl -s -X POST "$BASE/ai/summarise?prompt=test&simulate_failure=true")
    STATE=$(echo $R | python3 -c "import sys,json; print(json.load(sys.stdin)['circuit_state'])")
    echo "  Failure $i → circuit=$STATE"
done

echo -e "\n${BOLD}[WITH FIX] Circuit is OPEN – next call gets instant fallback...${RST}"
R=$(curl -s -X POST "$BASE/ai/summarise?prompt=after_open")
SRC=$(echo $R | python3 -c "import sys,json; print(json.load(sys.stdin)['source'])")
STATE=$(echo $R | python3 -c "import sys,json; print(json.load(sys.stdin)['circuit_state'])")
MSG=$(echo $R | python3 -c "import sys,json; print(json.load(sys.stdin)['response'])")
echo "  Source  : $SRC"
echo "  Circuit : $STATE"
echo "  Message : $MSG"

if [ "$SRC" = "fallback" ] && [ "$STATE" = "OPEN" ]; then
    echo -e "${GRN}  ✔ Server returned instant fallback – NO 60-second hang!${RST}"
else
    echo -e "${RED}  ✗ Expected fallback from OPEN circuit${RST}"
fi

hr
echo -e "${GRN}${BOLD}  Demo complete!${RST}"
hr
echo ""
