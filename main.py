from fastapi import FastAPI
from dotenv import load_dotenv
import uvicorn

from routers.webhook import router as webhook_router

load_dotenv()

app = FastAPI()

app.include_router(webhook_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
