"""Async MongoDB connection via Motor."""

import os
from motor.motor_asyncio import AsyncIOMotorClient

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        uri = os.environ["MONGODB_URI"]
        _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    return _client


def get_db():
    return get_client()["metrics_db"]


def get_raw_collection():
    return get_db()["raw_metrics"]


def get_clean_collection():
    return get_db()["clean_metrics"]


async def close_client():
    global _client
    if _client is not None:
        _client.close()
        _client = None
