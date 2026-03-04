"""Webhook router — thin dispatcher that delegates to the agent.

The agent orchestrator handles the entire pipeline.
This route parses the Twilio form data, calls the right handler,
and sends the reply back to WhatsApp.
"""

from typing import Optional

from fastapi import APIRouter, Form

from agent.agent import handle_audio_message, handle_text_message
from agent.tools.send_whatsapp import send_whatsapp, format_scholarship_reply

router = APIRouter()


@router.post("/webhook")
async def webhook(
    Body: str = Form(""),
    From: str = Form(...),
    NumMedia: int = Form(0),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
):
    # 1. Process through the agent pipeline
    if NumMedia > 0 and MediaUrl0:
        result = await handle_audio_message(
            media_url=MediaUrl0,
            content_type=MediaContentType0 or "",
            from_number=From,
        )
    else:
        result = await handle_text_message(text=Body, from_number=From)

    # 2. Format and send the reply to WhatsApp
    message = format_scholarship_reply(result)
    try:
        await send_whatsapp(to=From, message=message)
    except Exception as e:
        print(f"[webhook] ⚠ Failed to send WhatsApp reply to {From}: {e}")
        result["whatsapp_send_error"] = str(e)

    # 3. Return the full result JSON (useful for debugging / tests)
    return result

