#!/usr/bin/env bash
# bootstrap.sh — one command to run the Twilio Conversations demo
# No credentials needed upfront — add your keys in the browser wizard.
# Usage:
#   ./scripts/bootstrap.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT=5050

# ── Colors ────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

step()  { echo -e "\n${BLUE}▶ $1${RESET}"; }
ok()    { echo -e "${GREEN}✓ $1${RESET}"; }
warn()  { echo -e "${YELLOW}⚠ $1${RESET}"; }

echo -e "\n${BOLD}Twilio Conversations Demo${RESET}"
echo -e "──────────────────────────\n"

# ── 1. Install uv + Python ────────────────────────────────────
step "Checking uv + Python"
if ! command -v uv &>/dev/null; then
  warn "uv not found — installing now (includes Python 3.12)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
fi
ok "uv ready"

# ── 2. Install Python dependencies ───────────────────────────
step "Installing dependencies"
cd "$ROOT"
uv sync --quiet
ok "Flask, Anthropic SDK, Twilio SDK installed"

# ── 3. Install tunnel if needed ───────────────────────────────
step "Checking tunnel"
TUNNEL_CMD=""
if command -v ngrok &>/dev/null; then
  TUNNEL_CMD="ngrok" && ok "ngrok found"
elif command -v cloudflared &>/dev/null; then
  TUNNEL_CMD="cloudflared" && ok "cloudflared found"
else
  warn "No tunnel found — installing cloudflared"
  if command -v brew &>/dev/null; then
    brew install cloudflared --quiet && TUNNEL_CMD="cloudflared" && ok "cloudflared installed"
  elif [[ "$(uname -s)" == "Linux" ]]; then
    curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
      -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared
    TUNNEL_CMD="cloudflared" && ok "cloudflared installed"
  else
    warn "Could not auto-install tunnel — inbound SMS/Voice/WhatsApp won't work without one"
    warn "Install manually: brew install cloudflared"
  fi
fi

# ── 4. Start tunnel ───────────────────────────────────────────
PUBLIC_URL=""
TUNNEL_PID=""

if [[ -n "$TUNNEL_CMD" ]]; then
  step "Starting tunnel"

  if [[ "$TUNNEL_CMD" == "ngrok" ]]; then
    ngrok http "$PORT" --log=stdout > /tmp/ngrok.log 2>&1 &
    TUNNEL_PID=$!
    echo -n "Waiting for tunnel"
    for i in {1..20}; do
      PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
        | python3 -c "import sys,json; t=json.load(sys.stdin).get('tunnels',[]); print(t[0]['public_url'] if t else '')" 2>/dev/null || true)
      [[ -n "$PUBLIC_URL" ]] && break
      echo -n "." && sleep 1
    done
    echo ""
    ok "Tunnel: $PUBLIC_URL"

  elif [[ "$TUNNEL_CMD" == "cloudflared" ]]; then
    cloudflared tunnel --url "http://localhost:$PORT" --no-autoupdate > /tmp/cloudflared.log 2>&1 &
    TUNNEL_PID=$!
    echo -n "Waiting for tunnel"
    for i in {1..30}; do
      PUBLIC_URL=$(grep -o 'https://[^ ]*trycloudflare.com' /tmp/cloudflared.log 2>/dev/null | head -1 || true)
      [[ -n "$PUBLIC_URL" ]] && break
      echo -n "." && sleep 1
    done
    echo ""
    ok "Tunnel: $PUBLIC_URL"
  fi
fi

# Write tunnel URL to .env so the server and wizard can use it
if [[ -n "$PUBLIC_URL" ]]; then
  if [[ ! -f "$ROOT/.env" ]]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
  fi
  # Update or append TUNNEL_URL
  if grep -q "^TUNNEL_URL=" "$ROOT/.env" 2>/dev/null; then
    sed -i.bak "s|^TUNNEL_URL=.*|TUNNEL_URL=$PUBLIC_URL|" "$ROOT/.env" && rm -f "$ROOT/.env.bak"
  else
    echo "TUNNEL_URL=$PUBLIC_URL" >> "$ROOT/.env"
  fi
fi

# ── 5. Launch ─────────────────────────────────────────────────
step "Starting server"

DEMO_URL="${PUBLIC_URL:-http://localhost:$PORT}"

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}  Demo ready${RESET}"
echo -e ""
echo -e "${BOLD}  Open:  ${GREEN}$DEMO_URL${RESET}"
echo -e "${BOLD}  Local: ${GREEN}http://localhost:$PORT${RESET}"
echo -e ""
echo -e "  Add your keys in the browser wizard, or skip to"
echo -e "  run in mock mode — no credentials needed."
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

cleanup() {
  [[ -n "$TUNNEL_PID" ]] && kill "$TUNNEL_PID" 2>/dev/null || true
}
trap cleanup EXIT

cd "$ROOT"
uv run python demo_server.py
