"""
Output module — response generation, TTS, and PDF creation.

Responsibilities:
  - Build friendly reply text from eligibility results or missing-field prompts.
  - Convert reply text to Malayalam audio (TTS) via Bhashini or gTTS.
  - Generate a summary PDF using fpdf2 for the school principal.
  - Send the reply (text + optional media) back via the Twilio client.
"""

from __future__ import annotations

import os
from io import BytesIO
from typing import Any

from fpdf import FPDF
from twilio.rest import Client


def build_reply_text(
    eligible: list[dict[str, Any]],
    missing: list[str],
) -> str:
    """
    Build the plain-English reply string.

    - If *missing* is non-empty, ask for the next missing field.
    - If *eligible* is non-empty, list the matching scholarships.
    - Otherwise tell the user no matching scholarships were found.
    """
    if missing:
        field = missing[0]
        prompts = {
            "age": "Could you tell me the student's age?",
            "grade": "Which school grade (1–12) is the student currently in?",
            "caste": "What is the student's caste category? (SC / ST / OBC / General)",
            "income": "What is the approximate annual household income in rupees?",
        }
        return prompts.get(field, f"Please provide the student's {field}.")

    if eligible:
        names = ", ".join(s["name"] for s in eligible)
        docs = eligible[0]["documents"]
        doc_list = "\n".join(f"  • {d}" for d in docs)
        return (
            f"Great news! The student is eligible for: {names}.\n\n"
            f"Required documents for {eligible[0]['name']}:\n{doc_list}\n\n"
            "Please bring these to your school principal."
        )

    return (
        "Based on the information provided, no matching scholarships were found. "
        "Please check with your school for additional options."
    )


def generate_pdf(profile: dict[str, Any], eligible: list[dict[str, Any]]) -> bytes:
    """
    Create a summary PDF and return its raw bytes.

    TODO: add Malayalam font support for localised PDFs.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=14)
    pdf.cell(0, 10, "Kord — Scholarship Eligibility Summary", ln=True, align="C")
    pdf.ln(5)

    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, "Student Profile", ln=True)
    pdf.set_font("Helvetica", size=10)
    for key, value in profile.items():
        pdf.cell(0, 7, f"  {key.capitalize()}: {value}", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, "Eligible Scholarships", ln=True)
    pdf.set_font("Helvetica", size=10)
    for s in eligible:
        pdf.cell(0, 7, f"  • {s['name']}: {s['description']}", ln=True)
        pdf.cell(0, 7, f"    Documents: {', '.join(s['documents'])}", ln=True)

    return bytes(pdf.output())


def send_whatsapp_reply(to: str, body: str, pdf_bytes: bytes | None = None) -> None:
    """
    Send a WhatsApp message back to *to* via Twilio.

    If *pdf_bytes* is provided it is sent as a media attachment.
    NOTE: Twilio requires a publicly accessible URL for media; uploading
    the PDF is left as a TODO (use S3, Cloudinary, etc.).
    """
    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    from_number = os.environ["TWILIO_WHATSAPP_FROM"]

    # TODO: upload pdf_bytes to a public URL and pass it as media_url
    client.messages.create(body=body, from_=from_number, to=to)
