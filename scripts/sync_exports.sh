#!/bin/bash
# scripts/sync_exports.sh
#
# Sync Parquet files from the services VM (Airflow/Jupyter) to the backend VM's
# exports directory, so the FastAPI /exports endpoint can serve them.
#
# Run this as a cron job on the BACKEND VM:
#   */10 * * * * /opt/CloudDataAquisition/scripts/sync_exports.sh >> /var/log/sync_exports.log 2>&1
#
# Or run ad-hoc:
#   SERVICES_VM_IP=1.2.3.4 bash sync_exports.sh
#
# Prerequisites on backend VM:
#   - SSH key configured for passwordless access to services VM
#   - rsync installed

set -euo pipefail

SERVICES_VM_IP="${SERVICES_VM_IP:-}"
SERVICES_VM_USER="${SERVICES_VM_USER:-ubuntu}"
REMOTE_EXPORTS_DIR="${REMOTE_EXPORTS_DIR:-/var/lib/docker/volumes/airflow_exports_vol/_data}"
LOCAL_EXPORTS_DIR="${LOCAL_EXPORTS_DIR:-/var/lib/docker/volumes/metrics_exports_data/_data}"

if [ -z "$SERVICES_VM_IP" ]; then
    echo "ERROR: SERVICES_VM_IP is not set."
    echo "Usage: SERVICES_VM_IP=10.0.1.5 bash sync_exports.sh"
    exit 1
fi

echo "[$(date -Iseconds)] Starting export sync from ${SERVICES_VM_USER}@${SERVICES_VM_IP}:${REMOTE_EXPORTS_DIR}"

# Ensure local directory exists
mkdir -p "$LOCAL_EXPORTS_DIR"

# Sync only .parquet files (non-destructive — never deletes local files)
rsync -avz \
    --include="*.parquet" \
    --exclude="*" \
    -e "ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10" \
    "${SERVICES_VM_USER}@${SERVICES_VM_IP}:${REMOTE_EXPORTS_DIR}/" \
    "${LOCAL_EXPORTS_DIR}/"

echo "[$(date -Iseconds)] Sync complete. Files in ${LOCAL_EXPORTS_DIR}:"
ls -lh "$LOCAL_EXPORTS_DIR"/*.parquet 2>/dev/null || echo "  (no .parquet files yet)"
