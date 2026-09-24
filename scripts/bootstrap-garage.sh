#!/bin/sh
# One-time Garage bootstrap for the WSS Map Processing Platform (POSIX).
#
# The official Garage image is distroless (no shell), so the Garage CLI is run
# inside the running `garage` container via `docker compose exec`.
#
# Usage:
#   docker compose up -d --build postgres redis garage garage-cors
#   sh scripts/bootstrap-garage.sh
set -eu

cd "$(dirname "$0")/.."

BUCKET="${S3_BUCKET:-wss}"
KEY_NAME="wss-app"
CONFIG="/etc/garage.toml"

garage() {
    docker compose exec -T garage /garage -c "$CONFIG" "$@"
}

echo "[bootstrap] waiting for the garage container..."
i=0
until garage status >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -gt 60 ]; then
        echo "[bootstrap] garage did not become ready in time" >&2
        exit 1
    fi
    sleep 3
done

NODE_ID="$(garage node id 2>/dev/null | head -n1 | cut -d@ -f1 | tr -d '\r\n ')"
echo "[bootstrap] node id: $NODE_ID"

if ! garage layout show 2>/dev/null | grep -q "$NODE_ID"; then
    echo "[bootstrap] applying single-node cluster layout"
    garage layout assign -z dc1 -c 1G "$NODE_ID" || true
    garage layout apply --version 1 || true
fi

if ! garage bucket list 2>/dev/null | grep -qw "$BUCKET"; then
    echo "[bootstrap] creating bucket '$BUCKET'"
    garage bucket create "$BUCKET"
fi

if ! garage key info "$KEY_NAME" >/dev/null 2>&1; then
    echo "[bootstrap] creating access key '$KEY_NAME'"
    garage key create "$KEY_NAME"
fi

garage bucket allow --read --write --owner "$BUCKET" --key "$KEY_NAME" || true

INFO="$(garage key info --show-secret "$KEY_NAME")"
ACCESS_KEY="$(printf '%s\n' "$INFO" | awk -F': *' '/Key ID/ {print $2; exit}' | tr -d '\r\n ')"
SECRET_KEY="$(printf '%s\n' "$INFO" | awk -F': *' '/Secret key/ {print $2; exit}' | tr -d '\r\n ')"

if [ -z "$ACCESS_KEY" ] || [ -z "$SECRET_KEY" ]; then
    echo "[bootstrap] could not parse credentials" >&2
    exit 1
fi

mkdir -p infra/garage/credentials
printf '%s' "$ACCESS_KEY" > infra/garage/credentials/access_key
printf '%s' "$SECRET_KEY" > infra/garage/credentials/secret_key
echo "[bootstrap] wrote credentials to infra/garage/credentials/"

echo "[bootstrap] starting application services..."
docker compose up -d api cv-worker geo-worker web

echo ""
echo "[bootstrap] done."
echo "  UI:  http://localhost:3000   (admin / admin123)"
echo "  API: http://localhost:8000/docs"
