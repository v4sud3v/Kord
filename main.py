from fastapi import FastAPI, Form
from dotenv import load_dotenv
import uvicorn

from app.handlers import handle_incoming_message

load_dotenv()

app = FastAPI()


@app.post("/webhook")
async def webhook(Body: str = Form(...), From: str = Form(...)):
    return handle_incoming_message(body=Body, from_number=From)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
