#!/usr/bin/env bash
# bootstrap.sh — zero-dependency setup for the Twilio Conversations demo
# Installs uv + Python if missing, then: tunnel + provision + launch
# Usage:
#   ./scripts/bootstrap.sh                      # full setup
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

# ── 1. Install uv (installs Python 3.12 automatically) ────────
step "Checking uv + Python"
if ! command -v uv &>/dev/null; then
  warn "uv not found — installing now (this also installs Python 3.12)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Add uv to PATH for the rest of this script
  export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
fi
ok "uv $(uv --version)"

# ── 2. Install Python deps ────────────────────────────────────
step "Installing Python dependencies"
cd "$ROOT"
uv sync --quiet
ok "Dependencies ready (flask, anthropic, twilio)"

# ── 3. Copy .env if missing; open it for editing if keys absent ──
step "Checking credentials"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT/.env.example" "$ENV_FILE"
  warn ".env created from .env.example"
  warn "Add your keys now — or skip and use the in-browser wizard at http://localhost:$PORT"
fi

source_env() {
  set -o allexport
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +o allexport
}
source_env

# Keys are optional — wizard in the browser handles them if missing
if [[ -z "${ANTHROPIC_API_KEY:-}" || "${ANTHROPIC_API_KEY}" == "sk-ant-..."* ]]; then
  warn "ANTHROPIC_API_KEY not set — demo will run in mock mode until you add it in the browser"
fi
ok "Credentials checked"

# ── 4. Install + start tunnel ──────────────────────────────────
# Detect or auto-install a tunnel tool
TUNNEL_CMD=""
if command -v ngrok &>/dev/null; then
  TUNNEL_CMD="ngrok"
  ok "ngrok found"
elif command -v cloudflared &>/dev/null; then
  TUNNEL_CMD="cloudflared"
  ok "cloudflared found"
else
  step "No tunnel found — installing cloudflared (free, no account needed)"
  if command -v brew &>/dev/null; then
    brew install cloudflared --quiet && TUNNEL_CMD="cloudflared" && ok "cloudflared installed"
  elif [[ "$(uname -s)" == "Linux" ]]; then
    curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
      -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared
    TUNNEL_CMD="cloudflared" && ok "cloudflared installed"
  else
    warn "Could not auto-install a tunnel — inbound SMS/Voice/WhatsApp will not work"
    warn "Install manually: brew install cloudflared  OR  https://ngrok.com/download"
  fi
fi

uv sync --quiet
ok "Python dependencies installed"

# ── 3. Start tunnel ───────────────────────────────────────────
PUBLIC_URL=""
TUNNEL_PID=""

if [[ -n "$TUNNEL_CMD" ]]; then
  step "Starting tunnel on port $PORT"

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
