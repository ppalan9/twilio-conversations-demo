#!/usr/bin/env python3
"""
provision.py — Buy a Twilio number and wire all demo webhooks.

Called by bootstrap.sh. Can also be run standalone:
  uv run python scripts/provision.py \
    --base-url https://abc.ngrok.io \
    --account-sid ACxxx \
    --auth-token xxx

Flags:
  --phone-number +1...     Skip buying; use existing number
  --update-webhooks-only   Only update webhooks, don't buy or output PHONE:
  --area-code 415          Preferred area code for new number (default: 415)
"""

import argparse, sys
from twilio.rest import Client


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url",          required=True)
    p.add_argument("--account-sid",       required=True)
    p.add_argument("--auth-token",        required=True)
    p.add_argument("--phone-number",      default="")
    p.add_argument("--update-webhooks-only", action="store_true")
    p.add_argument("--area-code",         default="415")
    return p.parse_args()


def buy_number(client: Client, area_code: str) -> str:
    available = client.available_phone_numbers("US") \
        .local.list(area_code=area_code, voice_enabled=True, sms_enabled=True, limit=1)

    if not available:
        available = client.available_phone_numbers("US") \
            .local.list(voice_enabled=True, sms_enabled=True, limit=1)

    if not available:
        print("ERROR: No available numbers found", file=sys.stderr)
        sys.exit(1)

    purchased = client.incoming_phone_numbers.create(
        phone_number=available[0].phone_number
    )
    return purchased.phone_number


def update_webhooks(client: Client, phone_number: str, base_url: str):
    numbers = client.incoming_phone_numbers.list(phone_number=phone_number, limit=1)
    if not numbers:
        print(f"ERROR: Phone number {phone_number} not found in account", file=sys.stderr)
        sys.exit(1)

    sid = numbers[0].sid
    client.incoming_phone_numbers(sid).update(
        sms_url=f"{base_url}/webhook/sms",
        sms_method="POST",
        voice_url=f"{base_url}/webhook/voice",
        voice_method="POST",
    )

    # WhatsApp sandbox uses a separate resource; skip if not configured
    try:
        sandboxes = client.messaging.v1.services.list(limit=5)
        for svc in sandboxes:
            if "sandbox" in (svc.friendly_name or "").lower():
                client.messaging.v1.services(svc.sid).update(
                    inbound_request_url=f"{base_url}/webhook/whatsapp"
                )
                break
    except Exception:
        pass  # WhatsApp sandbox optional — don't fail bootstrap


def main():
    args = parse_args()
    client = Client(args.account_sid, args.auth_token)

    phone = args.phone_number

    if not args.update_webhooks_only:
        if not phone:
            phone = buy_number(client, args.area_code)

    update_webhooks(client, phone, args.base_url)

    if not args.update_webhooks_only:
        # bootstrap.sh reads this line to extract the number
        print(f"PHONE:{phone}")


if __name__ == "__main__":
    main()
