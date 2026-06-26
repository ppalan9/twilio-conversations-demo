"""
Twilio Conversation Intelligence Demo Server
- Real mode:  needs ANTHROPIC_API_KEY + Twilio creds in .env
- Mock mode:  set MOCK_MODE=true (or leave creds empty) — no external calls
"""

import os, json, time, uuid
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()

# On Render, RENDER_EXTERNAL_URL is the public URL — use it as the tunnel
if os.getenv("RENDER_EXTERNAL_URL"):
    os.environ.setdefault("TUNNEL_URL", os.environ["RENDER_EXTERNAL_URL"])

app = Flask(__name__, static_folder=".")

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
  escalation_risk (0-100), memory_nodes (list from: identity,observations,summary),
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
# Each flow: (keywords, turns[], data)
# turns[] = list of replies cycled through on repeated matches
# so the conversation progresses naturally without AI

MOCK_FLOWS = [
    # 0 — GREETING (init only)
    {
        "keys": [],
        "turns": ["Hi there! 👋 I'm here to help. What can I assist you with today?"],
        "data": {
            "sentiment":55,"intent_confidence":40,"resolution_likelihood":50,"escalation_risk":10,
            "memory_nodes":["identity"],
            "signals":[{"icon":"🔵","tag":"orch","msg":"Session initialized · Identity lookup started"}]
        }
    },
    # 1 — ORDER TRACKING
    {
        "keys": ["order","track","package","shipping","delivery","where","arrived","dispatch"],
        "turns": [
            "Let me pull up your order details right away. Can you confirm the email address on your account?",
            "Got it — I can see your order. It shipped yesterday and is currently in transit with an estimated delivery of tomorrow by 8pm.",
            "Your package is one stop away. You'll get a push notification the moment it's out for delivery."],
        "data": {
            "sentiment":62,"intent_confidence":88,"resolution_likelihood":78,"escalation_risk":10,
            "memory_nodes":["observations"],
            "signals":[
                {"icon":"🧠","tag":"mem","msg":"Intent: order tracking · Observations retrieved"},
                {"icon":"🔵","tag":"orch","msg":"Routed → Order Management flow"},
                {"icon":"📊","tag":"intel","msg":"Confidence 88% · Self-serve path selected"}
            ]
        }
    },
    # 2 — RETURN / REFUND
    {
        "keys": ["cancel","return","refund","send back","money back","wrong item","damaged","broken item"],
        "turns": [
            "I understand — I've already pulled your order history so you won't need to repeat anything. What's the reason for the return?",
            "No problem. I've initiated a return label to your email. Once we receive it, your refund will process within 3–5 business days.",
            "Your refund has been confirmed. You'll get a confirmation email shortly. Is there anything else I can help with?"],
        "data": {
            "sentiment":38,"intent_confidence":91,"resolution_likelihood":70,"escalation_risk":42,
            "memory_nodes":["observations","summary"],
            "signals":[
                {"icon":"⚠️","tag":"alert","msg":"Churn signal detected · Retention flow queued"},
                {"icon":"🧠","tag":"mem","msg":"Order history loaded · Reason captured"},
                {"icon":"🔵","tag":"orch","msg":"Routed → Returns & Refunds flow"}
            ]
        }
    },
    # 3 — FRUSTRATION / ESCALATION
    {
        "keys": ["frustrated","angry","furious","terrible","awful","unacceptable","ridiculous","worst","useless","this is a joke","fed up","sick of","not good enough"],
        "turns": [
            "I'm really sorry — that's not the experience we want you to have at all. I'm escalating this to a senior agent right now who will personally follow up within the hour.",
            "I completely understand your frustration and I'm sorry we've let you down. Your case has been flagged as high priority. A team lead is reviewing it now."],
        "data": {
            "sentiment":14,"intent_confidence":96,"resolution_likelihood":48,"escalation_risk":91,
            "memory_nodes":["identity","observations","summary"],
            "signals":[
                {"icon":"🔴","tag":"alert","msg":"Critical frustration · Human escalation triggered"},
                {"icon":"📊","tag":"intel","msg":"Sentiment: critical (14) · Empathy response applied"},
                {"icon":"🧠","tag":"mem","msg":"Escalation flag written to Memory Store"}
            ]
        }
    },
    # 4 — POSITIVE CLOSE
    {
        "keys": ["thanks","thank you","great","perfect","awesome","resolved","sorted","fixed","that works","you're the best","appreciate"],
        "turns": [
            "So glad I could help! 😊 Is there anything else I can assist you with today?",
            "Wonderful — happy to help anytime! Your satisfaction means a lot to us."],
        "data": {
            "sentiment":94,"intent_confidence":78,"resolution_likelihood":97,"escalation_risk":3,
            "memory_nodes":["summary"],
            "signals":[
                {"icon":"✅","tag":"intel","msg":"Resolution confirmed · CSAT prediction: 4.9/5"},
                {"icon":"🧠","tag":"mem","msg":"Positive outcome stored · Session summary updated"}
            ]
        }
    },
    # 5 — ACCOUNT / LOGIN
    {
        "keys": ["account","password","login","sign in","locked out","email","profile","username","two factor","2fa"],
        "turns": [
            "I've verified your identity. Are you trying to reset your password or update something on the account?",
            "I've sent a secure reset link to your email on file. It expires in 15 minutes — let me know if you need another one.",
            "Your account has been updated. You're all set — is there anything else?"],
        "data": {
            "sentiment":65,"intent_confidence":89,"resolution_likelihood":84,"escalation_risk":8,
            "memory_nodes":["identity","summary"],
            "signals":[
                {"icon":"🔵","tag":"orch","msg":"Identity verified · Account tools unlocked"},
                {"icon":"🧠","tag":"mem","msg":"Identity node updated · Auth context stored"}
            ]
        }
    },
    # 6 — BILLING / PRICING
    {
        "keys": ["price","pricing","plan","upgrade","downgrade","cost","billing","invoice","charge","fee","subscription","tier"],
        "turns": [
            "Based on your current usage, you're on our Starter plan. I can walk you through what each tier includes — which matters most to you: volume, features, or support level?",
            "The Growth plan would save you about 20% given your usage pattern. Want me to apply that change now or send a comparison to your email first?",
            "Done — I've applied the plan change. You'll see it reflected on your next invoice. Anything else I can help with?"],
        "data": {
            "sentiment":70,"intent_confidence":85,"resolution_likelihood":79,"escalation_risk":7,
            "memory_nodes":["observations","summary"],
            "signals":[
                {"icon":"📊","tag":"intel","msg":"Intent: plan evaluation · Usage history loaded"},
                {"icon":"🧠","tag":"mem","msg":"Billing context stored · Offer personalised"},
                {"icon":"🔵","tag":"orch","msg":"Routed → Billing flow"}
            ]
        }
    },
    # 7 — TECHNICAL / NOT WORKING
    {
        "keys": ["not working","broken","error","bug","crash","issue","problem","failed","won't load","can't","doesn't work","glitch"],
        "turns": [
            "I can see there's been an issue on your account. Can you tell me what you were trying to do when it happened?",
            "Thanks — I've reproduced the issue. This is a known bug that our engineering team is actively fixing. I'm adding you to the notification list so you'll hear as soon as it's resolved.",
            "Good news — the fix has been deployed. Can you try again and let me know if it's working for you now?"],
        "data": {
            "sentiment":42,"intent_confidence":87,"resolution_likelihood":65,"escalation_risk":38,
            "memory_nodes":["observations"],
            "signals":[
                {"icon":"⚠️","tag":"alert","msg":"Technical issue detected · Diagnostics run"},
                {"icon":"🔵","tag":"orch","msg":"Routed → Technical Support flow"},
                {"icon":"📊","tag":"intel","msg":"Escalation risk: moderate · Monitoring"}
            ]
        }
    },
    # 8 — SLOW / DELAY
    {
        "keys": ["slow","wait","waiting","delayed","delay","late","long time","taking forever","how long","when will"],
        "turns": [
            "I completely understand — waiting is frustrating. Let me check the status right now.",
            "I can see the delay was caused by a processing backlog earlier today. Things are moving again and your request should complete within the next 30 minutes."],
        "data": {
            "sentiment":35,"intent_confidence":82,"resolution_likelihood":72,"escalation_risk":30,
            "memory_nodes":["observations"],
            "signals":[
                {"icon":"⚠️","tag":"alert","msg":"Delay frustration detected · Proactive update sent"},
                {"icon":"📊","tag":"intel","msg":"Escalation risk: moderate (30%)"},
                {"icon":"🧠","tag":"mem","msg":"Wait context stored · Empathy flag set"}
            ]
        }
    },
    # 9 — COMPETITOR / SWITCHING
    {
        "keys": ["competitor","switch","switching","cancel my account","leave","competitor","other provider","moving to","considering"],
        "turns": [
            "I'm sorry to hear you're thinking about leaving — I'd love to understand what's not working so we can address it. What's been the main pain point?",
            "That's really helpful feedback. Based on what you've shared, I think there are a couple of things we can do right now that might change your mind — can I walk you through them?"],
        "data": {
            "sentiment":25,"intent_confidence":93,"resolution_likelihood":45,"escalation_risk":72,
            "memory_nodes":["identity","observations","summary"],
            "signals":[
                {"icon":"🔴","tag":"alert","msg":"Churn risk: HIGH · Retention flow activated"},
                {"icon":"📊","tag":"intel","msg":"Competitor mention detected · Counter-positioning ready"},
                {"icon":"🧠","tag":"mem","msg":"Churn flag + reason stored in Memory Store"}
            ]
        }
    },
    # 10 — HELLO / GREETING
    {
        "keys": ["hello","hi","hey","good morning","good afternoon","good evening","howdy","sup","yo"],
        "turns": [
            "Hey! Great to have you here. What can I help you with today?",
            "Hi again! I still have your context from earlier — what do you need?"],
        "data": {
            "sentiment":65,"intent_confidence":50,"resolution_likelihood":60,"escalation_risk":5,
            "memory_nodes":["identity"],
            "signals":[
                {"icon":"🔵","tag":"orch","msg":"Session recognised · Context restored"},
                {"icon":"🧠","tag":"mem","msg":"Identity node active · Prior session loaded"}
            ]
        }
    }]

