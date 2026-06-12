import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI

from routes.webhook import router as webhook_router

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="Multi-Agent AI Code Review",
    version="1.0.0",
    description="GitHub pull request reviews powered by LangGraph and Ollama.",
)

app.include_router(webhook_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
