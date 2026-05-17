"""Pydantic models for the metrics API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MetricsValues(BaseModel):
    cpu_load_percent: Optional[float] = Field(None, ge=0, le=100)
    memory_load_percent: Optional[float] = Field(None, ge=0, le=100)
    memory_used_mb: Optional[float] = Field(None, ge=0)
    network_in_bytes: Optional[int] = Field(None, ge=0)
    network_out_bytes: Optional[int] = Field(None, ge=0)
    latency_ms: Optional[float] = Field(None, ge=0)
    power_consumption_w: Optional[float] = Field(None, ge=0)


class MetricsPayload(BaseModel):
    host_id: str = Field(..., min_length=1, max_length=128)
    timestamp: datetime
    metrics: MetricsValues


class MetricsResponse(BaseModel):
    status: str = "ok"
    id: str


class HealthResponse(BaseModel):
    status: str = "ok"
    timestamp: datetime


class ExportFileInfo(BaseModel):
    name: str
    size_bytes: int
    size_mb: float
    modified: datetime
    download_url: str
