#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

IMAGE="zvibe:latest"
HOST_PORT=9000
CONTAINER_PORT=8080
CONTAINER_NAME="zvibe"

# Stop existing container if running
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "[INFO] Stopping existing container: $CONTAINER_NAME"
  docker stop "$CONTAINER_NAME" >/dev/null 2>&1 && docker rm "$CONTAINER_NAME" >/dev/null 2>&1
fi

# Build
echo "[INFO] Building $IMAGE..."
docker build --platform linux/amd64 -t "$IMAGE" "$PROJECT_DIR"

# Run
echo "[INFO] Running $IMAGE on http://localhost:$HOST_PORT"
docker run -d \
  --name "$CONTAINER_NAME" \
  -p "${HOST_PORT}:${CONTAINER_PORT}" \
  "$IMAGE"

echo "[OK] Container started: $CONTAINER_NAME"
echo "     URL: http://localhost:$HOST_PORT"
echo "     Demo: linh / demo123456"
echo "     Logs: docker logs -f $CONTAINER_NAME"
