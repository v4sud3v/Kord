"""Tool: Send a WhatsApp message via Twilio.

Uses the Twilio REST API to send a text message back to the student
on WhatsApp. This is how the agent's replies actually reach the user.
"""

from __future__ import annotations

import os

import httpx


def get_twilio_credentials() -> tuple[str, str, str]:
    """Return (account_sid, auth_token, whatsapp_from)."""
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM", "")
    if not sid or not token:
        raise RuntimeError(
            "TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set"
        )
    if not from_number:
        raise RuntimeError("TWILIO_WHATSAPP_FROM must be set")
    return sid, token, from_number


async def send_whatsapp(to: str, message: str) -> dict:
    """
    Send a WhatsApp message to the given number via Twilio.

    Args:
        to: The recipient's WhatsApp number (e.g. "whatsapp:+919876543210")
        message: The text message to send

    Returns:
        dict with "sid" and "status" from Twilio
    """
    sid, token, from_number = get_twilio_credentials()

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"

    async with httpx.AsyncClient(auth=(sid, token)) as client:
        resp = await client.post(
            url,
            data={
                "From": from_number,
                "To": to,
                "Body": message,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    print(f"[twilio] Sent message to {to} (SID: {data.get('sid', '?')})")
    return {"sid": data.get("sid", ""), "status": data.get("status", "")}


def format_scholarship_reply(result: dict) -> str:
    """
    Format the full agent response into a WhatsApp-friendly message.

    Takes the result dict from check_session and builds a readable message.
    """
    reply = result.get("reply", "")
    matched = result.get("matched_scholarships", [])

    if not result.get("all_keys_collected", False):
        # Still collecting info — just send the follow-up question
        return reply

    # All keys collected — build the full scholarship report
    parts = [reply, ""]  # reply + blank line

    if matched:
        for i, s in enumerate(matched[:10], 1):  # Max 10 scholarships
            parts.append(f"*{i}. {s['name']}*")
            if s.get("eligibility_summary"):
                parts.append(f"   📋 {s['eligibility_summary']}")
            if s.get("benefits"):
                parts.append(f"   💰 {s['benefits']}")
            if s.get("url"):
                parts.append(f"   🔗 {s['url']}")
            parts.append("")  # blank line between scholarships

        parts.append(
            f"_Found {len(matched)} scholarship(s) matching your profile._"
        )
        parts.append(
            "_Show this message to your school headmaster to apply!_"
        )
    else:
        parts.append(
            "I couldn't find matching scholarships right now. "
            "The database may still be loading — try again in a few minutes."
        )

    return "\n".join(parts)
