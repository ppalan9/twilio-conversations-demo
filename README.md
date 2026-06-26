# Twilio Conversations — Live Demo

**A working demo of Orchestration, Memory, and Intelligence — running in under 3 minutes.**

No slides. No vercel demos. Real channels with memory with your AI/LLM, seen in a split-pane UI.

---

## Why this exists

This demo lets you type and send real messages, switch channels mid-conversation, and watch the platform respond — memory preserved, signals firing, escalation risk updating live — without any backend setup on their end.

---

## The three pillars

|Conversation lego block | What it does| Value |
|---|---|---|
| ⚡ **Orchestration** | Routes every message to the right handler, regardless of channel | Customer switches from web chat to SMS — same conversation, context preseved |
| 🧠 **Memory** | Memory is available across every channel switch | Channel already knows what was said three channels ago |
| ✨ **Intelligence** | Sentiment, escalation risk, and intent confidence — live | Escalation risk hits 88% before anyone notices the frustration |

---

## Get started

**Prerequisites:** Nothing. The bootstrap script installs everything.

**1. Clone**

```bash
git clone https://github.com/ppalan9/twilio-conversations-demo.git
cd twilio-conversations-demo
```

**2. Run**

```bash
./scripts/bootstrap.sh
```

Installs Python, all dependencies, and a tunnel — then launches the server.

**3. Open**

```
http://localhost:5050
```

A setup wizard appears. Add your keys or skip to run in **mock mode** instantly — no credentials needed.

---

## Setup wizard

First load shows a 3-step wizard. No `.env` editing required.

| Step | What you enter | What you get |
|---|---|---|
| **1** | Anthropic API key (`sk-ant-…`) | Live Claude AI responses |
| **2** | Twilio Account SID + Auth Token + phone number | Real SMS, Voice, and WhatsApp |
| **3** | Your mobile number *(optional)* | Test SMS confirming end-to-end delivery |

Keys are stored in your browser only. Hit **Skip** at any step to stay in mock mode.

---

## Show me what you can do before i get my keys

| # | Do this | Point here |
|---|---|---|
| 1 | Text: `I need help with my order` | Memory nodes light up on the right panel |
| 2 | Click the **SMS** tab | Banner shows same session, context preserved |
| 3 | Type: `This is inconceivable, I've been waiting for days` | Escalation risk spikes to 88%, ALERT fires |
| 4 | Type: `Thank you, that's sorted` | Sentiment recovers, CSAT predicted high |
| 5 *(optional)* | Enter customer's phone in **Configure Keys** | Real SMS lands on their device mid-demo |

<img width="967" height="591" alt="Screenshot 2026-06-26 at 4 02 49 AM" src="https://github.com/user-attachments/assets/24f373e5-dbb5-4f19-a961-a5a06cd8e711" />

---
## Connecting real channels

```bash
ngrok http 5050
```

Set these in [Twilio Console](https://console.twilio.com) → Phone Numbers → your number:

| Channel | Webhook URL |
|---|---|
| SMS | `https://<tunnel>/webhook/sms` |
| Voice | `https://<tunnel>/webhook/voice` |
| WhatsApp | `https://<tunnel>/webhook/whatsapp` |

Or let bootstrap do it all — buys a number and wires every webhook automatically:

```bash
./scripts/bootstrap.sh
```

Already have a number? Skip provisioning:

```bash
./scripts/bootstrap.sh --skip-provisioning
```

---

## What `bootstrap.sh` does

```
1. Installs uv + Python 3.12
2. Installs Flask, Anthropic SDK, Twilio SDK
3. Installs cloudflared tunnel if none found
4. Creates .env from .env.example
5. Starts tunnel → buys Twilio number → wires webhooks → launches server
```

---

## Project structure

```
twilio-conversations-demo/
├── demo_server.py     # Flask backend — API, session memory, webhooks
├── index.html         # Frontend — single HTML file, no build step
├── .env.example       # Credential template
├── pyproject.toml     # Python dependencies
└── scripts/
    ├── bootstrap.sh   # One-command setup
    └── provision.py   # Provisions Twilio number and webhooks
```

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | HTML / CSS / JS — single file, no build step |
| Backend | Python 3.12, Flask |
| AI | Claude `claude-sonnet-4-6` via Anthropic API — BYOK |
| Channels | Twilio SMS, Voice, WhatsApp |
| Packaging | `uv` |
| Tunnel | cloudflared (auto-installed) or ngrok |

---
## Wait but i am not logged into my public git repo

  **Option A — No Git**

  1. Go to https://github.com/ppalan9/twilio-conversations-demo
  2. Click the green Code button
  3. Click Download ZIP
  4. Unzip it
  5. Open Terminal, drag the folder into the Terminal window (auto-fills the path), press Enter
  6. Run: ./scripts/bootstrap.sh
  7. Open http://localhost:5050

  ---
  **Option B — With Git**
  
  git clone https://github.com/ppalan9/twilio-conversations-demo.git
  cd twilio-conversations-demo
  ./scripts/bootstrap.sh

---

## License

MIT