# Tracks how many times each session has matched each flow (for multi-turn progression)
def mock_reply(text: str, session: dict) -> dict:
    t = text.lower()

    if t == "__init__":
        flow = MOCK_FLOWS[0]
        reply = flow["turns"][0]
        data  = flow["data"]
        session["history"].append({"role": "assistant", "content": reply})
        for node in data.get("memory_nodes", []):
            session["memory"][node] = True
        return {"reply": reply, **data, "mock": True}

    # Match flow by keyword
    for i, flow in enumerate(MOCK_FLOWS[1:], start=1):
        if any(k in t for k in flow["keys"]):
            # Multi-turn: cycle through replies so repeated messages progress naturally
            turn_key = f"_turns_{i}"
            turn_idx = session["memory"].get(turn_key, 0)
            reply = flow["turns"][min(turn_idx, len(flow["turns"]) - 1)]
            session["memory"][turn_key] = turn_idx + 1

            data = flow["data"]
            session["history"].append({"role": "user",      "content": text})
            session["history"].append({"role": "assistant", "content": reply})
            for node in data.get("memory_nodes", []):
                session["memory"][node] = True
            return {"reply": reply, **data, "mock": True}

    # Fallback — vary by message count so it doesn't feel robotic
    count = len([h for h in session["history"] if h["role"] == "user"])
    fallbacks = [
        "Got it — I'm looking into that for you right now.",
        "Let me check on that. One moment.",
        "I'm on it — pulling up the details now.",
        "Sure, I can help with that. Can you share a bit more so I look in the right place?"]
    reply = fallbacks[count % len(fallbacks)]
    data = {
        "sentiment": 60, "intent_confidence": 52, "resolution_likelihood": 62, "escalation_risk": 15,
        "memory_nodes": ["observations"],
        "signals": [{"icon":"🔵","tag":"orch","msg":"Processing · Context updated"}]
    }
    session["history"].append({"role": "user",      "content": text})
    session["history"].append({"role": "assistant", "content": reply})
    session["memory"]["context"] = True
    return {"reply": reply, **data, "mock": True}


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

