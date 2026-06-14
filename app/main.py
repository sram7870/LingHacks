from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api import router
import os

app = FastAPI(
    title="LingHacks Scientific Reasoning Backend",
    description="A multi-stage scientific reasoning service for extracting claims, evidence, and controversy graphs from papers.",
    version="0.1.0",
)

app.include_router(router)
app.include_router(router, prefix="/api")

# Serve uploaded files
uploads_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'uploads'))
os.makedirs(uploads_path, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")
