from fastapi import FastAPI
from app.api import router

app = FastAPI(
    title="LingHacks Scientific Reasoning Backend",
    description="A multi-stage scientific reasoning service for extracting claims, evidence, and controversy graphs from papers.",
    version="0.1.0",
)

app.include_router(router)


@app.get("/health", tags=["Health"])
def health_check() -> dict:
    return {"status": "ok"}