@app.route("/api/validate-creds", methods=["POST"])
def api_validate_creds():
    """Validate credentials before saving — returns {ok, error} per service."""
    data = request.get_json(force=True)
    service = data.get("service", "")  # "anthropic" or "twilio"

    if service == "anthropic":
        key = data.get("key", "").strip()
        if not key:
            return jsonify({"ok": False, "error": "No API key provided."})
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            client.models.list(limit=1)
            return jsonify({"ok": True})
        except Exception as e:
            msg = str(e)
            if "401" in msg or "authentication" in msg.lower() or "invalid" in msg.lower():
                return jsonify({"ok": False, "error": "Invalid API key — check console.anthropic.com → API Keys."})
            return jsonify({"ok": False, "error": f"Could not reach Anthropic: {msg}"})

    elif service == "twilio":
        sid   = data.get("sid", "").strip()
        token = data.get("token", "").strip()
        if not sid or not token:
            return jsonify({"ok": False, "error": "Account SID and Auth Token are both required."})
        try:
            from twilio.rest import Client
            client = Client(sid, token)
            client.api.accounts(sid).fetch()
            return jsonify({"ok": True})
        except Exception as e:
            msg = str(e)
            if "20003" in msg or "authenticate" in msg.lower() or "401" in msg:
                return jsonify({"ok": False, "error": "Invalid credentials — check console.twilio.com → Account Info."})
            return jsonify({"ok": False, "error": f"Could not reach Twilio: {msg}"})

    return jsonify({"ok": False, "error": "Unknown service."}), 400


