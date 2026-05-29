"""
airflow/dags/clean_metrics_dag.py

Hourly data cleaning pipeline:
  extract_raw → validate_schema → remove_duplicates → remove_outliers
             → aggregate_windows → load_clean → export_parquet

Uses XComs to pass data between tasks (suitable for PoC scale).
For production with large data volumes, use GCS intermediate storage instead.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from pymongo import UpdateOne

# Metrics columns to clean / aggregate
METRIC_COLS = [
    "cpu_load_percent",
    "memory_load_percent",
    "memory_used_mb",
    "network_in_bytes",
    "network_out_bytes",
    "latency_ms",
    "power_consumption_w",
]

EXPORTS_DIR = Path("/exports")
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

log = logging.getLogger(__name__)


def _get_hook():
    import sys
    sys.path.insert(0, "/opt/airflow/plugins")
    from mongo_hook import MongoDBHook
    return MongoDBHook()


# ── Task functions ────────────────────────────────────────────────────────────

def extract_raw(**context) -> str:
    """Query raw_metrics for the last 2 hours. Return serialized JSON."""
    hook = _get_hook()
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=2)

    collection = hook.get_collection("raw_metrics")
    docs = list(collection.find(
        {"timestamp": {"$gte": window_start, "$lte": now}},
        {"_id": 0, "host_id": 1, "timestamp": 1, "metrics": 1},
    ))
    hook.close()

    log.info("Extracted %d raw documents from last 2 hours", len(docs))

    # Flatten metrics dict for DataFrame processing
    rows = []
    for doc in docs:
        m = doc.get("metrics", {}) or {}
        row = {
            "host_id": doc["host_id"],
            "timestamp": doc["timestamp"].isoformat() if hasattr(doc["timestamp"], "isoformat") else str(doc["timestamp"]),
        }
        for col in METRIC_COLS:
            row[col] = m.get(col)
        rows.append(row)

    # Push to XCom as JSON string
    context["ti"].xcom_push(key="raw_rows", value=json.dumps(rows))
    return f"extracted_{len(rows)}_rows"


def validate_schema(**context) -> str:
    """Drop rows where ALL metric values are None."""
    rows = json.loads(context["ti"].xcom_pull(key="raw_rows", task_ids="extract_raw"))
    df = pd.DataFrame(rows)

    before = len(df)
    df = df.dropna(subset=METRIC_COLS, how="all")
    after = len(df)

    log.info("Schema validation: dropped %d rows (all-null metrics)", before - after)
    context["ti"].xcom_push(key="validated_rows", value=df.to_json(orient="records"))
    return f"validated_{after}_rows"


def remove_duplicates(**context) -> str:
    """Deduplicate on (host_id, timestamp), keep first occurrence."""
    data = context["ti"].xcom_pull(key="validated_rows", task_ids="validate_schema")
    df = pd.read_json(data, orient="records")

    before = len(df)
    df = df.drop_duplicates(subset=["host_id", "timestamp"], keep="first")
    after = len(df)

    log.info("Deduplication: removed %d duplicate rows", before - after)
    context["ti"].xcom_push(key="deduped_rows", value=df.to_json(orient="records"))
    return f"deduped_{after}_rows"


def remove_outliers(**context) -> str:
    """IQR-based outlier capping per metric (per host_id group)."""
    data = context["ti"].xcom_pull(key="deduped_rows", task_ids="remove_duplicates")
    df = pd.read_json(data, orient="records")

    for col in METRIC_COLS:
        if col not in df.columns:
            continue
        for host_id in df["host_id"].unique():
            mask = df["host_id"] == host_id
            series = df.loc[mask, col].dropna()
            if len(series) < 4:
                continue
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            df.loc[mask, col] = df.loc[mask, col].clip(lower=lower, upper=upper)

    log.info("Outlier capping complete for %d rows", len(df))
    context["ti"].xcom_push(key="cleaned_rows", value=df.to_json(orient="records"))
    return f"cleaned_{len(df)}_rows"


def aggregate_windows(**context) -> str:
    """Aggregate into 1-minute windows: compute mean, min, max per metric per host."""
    data = context["ti"].xcom_pull(key="cleaned_rows", task_ids="remove_outliers")
    df = pd.read_json(data, orient="records")

    if df.empty:
        log.info("No data to aggregate")
        context["ti"].xcom_push(key="aggregated_rows", value="[]")
        return "aggregated_0_rows"

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()

    aggregated = []
    for host_id in df["host_id"].unique():
        host_df = df[df["host_id"] == host_id][METRIC_COLS]
        resampled = host_df.resample("1min")

        means = resampled.mean()
        mins = resampled.min()
        maxs = resampled.max()
        counts = resampled.count()

        for window_start in means.index:
            window_end = window_start + timedelta(minutes=1)
            metrics_agg = {}
            for col in METRIC_COLS:
                metrics_agg[col] = {
                    "mean": round(float(means.loc[window_start, col]), 4) if pd.notna(means.loc[window_start, col]) else None,
                    "min": round(float(mins.loc[window_start, col]), 4) if pd.notna(mins.loc[window_start, col]) else None,
                    "max": round(float(maxs.loc[window_start, col]), 4) if pd.notna(maxs.loc[window_start, col]) else None,
                }

            sample_count = int(counts[METRIC_COLS[0]].get(window_start, 0)) if METRIC_COLS else 0
            aggregated.append({
                "host_id": host_id,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "interval_minutes": 1,
                "sample_count": sample_count,
                "metrics": metrics_agg,
            })

    log.info("Aggregated into %d 1-minute windows", len(aggregated))
    context["ti"].xcom_push(key="aggregated_rows", value=json.dumps(aggregated))
    return f"aggregated_{len(aggregated)}_rows"


def load_clean(**context) -> str:
    """Upsert aggregated documents into clean_metrics collection."""
    data = context["ti"].xcom_pull(key="aggregated_rows", task_ids="aggregate_windows")
    rows = json.loads(data)

    if not rows:
        log.info("No aggregated rows to load")
        return "loaded_0_rows"

    hook = _get_hook()
    collection = hook.get_collection("clean_metrics")
    now = datetime.now(timezone.utc)

    ops = []
    for row in rows:
        window_start_dt = datetime.fromisoformat(row["window_start"])
        window_end_dt = datetime.fromisoformat(row["window_end"])
        doc = {
            **row,
            "window_start": window_start_dt,
            "window_end": window_end_dt,
            "processed_at": now,
        }
        ops.append(UpdateOne(
            {"host_id": row["host_id"], "window_start": window_start_dt},
            {"$set": doc},
            upsert=True,
        ))

    if ops:
        result = collection.bulk_write(ops)
        log.info("Upserted %d clean_metrics documents (%d new, %d modified)",
                 len(ops), result.upserted_count, result.modified_count)

    hook.close()
    return f"loaded_{len(rows)}_rows"


def export_parquet(**context) -> str:
    """Export the current batch to a Parquet file and optionally upload to GCS."""
    data = context["ti"].xcom_pull(key="aggregated_rows", task_ids="aggregate_windows")
    rows = json.loads(data)

    if not rows:
        log.info("No data to export")
        return "exported_0_rows"

    # Flatten for DataFrame
    flat_rows = []
    for row in rows:
        flat = {
            "host_id": row["host_id"],
            "window_start": row["window_start"],
            "window_end": row["window_end"],
            "interval_minutes": row["interval_minutes"],
            "sample_count": row["sample_count"],
        }
        for col, stats in row["metrics"].items():
            flat[f"{col}_mean"] = stats.get("mean")
            flat[f"{col}_min"] = stats.get("min")
            flat[f"{col}_max"] = stats.get("max")
        flat_rows.append(flat)

    df = pd.DataFrame(flat_rows)
    df["window_start"] = pd.to_datetime(df["window_start"], utc=True)
    df["window_end"] = pd.to_datetime(df["window_end"], utc=True)

    run_ts = context["data_interval_start"].strftime("%Y-%m-%d_%H%M")
    filename = f"metrics_{run_ts}.parquet"
    local_path = EXPORTS_DIR / filename

    table = pa.Table.from_pandas(df)
    pq.write_table(table, str(local_path), compression="snappy")
    log.info("Wrote Parquet file: %s (%d bytes)", local_path, local_path.stat().st_size)

    # Optional: upload to GCS
    gcs_bucket = os.environ.get("GCS_BUCKET_NAME") or Variable.get("gcs_bucket", default_var=None)
    if gcs_bucket:
        try:
            from google.cloud import storage as gcs
            client = gcs.Client()
            bucket = client.bucket(gcs_bucket)
            blob = bucket.blob(f"parquet/{filename}")
            blob.upload_from_filename(str(local_path))
            log.info("Uploaded to gs://%s/parquet/%s", gcs_bucket, filename)
        except Exception as exc:
            log.warning("GCS upload failed (non-fatal): %s", exc)

    return f"exported_{len(rows)}_rows_to_{filename}"


# ── DAG definition ────────────────────────────────────────────────────────────

default_args = {
    "owner": "metrics",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
}

with DAG(
    dag_id="clean_metrics",
    description="Hourly pipeline: extract raw metrics → clean → aggregate → load → export Parquet",
    schedule="@hourly",
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    default_args=default_args,
    tags=["metrics", "cleaning"],
) as dag:

    t_extract = PythonOperator(task_id="extract_raw", python_callable=extract_raw)
    t_validate = PythonOperator(task_id="validate_schema", python_callable=validate_schema)
    t_dedup = PythonOperator(task_id="remove_duplicates", python_callable=remove_duplicates)
    t_outliers = PythonOperator(task_id="remove_outliers", python_callable=remove_outliers)
    t_aggregate = PythonOperator(task_id="aggregate_windows", python_callable=aggregate_windows)
    t_load = PythonOperator(task_id="load_clean", python_callable=load_clean)
    t_export = PythonOperator(task_id="export_parquet", python_callable=export_parquet)

    t_extract >> t_validate >> t_dedup >> t_outliers >> t_aggregate >> [t_load, t_export]
