#!/bin/bash
set -euo pipefail

# ── Install Docker ──────────────────────────────────────────────────────────
apt-get update -y
apt-get install -y ca-certificates curl gnupg git

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

systemctl enable docker
systemctl start docker

# ── Install gcloud ───────────────────────────────────────────────────────────
if ! command -v gcloud &>/dev/null; then
  curl -sSL https://sdk.cloud.google.com | bash -s -- --disable-prompts
  source /root/google-cloud-sdk/path.bash.inc
fi

# ── Clone repository ─────────────────────────────────────────────────────────
REPO_DIR="/opt/CloudDataAquisition"
if [ ! -d "$REPO_DIR" ]; then
  git clone "${REPO_URL}" "$REPO_DIR"
fi

# ── Pull secrets ─────────────────────────────────────────────────────────────
MONGODB_URI=$(gcloud secrets versions access latest --secret="mongodb-uri" --quiet 2>/dev/null || echo "")
# GCS bucket name is not sensitive — injected directly by Terraform templatefile
GCS_BUCKET="${GCS_BUCKET_NAME}"

# ── Set up Airflow ───────────────────────────────────────────────────────────
cd "$REPO_DIR/airflow"

cat > .env <<EOF
MONGODB_URI=$${MONGODB_URI}
GCS_BUCKET_NAME=$${GCS_BUCKET}
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
AIRFLOW__CORE__FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")
AIRFLOW__WEBSERVER__SECRET_KEY=$(cat /proc/sys/kernel/random/uuid)
AIRFLOW_UID=$(id -u)
EOF

mkdir -p logs plugins
docker compose up -d --build

# ── Set up JupyterLab ────────────────────────────────────────────────────────
cd "$REPO_DIR/analytics"

cat > .env <<EOF
MONGODB_URI=$${MONGODB_URI}
GCS_BUCKET_NAME=$${GCS_BUCKET}
EOF

mkdir -p exports
docker compose up -d --build

echo "Services VM startup complete."
echo "Airflow: http://localhost:8080"
echo "JupyterLab token: $(docker compose -f /opt/CloudDataAquisition/analytics/docker-compose.yml logs jupyter 2>&1 | grep 'token=' | tail -1)"
