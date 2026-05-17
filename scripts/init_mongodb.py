"""
scripts/init_mongodb.py

One-time setup: create MongoDB collections and indexes.

Usage:
    MONGODB_URI="mongodb://metrics_user:PASS@10.0.1.X:27017/metrics_db?authSource=admin" python init_mongodb.py

Run this after:
  1. terraform apply completes and the MongoDB VM is running
  2. Secrets (mongodb-username, mongodb-password) are set in Secret Manager
  3. The MongoDB VM startup script has finished (allow ~3 minutes)

Get the MongoDB internal IP:
    terraform output mongodb_internal_ip
"""

import os
import sys
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, OperationFailure

MONGODB_URI = os.environ.get("MONGODB_URI")
if not MONGODB_URI:
    print("ERROR: MONGODB_URI environment variable is not set.")
    sys.exit(1)


def main():
    print("Connecting to MongoDB...")
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=10000)

    try:
        client.admin.command("ping")
        print("Connected.")
    except ConnectionFailure as e:
        print(f"ERROR: Could not connect to MongoDB: {e}")
        sys.exit(1)

    db = client["metrics_db"]

    # ── raw_metrics ───────────────────────────────────────────────────────────
    print("\nSetting up 'raw_metrics' collection...")
    raw = db["raw_metrics"]

    # Compound index: efficient time-range queries per host
    raw.create_index(
        [("host_id", ASCENDING), ("timestamp", DESCENDING)],
        name="host_timestamp_idx",
        background=True,
    )
    print("  Created index: host_id + timestamp (compound)")

    # TTL index: auto-delete raw documents after 30 days
    raw.create_index(
        [("timestamp", ASCENDING)],
        name="raw_ttl_idx",
        expireAfterSeconds=30 * 24 * 3600,
        background=True,
    )
    print("  Created index: timestamp TTL (30 days)")

    # ── clean_metrics ─────────────────────────────────────────────────────────
    print("\nSetting up 'clean_metrics' collection...")
    clean = db["clean_metrics"]

    # Compound index for time-range queries per host
    clean.create_index(
        [("host_id", ASCENDING), ("window_start", DESCENDING)],
        name="host_window_idx",
        background=True,
    )
    print("  Created index: host_id + window_start (compound)")

    # Unique constraint to prevent duplicate aggregation windows
    clean.create_index(
        [("host_id", ASCENDING), ("window_start", ASCENDING)],
        name="host_window_unique_idx",
        unique=True,
        background=True,
    )
    print("  Created index: host_id + window_start (unique, for upserts)")

    # ── Verify ────────────────────────────────────────────────────────────────
    print("\nIndex summary:")
    for coll_name in ["raw_metrics", "clean_metrics"]:
        coll = db[coll_name]
        indexes = list(coll.list_indexes())
        print(f"\n  {coll_name}:")
        for idx in indexes:
            print(f"    {idx['name']}: {idx['key']}")

    print("\nMongoDB initialization complete.")
    client.close()


if __name__ == "__main__":
    main()
