"""Webhook router — thin dispatcher that delegates to the agent.

The agent orchestrator handles the entire pipeline.
This route just parses the Twilio form data and calls the right handler.
"""

from typing import Optional

from fastapi import APIRouter, Form

from agent.agent import handle_audio_message, handle_text_message

router = APIRouter()


@router.post("/webhook")
async def webhook(
    Body: str = Form(""),
    From: str = Form(...),
    NumMedia: int = Form(0),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
):
    if NumMedia > 0 and MediaUrl0:
        return await handle_audio_message(
            media_url=MediaUrl0,
            content_type=MediaContentType0 or "",
            from_number=From,
        )
    return await handle_text_message(text=Body, from_number=From)
