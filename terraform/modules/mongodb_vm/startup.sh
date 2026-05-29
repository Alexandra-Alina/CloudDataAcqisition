#!/bin/bash
set -euo pipefail

# ── Install Docker ──────────────────────────────────────────────────────────
apt-get update -y
apt-get install -y ca-certificates curl gnupg

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

# ── Install gcloud (required for Secret Manager access) ──────────────────────
if ! command -v gcloud &>/dev/null; then
  curl -sSL https://sdk.cloud.google.com | bash -s -- --disable-prompts
  source /root/google-cloud-sdk/path.bash.inc
fi

# ── Read credentials from Secret Manager ────────────────────────────────────
MONGO_USER=$(gcloud secrets versions access latest --secret="mongodb-username" --quiet 2>/dev/null || echo "metrics_user")
MONGO_PASS=$(gcloud secrets versions access latest --secret="mongodb-password" --quiet 2>/dev/null || echo "")

if [ -z "$MONGO_PASS" ]; then
  echo "ERROR: Secret 'mongodb-password' is empty or not set. Exiting."
  exit 1
fi

# ── Persistent data directory ────────────────────────────────────────────────
mkdir -p /data/mongodb
chown -R 999:999 /data/mongodb   # MongoDB container user UID

# ── Write docker-compose for MongoDB ────────────────────────────────────────
cat > /opt/docker-compose.mongodb.yml <<EOF
services:
  mongodb:
    image: mongo:7.0
    container_name: mongodb
    restart: unless-stopped
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${MONGO_USER}
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_PASS}
      MONGO_INITDB_DATABASE: metrics_db
    command: mongod --auth --bind_ip_all --wiredTigerCacheSizeGB 0.25
    volumes:
      - /data/mongodb:/data/db
    ports:
      - "27017:27017"
    healthcheck:
      test: ["CMD", "mongosh", "--quiet", "--eval", "db.adminCommand('ping').ok"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
    deploy:
      resources:
        limits:
          memory: 400m
EOF

docker compose -f /opt/docker-compose.mongodb.yml up -d

echo "MongoDB started. Waiting for ready state..."
sleep 20

# ── Create metrics_db user with readWrite role ───────────────────────────────
docker exec mongodb mongosh \
  --username "$MONGO_USER" \
  --password "$MONGO_PASS" \
  --authenticationDatabase admin \
  --eval "
    db = db.getSiblingDB('admin');
    db.createUser({
      user: '${MONGO_USER}',
      pwd: '${MONGO_PASS}',
      roles: [{ role: 'readWrite', db: 'metrics_db' }]
    });
    print('metrics_db user created in admin db');
  " 2>/dev/null || echo "User may already exist — skipping."

echo "MongoDB initialization complete."
echo "Internal IP: $(hostname -I | awk '{print $1}')"
echo "Connection URI: mongodb://${MONGO_USER}:<password>@$(hostname -I | awk '{print $1}'):27017/metrics_db?authSource=admin"
