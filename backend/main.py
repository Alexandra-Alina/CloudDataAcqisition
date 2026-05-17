"""
backend/main.py
FastAPI HTTP backend for metrics ingestion and Parquet file serving.

Endpoints:
    POST /metrics              — ingest a metrics payload (requires X-API-Key)
    GET  /health               — health check
    GET  /exports              — list available Parquet files (requires X-API-Key)
    GET  /exports/{filename}   — download a Parquet file (requires X-API-Key)
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()  # Load .env before anything else

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import database
import exports as exports_router
from auth import verify_api_key
from models import HealthResponse, MetricsPayload, MetricsResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify MongoDB connection on startup
    try:
        await database.get_client().admin.command("ping")
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("MongoDB ping failed: %s", exc)
    yield
    await database.close_client()


app = FastAPI(
    title="Metrics Ingestion API",
    description="Receives timeseries system metrics and stores them in MongoDB.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(exports_router.router)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    return HealthResponse(timestamp=datetime.now(timezone.utc))


@app.post("/metrics", response_model=MetricsResponse, tags=["metrics"])
async def ingest_metrics(
    payload: MetricsPayload,
    _: str = Depends(verify_api_key),
):
    """Receive a metrics payload and store it in the raw_metrics collection."""
    collection = database.get_raw_collection()

    doc = {
        "host_id": payload.host_id,
        "timestamp": payload.timestamp,
        "ingested_at": datetime.now(timezone.utc),
        "metrics": payload.metrics.model_dump(exclude_none=False),
    }

    result = await collection.insert_one(doc)
    return MetricsResponse(id=str(result.inserted_id))


@app.get("/metrics/latest", tags=["metrics"])
async def get_latest_metrics(
    host_id: str,
    limit: int = 100,
    _: str = Depends(verify_api_key),
):
    """Return the most recent N raw metric documents for a given host."""
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")

    collection = database.get_raw_collection()
    cursor = collection.find(
        {"host_id": host_id},
        {"_id": 0},
    ).sort("timestamp", -1).limit(limit)

    docs = await cursor.to_list(length=limit)
    # Convert datetime objects to ISO strings for JSON serialization
    for doc in docs:
        if "timestamp" in doc:
            doc["timestamp"] = doc["timestamp"].isoformat()
        if "ingested_at" in doc:
            doc["ingested_at"] = doc["ingested_at"].isoformat()
    return docs
