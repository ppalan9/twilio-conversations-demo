# Twilio Conversations Demo

A self-contained, browser-based demo of the Twilio Conversations layer — Orchestration, Memory, and Intelligence — running live with Claude AI and real SMS, Voice, and WhatsApp channels.

**Time to first demo: < 3 minutes.**

---

## What it shows

| Pillar | The "aha" moment |
|---|---|
| **Orchestration** | One session, every channel — no duplicated routing logic |
| **Memory** | Context travels when the customer switches from web chat to SMS to a call |
| **Intelligence** | Sentiment, escalation risk, and intent scores updating in real time |

---

## Quick start

### Step 1 — Clone and install

```bash
git clone https://github.com/ppalan9/twilio-conversations-demo.git
cd twilio-conversations-demo
uv sync
```

> No `uv`? Install it: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Step 2 — Start the server

```bash
uv run python demo_server.py
```

Open **http://localhost:5050** — a 3-step setup wizard appears in the UI.

### Step 3 — Add your keys in the browser

The wizard walks you through:

1. **Anthropic API key** — get one free at [console.anthropic.com](https://console.anthropic.com) → API Keys
2. **Twilio credentials** — Account SID + Auth Token from [console.twilio.com](https://console.twilio.com) → Account Info
3. **Your mobile number** — optional, to receive a test SMS confirming end-to-end delivery

Hit **Launch Demo →** and you're live. Skip any step to run in mock mode immediately.

---

## Enabling real inbound SMS / Voice / WhatsApp

Point your Twilio number's webhooks to your server. For local dev, use a tunnel:

```bash
brew install ngrok/ngrok/ngrok
ngrok http 5050
```

Then in [Twilio Console](https://console.twilio.com) → Phone Numbers → your number:

| Channel | Webhook field | URL |
|---|---|---|
| SMS | Messaging → "A message comes in" | `https://<ngrok-url>/webhook/sms` |
| Voice | Voice → "A call comes in" | `https://<ngrok-url>/webhook/voice` |
| WhatsApp | Messaging → Senders → Sandbox | `https://<ngrok-url>/webhook/whatsapp` |

Or run the one-command bootstrap that does all of this automatically:

```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
./scripts/bootstrap.sh
```

Bootstrap buys a Twilio number, wires all webhooks, starts the tunnel, and launches the server.

---

## Demo script (5 minutes)

1. **Type:** `I need help tracking my order` — watch memory nodes light up on the right
2. **Click SMS tab** — banner shows memory was preserved across channels
3. **Type:** `This is terrible, I've been waiting for days` — escalation risk spikes to 88%
4. **Type:** `Thank you, that's sorted` — sentiment recovers, CSAT predicted high
5. **Optional:** enter your phone number in Configure Keys — get a real SMS on your device

---

## Customise

| Goal | Where |
|---|---|
| New intent / keyword | `MOCK_FLOWS` in `demo_server.py` + `MOCK[]` in `index.html` |
| Change the agent persona | `system` prompt in `claude_reply()` in `demo_server.py` |
| Change greeting | `MOCK_FLOWS[0]` in `demo_server.py` |
| Vertical (banking, retail) | Swap persona + mock flows |

---

## Stack

| Component | Tech |
|---|---|
| Frontend | Single-file HTML/CSS/JS — no build step |
| Backend | Python 3.12+, Flask |
| AI | Claude (`claude-sonnet-4-6`) via Anthropic API |
| Channels | Twilio SMS, Voice (TwiML), WhatsApp |
| Package manager | `uv` |

---

## Related

- [Twilio Conversations API docs](https://www.twilio.com/docs/conversations)
- [Anthropic Claude API](https://docs.anthropic.com)
- [twilio-conversations-layer-claude-factory](https://github.com/twilio-internal/twilio-conversations-layer-claude-factory) *(Twilio-internal)*
