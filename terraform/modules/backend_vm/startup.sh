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

# ── Install gcloud (for Secret Manager access) ──────────────────────────────
if ! command -v gcloud &>/dev/null; then
  curl -sSL https://sdk.cloud.google.com | bash -s -- --disable-prompts
  source /root/google-cloud-sdk/path.bash.inc
fi

# ── Clone repository ─────────────────────────────────────────────────────────
REPO_DIR="/opt/CloudDataAquisition"
if [ ! -d "$REPO_DIR" ]; then
  git clone "${REPO_URL}" "$REPO_DIR"
fi
cd "$REPO_DIR/backend"

# ── Pull secrets from Secret Manager ────────────────────────────────────────
MONGODB_URI=$(gcloud secrets versions access latest --secret="mongodb-uri" --quiet 2>/dev/null || echo "")
BACKEND_API_KEY=$(gcloud secrets versions access latest --secret="backend-api-key" --quiet 2>/dev/null || echo "")

cat > .env <<EOF
MONGODB_URI=$${MONGODB_URI}
BACKEND_API_KEY=$${BACKEND_API_KEY}
EXPORTS_DIR=/app/exports
EOF

# ── Start backend ────────────────────────────────────────────────────────────
docker compose pull || true
docker compose up -d --build

echo "Backend started. Health check:"
sleep 10
curl -s http://localhost:8000/health || echo "Health check pending — container may still be starting"
