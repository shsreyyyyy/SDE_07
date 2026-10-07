from fastapi import FastAPI
from .api.routes import router
from .config import UPLOAD_DIR, PROCESSED_DIR

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Geospatial File Measurement API",
    version="1.0.0",
    description="Upload KML or zipped Shapefile data and retrieve CRS-safe measurements.",
)
app.include_router(router, prefix="/api")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
