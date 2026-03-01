def handle_incoming_message(body: str, from_number: str) -> dict:
    """Process an incoming WhatsApp message and return a response payload."""
    print(f"Message from {from_number}: {body}")
    return {"status": "ok"}
