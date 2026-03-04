"""FastAPI application entry point with scholarship DB lifecycle."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB + background-refresh stale scholarship data."""
    from data.db import init_db
    from scrapers import refresh_if_stale

    print("\n🚀 Kord starting up...")

    # 1. Verify Supabase connection
    try:
        init_db()
    except Exception as e:
        print(f"⚠ DB init failed (scholarships won't work): {e}")

    # 2. Refresh stale scholarship data in the background
    #    (doesn't block startup — the app is usable immediately)
    async def _background_refresh():
        try:
            await refresh_if_stale(max_age_hours=24)
        except Exception as e:
            print(f"⚠ Background scholarship refresh failed: {e}")

    asyncio.create_task(_background_refresh())

    yield  # app is running

    print("👋 Kord shutting down...")


app = FastAPI(title="Kord", lifespan=lifespan)

# Import router AFTER app is created
from routers.webhook import router  # noqa: E402

app.include_router(router)
