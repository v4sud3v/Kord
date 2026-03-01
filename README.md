# Kord

A WhatsApp AI Agent (assistant) that helps low-income Kerala students discover and claim government scholarships — without touching a single portal.

---

## the problem

Most students who qualify for scholarships like e-Grantz, Prathibha, or Unnathi never apply. The portals are confusing, the documents are in English, and nobody tells them they even qualify. The money sits unclaimed.

---

## how it works

A student sends a voice note in Malayalam describing their situation. Kord transcribes it, extracts the relevant details, matches them against Kerala's scholarship eligibility rules, and replies with a formatted text block the student can hand to their school headmaster. The teacher submits it. The student does nothing else.

---

## pipeline

```
WhatsApp voice note (Malayalam)
        ↓
Twilio → FastAPI (audio streamed in memory, nothing saved to disk)
        ↓
Sarvam AI (saaras:v2.5) — transcription + translation
        ↓
Groq — extracts Age, Grade, Income, Caste, Location as JSON
        ↓
Local matcher — checks against Kerala scholarship eligibility rules
        ↓
Twilio sends the result back to the student
```

---

## stack

| layer | tool |
|---|---|
| backend | Python + FastAPI |
| WhatsApp | Twilio Sandbox |
| speech-to-text | Sarvam AI |
| entity extraction | Groq |
| tunnel | ngrok |

---

## setup

**Requirements:** Python 3.14+, [uv](https://github.com/astral-sh/uv), ngrok

**Dependencies** (managed via `pyproject.toml`, installed automatically with `uv sync`):
- `fastapi[standard]`
- `uvicorn`
- `httpx`
- `python-dotenv`
- `python-multipart`
- `sarvamai`

**Dev dependencies:** `pytest`, `pytest-asyncio`

```bash
git clone <your-repo-url>
cd Kord
uv sync
```

Create a `.env` file:
```env
SARVAM_API_KEY=your_sarvam_key
GROQ_API_KEY=your_groq_key
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_twilio_auth_token
```

```bash
uv run fastapi dev main.py
ngrok http 8000
```

Set the Twilio sandbox webhook to `https://<your-ngrok-url>/webhook`, join the sandbox, and send a voice note.

---

## tests

```bash
uv run pytest -v
```
