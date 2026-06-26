"""
Twilio Conversation Intelligence Demo Server
- Real mode:  needs ANTHROPIC_API_KEY + Twilio creds in .env
- Mock mode:  set MOCK_MODE=true (or leave creds empty) — no external calls
"""

import os, json, time, uuid
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="Documents")

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

@app.route("/api/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return "", 204

# ── Config ────────────────────────────────────────────────────
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
TWILIO_SID      = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE    = os.getenv("TWILIO_PHONE_NUMBER", "+15550001234")
TWILIO_WA       = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
MOCK_MODE       = os.getenv("MOCK_MODE", "true").lower() == "true" or not ANTHROPIC_KEY

# ── In-memory session store (replace with Redis/DB in prod) ───
sessions: dict[str, dict] = {}

def get_session(sid: str) -> dict:
    if sid not in sessions:
        sessions[sid] = {"history": [], "memory": {}, "channel": "chat"}
    return sessions[sid]

# ── Claude client ─────────────────────────────────────────────
def claude_reply(session: dict, user_msg: str) -> dict:
    """Call Claude with conversation history + memory context."""
    if MOCK_MODE or user_msg == "__init__":
        return mock_reply(user_msg, session)

    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    mem_ctx = json.dumps(session.get("memory", {}), indent=2) if session.get("memory") else "none yet"
    system = f"""You are a helpful customer support AI for a demo of Twilio's Conversation Intelligence platform.
Keep replies concise (1-3 sentences). Be warm and direct.

Customer memory profile (what you know so far):
{mem_ctx}

After each reply, output a JSON block on its own line starting with SIGNALS: containing:
  sentiment (0-100), intent_confidence (0-100), resolution_likelihood (0-100),
  escalation_risk (0-100), memory_nodes (list from: identity,observations,summary,intent,context),
  signals (list of {{icon, tag (orch|mem|intel|alert), msg}})
"""
    msgs = [{"role": m["role"], "content": m["content"]} for m in session["history"]]
    msgs.append({"role": "user", "content": user_msg})

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=system,
        messages=msgs
    )
    raw = resp.content[0].text

    # Split reply from signals
    reply_text, signals_data = raw, {}
    if "SIGNALS:" in raw:
        parts = raw.split("SIGNALS:", 1)
        reply_text = parts[0].strip()
        try:
            signals_data = json.loads(parts[1].strip())
        except Exception:
            signals_data = {}

    # Update session history
    session["history"].append({"role": "user", "content": user_msg})
    session["history"].append({"role": "assistant", "content": reply_text})

    # Update memory from signals
    for node in signals_data.get("memory_nodes", []):
        session["memory"][node] = True

    return {"reply": reply_text, **signals_data}


# ── Mock reply engine ─────────────────────────────────────────
MOCK_FLOWS = [
    ([], "Hi there! 👋 I'm here to help. What can I assist you with today?",
     {"sentiment":55,"intent_confidence":40,"resolution_likelihood":50,"escalation_risk":10,
      "memory_nodes":["identity"],
      "signals":[{"icon":"🔵","tag":"orch","msg":"Session initialized · Identity lookup started"}]}),

    (["order","track","package","shipping","delivery","where"],
     "I can help track that. One moment while I pull up your order details.",
     {"sentiment":62,"intent_confidence":85,"resolution_likelihood":70,"escalation_risk":12,
      "memory_nodes":["observations","context","intent"],
      "signals":[{"icon":"🧠","tag":"mem","msg":"Intent: Order tracking · Observations retrieved"},
                 {"icon":"📊","tag":"intel","msg":"Confidence 85% · Self-serve flow selected"}]}),

    (["cancel","return","refund","money"],
     "I understand — I've pulled your history so you won't need to repeat details. Let me look into this.",
     {"sentiment":38,"intent_confidence":90,"resolution_likelihood":68,"escalation_risk":45,
      "memory_nodes":["observations","summary","intent"],
      "signals":[{"icon":"⚠️","tag":"alert","msg":"Churn signal detected · Retention flow queued"},
                 {"icon":"🧠","tag":"mem","msg":"Observations loaded · Summary applied"}]}),

    (["frustrated","angry","terrible","awful","not working","broken","useless","worst"],
     "I'm really sorry this has been difficult. I'm escalating this now so the right person handles it personally.",
     {"sentiment":16,"intent_confidence":96,"resolution_likelihood":52,"escalation_risk":88,
      "memory_nodes":["identity","observations","context","summary"],
      "signals":[{"icon":"🔴","tag":"alert","msg":"High frustration · Human escalation triggered"},
                 {"icon":"📊","tag":"intel","msg":"Sentiment: critical · Empathy response applied"}]}),

    (["thanks","thank you","great","perfect","awesome","resolved","fixed","helped"],
     "So glad I could help! 😊 Is there anything else I can assist you with?",
     {"sentiment":93,"intent_confidence":72,"resolution_likelihood":96,"escalation_risk":4,
      "memory_nodes":["intent","summary"],
      "signals":[{"icon":"✅","tag":"intel","msg":"Sentiment recovered · CSAT prediction: 4.8/5"},
                 {"icon":"🧠","tag":"mem","msg":"Outcome stored · Summary updated"}]}),

    (["account","password","login","email","profile"],
     "I've already verified your identity. What would you like to update on your account?",
     {"sentiment":65,"intent_confidence":88,"resolution_likelihood":82,"escalation_risk":10,
      "memory_nodes":["identity","summary"],
      "signals":[{"icon":"🔵","tag":"orch","msg":"Identity verified · Account tools unlocked"}]}),

    (["price","plan","upgrade","cost","cheap","expensive"],
     "Based on your usage, I can walk you through the options that make the most sense for you.",
     {"sentiment":70,"intent_confidence":84,"resolution_likelihood":76,"escalation_risk":8,
      "memory_nodes":["observations","intent","summary"],
      "signals":[{"icon":"📊","tag":"intel","msg":"Intent: upgrade evaluation · Offer personalized"},
                 {"icon":"🧠","tag":"mem","msg":"Observations applied to recommendation"}]}),
]

