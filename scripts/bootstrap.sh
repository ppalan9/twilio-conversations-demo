#!/usr/bin/env bash
# bootstrap.sh — one-command setup for the Twilio Conversations Layer demo
# Usage:
#   ./scripts/bootstrap.sh                   # full setup: tunnel + provision + launch
#   ./scripts/bootstrap.sh --skip-provisioning  # skip Twilio number purchase

set -euo pipefail

SKIP_PROVISION=false
for arg in "$@"; do
  [[ "$arg" == "--skip-provisioning" ]] && SKIP_PROVISION=true
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
PORT=5050

# ── Colors ────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

step()  { echo -e "\n${BLUE}▶ $1${RESET}"; }
ok()    { echo -e "${GREEN}✓ $1${RESET}"; }
warn()  { echo -e "${YELLOW}⚠ $1${RESET}"; }
fatal() { echo -e "${RED}✗ $1${RESET}"; exit 1; }

echo -e "\n${BOLD}Twilio Conversations Layer — Demo Bootstrap${RESET}"
echo -e "────────────────────────────────────────────\n"

# ── 1. Check .env ─────────────────────────────────────────────
step "Checking credentials"
[[ -f "$ENV_FILE" ]] || fatal ".env not found. Run: cp .env.example .env and fill in credentials."

source_env() {
  set -o allexport
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +o allexport
}
source_env

[[ -n "${ANTHROPIC_API_KEY:-}" ]]   || fatal "ANTHROPIC_API_KEY is not set in .env"
[[ -n "${TWILIO_ACCOUNT_SID:-}" ]]  || fatal "TWILIO_ACCOUNT_SID is not set in .env"
[[ -n "${TWILIO_AUTH_TOKEN:-}" ]]   || fatal "TWILIO_AUTH_TOKEN is not set in .env"
ok "Credentials loaded"

# ── 2. Check dependencies ─────────────────────────────────────
step "Checking dependencies"

check_cmd() {
  command -v "$1" &>/dev/null || fatal "'$1' not found. Install: $2"
}

check_cmd uv       "https://docs.astral.sh/uv/getting-started/installation/"
check_cmd python3  "https://python.org"

# Detect tunnel tool
TUNNEL_CMD=""
if command -v ngrok &>/dev/null; then
  TUNNEL_CMD="ngrok"
  ok "ngrok found"
elif command -v cloudflared &>/dev/null; then
  TUNNEL_CMD="cloudflared"
  ok "cloudflared found"
else
  warn "No tunnel tool found (ngrok or cloudflared). Install ngrok: https://ngrok.com/download"
  warn "Continuing without tunnel — webhooks will not work for inbound SMS/Voice/WhatsApp"
fi

uv sync --quiet
ok "Python dependencies installed"

# ── 3. Start tunnel ───────────────────────────────────────────
PUBLIC_URL=""
TUNNEL_PID=""

if [[ -n "$TUNNEL_CMD" ]]; then
  step "Starting $TUNNEL_CMD tunnel on port $PORT"

  if [[ "$TUNNEL_CMD" == "ngrok" ]]; then
    ngrok http "$PORT" --log=stdout > /tmp/ngrok.log 2>&1 &
    TUNNEL_PID=$!
    echo -n "Waiting for tunnel URL"
    for i in {1..20}; do
      PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
        | python3 -c "import sys,json; t=json.load(sys.stdin).get('tunnels',[]); print(t[0]['public_url'] if t else '')" 2>/dev/null || true)
      [[ -n "$PUBLIC_URL" ]] && break
      echo -n "."
      sleep 1
    done
    echo ""
    [[ -n "$PUBLIC_URL" ]] || fatal "ngrok tunnel did not start. Check /tmp/ngrok.log"
    ok "Tunnel: $PUBLIC_URL"

  elif [[ "$TUNNEL_CMD" == "cloudflared" ]]; then
    cloudflared tunnel --url "http://localhost:$PORT" --no-autoupdate > /tmp/cloudflared.log 2>&1 &
    TUNNEL_PID=$!
    echo -n "Waiting for tunnel URL"
    for i in {1..30}; do
      PUBLIC_URL=$(grep -o 'https://[^ ]*trycloudflare.com' /tmp/cloudflared.log 2>/dev/null | head -1 || true)
      [[ -n "$PUBLIC_URL" ]] && break
      echo -n "."
      sleep 1
    done
    echo ""
    [[ -n "$PUBLIC_URL" ]] || fatal "cloudflared tunnel did not start. Check /tmp/cloudflared.log"
    ok "Tunnel: $PUBLIC_URL"
  fi
fi

# ── 4. Provision Twilio number ────────────────────────────────
if [[ "$SKIP_PROVISION" == "false" && -n "$PUBLIC_URL" ]]; then
  step "Provisioning Twilio resources"

  if [[ -z "${TWILIO_PHONE_NUMBER:-}" ]]; then
    PROVISIONED=$(cd "$ROOT" && uv run python scripts/provision.py \
      --base-url "$PUBLIC_URL" \
      --account-sid "$TWILIO_ACCOUNT_SID" \
      --auth-token "$TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER=$(echo "$PROVISIONED" | grep "^PHONE:" | cut -d: -f2)
    echo "TWILIO_PHONE_NUMBER=$TWILIO_PHONE_NUMBER" >> "$ENV_FILE"
    ok "Provisioned number: $TWILIO_PHONE_NUMBER"
    source_env
  else
    # Number exists — just update webhooks
    cd "$ROOT" && uv run python scripts/provision.py \
      --base-url "$PUBLIC_URL" \
      --account-sid "$TWILIO_ACCOUNT_SID" \
      --auth-token "$TWILIO_AUTH_TOKEN" \
      --phone-number "$TWILIO_PHONE_NUMBER" \
      --update-webhooks-only
    ok "Webhooks updated for $TWILIO_PHONE_NUMBER → $PUBLIC_URL"
  fi
elif [[ "$SKIP_PROVISION" == "true" ]]; then
  warn "Skipping provisioning (--skip-provisioning)"
  [[ -n "${TWILIO_PHONE_NUMBER:-}" ]] && warn "Existing number: $TWILIO_PHONE_NUMBER — update webhooks manually"
fi

# ── 5. Launch server ──────────────────────────────────────────
step "Starting demo server"

DEMO_URL="${PUBLIC_URL:-http://localhost:$PORT}"

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}  Demo ready${RESET}"
echo -e "${BOLD}  URL:    ${GREEN}$DEMO_URL${RESET}"
[[ -n "${TWILIO_PHONE_NUMBER:-}" ]] && \
echo -e "${BOLD}  Number: ${GREEN}$TWILIO_PHONE_NUMBER${RESET}  ← text or call this"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

cleanup() {
  [[ -n "$TUNNEL_PID" ]] && kill "$TUNNEL_PID" 2>/dev/null || true
}
trap cleanup EXIT

cd "$ROOT"
uv run python demo_server.py