@app.route("/api/config", methods=["POST"])
def api_config():
    """Accept live credentials from the demo UI, hot-reload them, and optionally provision."""
    global ANTHROPIC_KEY, TWILIO_SID, TWILIO_TOKEN, TWILIO_PHONE, MOCK_MODE
    data = request.get_json(force=True)

    new_anthropic = data.get("anthropic", "").strip()
    new_sid       = data.get("sid", "").strip()
    new_token     = data.get("token", "").strip()
    new_phone     = data.get("twilioNum", "").strip()
    customer_phone = data.get("phone", "").strip()
    do_provision   = data.get("provision", False)

    if new_anthropic:
        ANTHROPIC_KEY = new_anthropic
    if new_sid:
        TWILIO_SID = new_sid
    if new_token:
        TWILIO_TOKEN = new_token
    if new_phone:
        TWILIO_PHONE = new_phone

    MOCK_MODE = not bool(ANTHROPIC_KEY)

    # Persist to .env so creds survive server restarts
    _write_env()

    # Auto-provision: buy a number and wire webhooks if requested
    provision_result = {}
    if do_provision and TWILIO_SID and TWILIO_TOKEN:
        tunnel_url = os.getenv("TUNNEL_URL", "").strip()
        if not tunnel_url:
            provision_result = {"warn": "No tunnel URL found — run bootstrap.sh to start a tunnel, then webhooks will be wired automatically."}
        else:
            try:
                import subprocess, sys
                script = os.path.join(os.path.dirname(__file__), "scripts", "provision.py")
                args_cmd = [
                    sys.executable, script,
                    "--base-url",    tunnel_url,
                    "--account-sid", TWILIO_SID,
                    "--auth-token",  TWILIO_TOKEN,
                ]
                if TWILIO_PHONE:
                    args_cmd += ["--phone-number", TWILIO_PHONE]
                result = subprocess.run(args_cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    # provision.py prints "PHONE:+1..." on success
                    for line in result.stdout.splitlines():
                        if line.startswith("PHONE:"):
                            TWILIO_PHONE = line[6:].strip()
                            _write_env()
                    provision_result = {"provisioned": True, "phone": TWILIO_PHONE}
                else:
                    provision_result = {"warn": f"Provisioning failed: {result.stderr.strip()}"}
            except Exception as e:
                provision_result = {"warn": f"Provisioning error: {e}"}

    # Optionally send a test SMS to the customer's phone
    if customer_phone and TWILIO_PHONE and TWILIO_SID and TWILIO_TOKEN:
        try:
            from twilio.rest import Client
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            client.messages.create(
                body="👋 Your Twilio Conversation Intelligence demo is live! Reply to this message to start a cross-channel experience.",
                from_=TWILIO_PHONE,
                to=customer_phone
            )
        except Exception as e:
            return jsonify({"ok": True, "warn": f"Keys saved but SMS failed: {e}", **provision_result})

    return jsonify({"ok": True, **provision_result})


def _write_env():
    """Persist current in-memory credentials to .env."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()

    def _set(key, val):
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={val}\n"
                return
        lines.append(f"{key}={val}\n")

    _set("ANTHROPIC_API_KEY",    ANTHROPIC_KEY)
    _set("TWILIO_ACCOUNT_SID",   TWILIO_SID)
    _set("TWILIO_AUTH_TOKEN",    TWILIO_TOKEN)
    _set("TWILIO_PHONE_NUMBER",  TWILIO_PHONE)

    with open(env_path, "w") as f:
        f.writelines(lines)


@app.route("/api/verify-caller-id", methods=["POST"])
def api_verify_caller_id():
    """Initiate Twilio caller ID verification — Twilio calls the number with a code."""
    data  = request.get_json(force=True)
    phone = data.get("phone", "").strip()
    if not phone:
        return jsonify({"error": "missing phone"}), 400
    if not TWILIO_SID or not TWILIO_TOKEN:
        return jsonify({"error": "Twilio credentials not configured yet"}), 400
    try:
        from twilio.rest import Client
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        validation = client.validation_requests.create(phone_number=phone)
        return jsonify({"ok": True, "validation_code": validation.validation_code, "phone": phone})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
    return send_from_directory(".", "index.html")

if __name__ == "__main__":
    mode = "MOCK (open browser to add keys)" if MOCK_MODE else "LIVE (Claude + Twilio)"
    print(f"\n  Twilio Conversations Demo")
    print(f"  Mode: {mode}")
    print(f"  URL:  http://localhost:5050")
    if not MOCK_MODE:
        print(f"  SMS webhook:       POST /webhook/sms")
        print(f"  WhatsApp webhook:  POST /webhook/whatsapp")
        print(f"  Voice webhook:     POST /webhook/voice")
    print(f"  Chat API:          POST /api/chat\n")
    port = int(os.getenv("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)