def mock_reply(text: str, session: dict) -> dict:
    t = text.lower()
    if t == "__init__":
        _, reply, data = MOCK_FLOWS[0]
        session["history"].append({"role": "assistant", "content": reply})
        for node in data.get("memory_nodes", []):
            session["memory"][node] = True
        return {"reply": reply, **data}
    for keywords, reply, data in MOCK_FLOWS[1:]:
        if any(k in t for k in keywords):
            session["history"].append({"role": "user", "content": text})
            session["history"].append({"role": "assistant", "content": reply})
            for node in data.get("memory_nodes", []):
                session["memory"][node] = True
            return {"reply": reply, **data}
    # Generic fallback
    reply = "I'm on it — let me look into that for you right away."
    data = {"sentiment":60,"intent_confidence":58,"resolution_likelihood":60,"escalation_risk":18,
            "memory_nodes":["context"],
            "signals":[{"icon":"🔵","tag":"orch","msg":"Processing · Context updated"}]}
    session["history"].append({"role": "user", "content": text})
    session["history"].append({"role": "assistant", "content": reply})
    session["memory"]["context"] = True
    return {"reply": reply, **data}


# ── Twilio inbound SMS/WhatsApp webhook ───────────────────────
def twilio_twiml_response(text: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{text}</Message></Response>'

@app.route("/webhook/sms", methods=["POST"])
def sms_webhook():
    """Twilio sends inbound SMS here. Point your Twilio number webhook to /webhook/sms."""
    from_num = request.form.get("From", "unknown")
    body     = request.form.get("Body", "")
    sid      = f"sms:{from_num}"
    session  = get_session(sid)
    session["channel"] = "sms"

    result = claude_reply(session, body)
    return twilio_twiml_response(result["reply"]), 200, {"Content-Type": "text/xml"}

@app.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_webhook():
    """Point your Twilio WhatsApp sender webhook to /webhook/whatsapp."""
    from_num = request.form.get("From", "unknown")
    body     = request.form.get("Body", "")
    sid      = f"wa:{from_num}"
    session  = get_session(sid)
    session["channel"] = "whatsapp"

    result = claude_reply(session, body)
    return twilio_twiml_response(result["reply"]), 200, {"Content-Type": "text/xml"}

@app.route("/webhook/voice", methods=["POST"])
def voice_webhook():
    """Twilio Voice — returns TwiML that reads a greeting then connects."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response><Say voice="Polly.Joanna">Welcome back. Your context has been loaded. How can I help you today?</Say>'
        '<Gather input="speech" action="/webhook/voice/gather" timeout="5"/></Response>'
    ), 200, {"Content-Type": "text/xml"}

@app.route("/webhook/voice/gather", methods=["POST"])
def voice_gather():
    speech  = request.form.get("SpeechResult", "")
    from_num = request.form.get("From", "unknown")
    sid      = f"voice:{from_num}"
    session  = get_session(sid)
    session["channel"] = "voice"

    result  = claude_reply(session, speech)
    say_txt = result["reply"].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<Response><Say voice="Polly.Joanna">{say_txt}</Say>'
        f'<Gather input="speech" action="/webhook/voice/gather" timeout="5"/></Response>'
    ), 200, {"Content-Type": "text/xml"}


# ── REST API for the web demo UI ──────────────────────────────
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data    = request.get_json(force=True)
    text    = data.get("message", "").strip()
    sid     = data.get("session_id") or str(uuid.uuid4())
    channel = data.get("channel", "chat")

    if not text:
        return jsonify({"error": "empty message"}), 400

    session = get_session(sid)
    session["channel"] = channel

    # Cross-channel: if session has history from another channel, note it
    prev_channel = session.get("last_channel")
    if prev_channel and prev_channel != channel:
        session["memory"]["channel_switch"] = f"{prev_channel}→{channel}"
    session["last_channel"] = channel

    result = claude_reply(session, text)
    return jsonify({
        "session_id": sid,
        "reply":      result.get("reply", ""),
        "scores": {
            "sentiment":            result.get("sentiment", 60),
            "intent_confidence":    result.get("intent_confidence", 60),
            "resolution_likelihood":result.get("resolution_likelihood", 60),
            "escalation_risk":      result.get("escalation_risk", 20),
        },
        "memory_nodes": result.get("memory_nodes", []),
        "signals":      result.get("signals", []),
        "mock":         MOCK_MODE,
    })

@app.route("/api/session/<sid>", methods=["GET"])
def api_session(sid):
    s = sessions.get(sid, {})
    return jsonify({"history_len": len(s.get("history",[])), "memory": s.get("memory",{}), "channel": s.get("channel","chat")})

@app.route("/api/config", methods=["POST"])
def api_config():
    """Accept live credentials from the demo UI and hot-reload them."""
    global ANTHROPIC_KEY, TWILIO_SID, TWILIO_TOKEN, TWILIO_PHONE, MOCK_MODE
    data = request.get_json(force=True)

    ANTHROPIC_KEY = data.get("anthropic", "").strip()
    TWILIO_SID    = data.get("sid", "").strip()
    TWILIO_TOKEN  = data.get("token", "").strip()
    TWILIO_PHONE  = data.get("twilioNum", "").strip() or TWILIO_PHONE
    customer_phone = data.get("phone", "").strip()

    if not ANTHROPIC_KEY or not TWILIO_SID or not TWILIO_TOKEN:
        return jsonify({"ok": False, "error": "Missing required fields"}), 400

    MOCK_MODE = False  # live mode now that we have keys

    # Optionally send a test SMS to the customer's phone
    if customer_phone and TWILIO_PHONE:
        try:
            from twilio.rest import Client
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            client.messages.create(
                body="👋 Your Twilio Conversation Intelligence demo is live! Reply to this message to start a cross-channel experience.",
                from_=TWILIO_PHONE,
                to=customer_phone
            )
        except Exception as e:
            return jsonify({"ok": True, "warn": f"Keys saved but SMS failed: {e}"})

    return jsonify({"ok": True})


@app.route("/api/send-sms", methods=["POST"])
def api_send_sms():
    """Optionally send an outbound SMS from the demo UI."""
    if MOCK_MODE:
        return jsonify({"ok": True, "mock": True, "note": "Mock mode — no SMS sent"})
    data = request.get_json(force=True)
    to   = data.get("to")
    body = data.get("body", "Your Twilio demo is live! Reply to this message to continue.")
    if not to:
        return jsonify({"error": "missing 'to'"}), 400
    try:
        from twilio.rest import Client
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        msg = client.messages.create(body=body, from_=TWILIO_PHONE, to=to)
        return jsonify({"ok": True, "sid": msg.sid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Serve demo HTML ───────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("Documents", "twilio-conv-demo.html")

if __name__ == "__main__":
    mode = "MOCK" if MOCK_MODE else "LIVE (Claude + Twilio)"
    print(f"\n  Twilio Conversation Intelligence Demo")
    print(f"  Mode: {mode}")
    print(f"  URL:  http://localhost:5050")
    if not MOCK_MODE:
        print(f"  SMS webhook:       POST /webhook/sms")
        print(f"  WhatsApp webhook:  POST /webhook/whatsapp")
        print(f"  Voice webhook:     POST /webhook/voice")
    print(f"  Chat API:          POST /api/chat\n")
    app.run(port=5050, debug=True)
