from fastapi import APIRouter, Form

router = APIRouter()


def handle_incoming_message(body: str, from_number: str) -> dict:
    """Process an incoming WhatsApp message and return a response payload."""
    print(f"Message from {from_number}: {body}")
    return {"status": "ok"}


@router.post("/webhook")
async def webhook(Body: str = Form(...), From: str = Form(...)):
    return handle_incoming_message(body=Body, from_number=From)
