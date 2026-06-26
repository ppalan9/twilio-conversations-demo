# Twilio Conversations Layer — Live Demo

> Build a working Conversations demo in under 3 minutes. No slides. Real channels. Live AI.

A self-contained demo that shows **Orchestration**, **Memory**, and **Intelligence** working together — with a real Twilio number, live Claude-powered responses, and real-time signals in a split-pane UI that looks like a product.

---

## What it demonstrates

```
Customer sends a message on any channel
         │
         ▼
  ⚡ Orchestration ──── routes to the right handler, no code per channel
         │
         ▼
  🧠 Memory ──────────── context travels with the customer across every channel
         │
         ▼
  ✨ Intelligence ──── sentiment, escalation risk, intent confidence — live
```

| | The "aha" moment |
|---|---|
| **Orchestration** | Switch from Web Chat → SMS mid-conversation. Same session. No re-auth. |
| **Memory** | The agent already knows what was said three channels ago. |
| **Intelligence** | Escalation risk spikes to 88% before a human notices the frustration. |

---

## Get started

### Prerequisites

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- A free [Anthropic API key](https://console.anthropic.com) *(optional — mock mode works without one)*
- A [Twilio account](https://twilio.com/try-twilio) *(optional — for real SMS/Voice/WhatsApp)*

### 3 steps

**1. Clone and install**

```bash
git clone https://github.com/ppalan9/twilio-conversations-demo.git
cd twilio-conversations-demo
uv sync
```

**2. Start the server**

```bash
uv run python demo_server.py
```

**3. Open the browser and follow the wizard**

```
http://localhost:5050
```

A setup wizard appears in the UI — paste your keys, hit **Launch Demo →**. Skip any step to run in **mock mode** immediately with no credentials.

---

## The setup wizard

On first load, a 3-step wizard guides you through configuration — no terminal editing required.

| Step | What you enter | Required? |
|---|---|---|
| 1 | Anthropic API key (`sk-ant-…`) | For live Claude responses |
| 2 | Twilio Account SID + Auth Token + phone number | For real SMS/Voice/WhatsApp |
| 3 | Your mobile number | To receive a test SMS (confirms end-to-end) |

Keys are saved in your browser (`localStorage`) and pushed to the backend automatically. Hit **Skip** at any step to stay in mock mode.

---

## Demo script

Run this in a customer meeting — takes 5 minutes.

| Step | What to do | What to point at |
|---|---|---|
| 1 | Type: `I need help tracking my order` | Memory nodes lighting up on the right panel |
| 2 | Click the **SMS** tab | Channel switch banner — same session, context preserved |
| 3 | Type: `This is terrible, I've been waiting for days` | Escalation risk bar → 88%, red ALERT signal fires |
| 4 | Type: `Thank you, that's sorted` | Sentiment recovers, CSAT predicted high |
| 5 *(optional)* | Click **Configure Keys** → enter customer's phone | Real SMS lands on their device mid-demo |

---

## Enabling real inbound channels

For SMS, Voice, and WhatsApp to work inbound, your server needs a public URL. The fastest way:

```bash
# Install ngrok
brew install ngrok/ngrok/ngrok

# Start a tunnel
ngrok http 5050
```

Then point your Twilio number's webhooks to the tunnel URL:

| Channel | Twilio Console setting | Webhook |
|---|---|---|
| SMS | Phone Numbers → Messaging → "A message comes in" | `https://<tunnel>/webhook/sms` |
| Voice | Phone Numbers → Voice → "A call comes in" | `https://<tunnel>/webhook/voice` |
| WhatsApp | Messaging → Senders → WhatsApp Sandbox | `https://<tunnel>/webhook/whatsapp` |

### One-command setup (tunnel + provision + launch)

```bash
cp .env.example .env
# edit .env: ANTHROPIC_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
./scripts/bootstrap.sh
```

This automatically: starts the tunnel, buys a Twilio number, wires all three webhooks, and launches the server. Prints the public URL and phone number when done.

---

## Project structure

```
twilio-conversations-demo/
├── demo_server.py        # Flask backend — chat API, session memory, webhooks
├── index.html            # Frontend SPA — no build step, works as file://
├── .env.example          # Credential template
├── pyproject.toml        # Python deps (uv)
└── scripts/
    ├── bootstrap.sh      # One-command: tunnel + provision + launch
    └── provision.py      # Buys Twilio number, sets all webhook URLs
```

---

## Customise for your customer

| Goal | File | What to change |
|---|---|---|
| Add a new intent / keyword | `demo_server.py` | Add entry to `MOCK_FLOWS` |
| Mirror it in offline/mock mode | `index.html` | Add matching entry to `MOCK[]` |
| Change the AI persona | `demo_server.py` | Edit `system` prompt in `claude_reply()` |
| Change the greeting | `demo_server.py` | Edit `MOCK_FLOWS[0]` |
| Swap to a different vertical | Both files | Replace persona + MOCK_FLOWS with industry-specific flows |
| Use real Twilio Conversations API | `demo_server.py` | Replace the `sessions` dict with a Conversations Service client |

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla HTML/CSS/JS, single file, no build step |
| Backend | Python 3.12+, Flask |
| AI | Claude `claude-sonnet-4-6` via Anthropic API |
| Channels | Twilio SMS, Voice (TwiML + STT), WhatsApp |
| Package manager | `uv` |
| Tunnel (local dev) | ngrok or cloudflared |

---

## Related resources

- [Twilio Conversations API](https://www.twilio.com/docs/conversations)
- [Twilio Voice](https://www.twilio.com/docs/voice)
- [Anthropic Claude API](https://docs.anthropic.com)
- [Claude model reference](https://docs.anthropic.com/en/docs/models-overview)
- [twilio-conversations-layer-claude-factory](https://github.com/twilio-internal/twilio-conversations-layer-claude-factory) — full Claude Code factory with MCP server and `/architect` skill *(Twilio-internal org)*

---

## License

MIT
