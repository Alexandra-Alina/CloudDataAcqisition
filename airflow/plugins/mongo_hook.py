"""Custom MongoDB hook for Apache Airflow using connection URI from Airflow Variables."""

import os
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database


class MongoDBHook:
    """Simple MongoDB connection wrapper for use in Airflow DAG tasks.

    Reads the MongoDB URI from:
    1. Airflow Variable 'mongodb_uri' (if available)
    2. Environment variable MONGODB_URI (fallback)
    """

    def __init__(self, db_name: str = "metrics_db"):
        self.db_name = db_name
        self._client: MongoClient | None = None

    def _get_uri(self) -> str:
        try:
            from airflow.models import Variable
            uri = Variable.get("mongodb_uri", default_var=None)
            if uri:
                return uri
        except Exception:
            pass
        uri = os.environ.get("MONGODB_URI")
        if not uri:
            raise ValueError("MongoDB URI not found in Airflow Variables or MONGODB_URI env var")
        return uri

    def get_client(self) -> MongoClient:
        if self._client is None:
            self._client = MongoClient(self._get_uri(), serverSelectionTimeoutMS=10000)
        return self._client

    def get_db(self) -> Database:
        return self.get_client()[self.db_name]

    def get_collection(self, collection_name: str) -> Any:
        return self.get_db()[collection_name]

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
