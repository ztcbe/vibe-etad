#!/usr/bin/env bash
# ============================================================
# deploy_agentbase.sh — Deploy zvibe_be to GreenNode AgentBase
#
# Usage:
#   ./scripts/deploy_agentbase.sh              # Full deploy (build + push + create/update)
#   ./scripts/deploy_agentbase.sh --build-only # Build + push only (no runtime create/update)
#   ./scripts/deploy_agentbase.sh --update     # Update existing runtime with new image
#   ./scripts/deploy_agentbase.sh --dry-run    # Show plan without executing
#
# Prerequisites:
#   - Docker installed and running
#   - .greennode.json with IAM credentials (client_id + client_secret)
#   - Internet access to vcr.vngcloud.vn + agentbase.api.vngcloud.vn
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_DIR="$PROJECT_DIR/.claude/skills/agentbase/scripts"

# ── Configuration ──
RUNTIME_NAME="zvibe-be"
FLAVOR="runtime-s2-general-4x8"      # 4 CPU / 8 GB RAM
NETWORK_MODE="PUBLIC"
MIN_REPLICAS=1
MAX_REPLICAS=1
CPU_SCALE=50
MEM_SCALE=50
PLATFORM="linux/amd64"
ENV_FILE="$PROJECT_DIR/.agentbase/runtime.env"

# ── CR Config (auto-discovered) ──
CR_REGISTRY="vcr.vngcloud.vn"
CR_REPO=""    # Will be fetched from CR API
IMAGE_NAME="zvibe-be"

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Parse args ──
BUILD_ONLY=false
UPDATE_RUNTIME=false
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --build-only) BUILD_ONLY=true ;;
    --update)     UPDATE_RUNTIME=true ;;
    --dry-run)    DRY_RUN=true ;;
    --help|-h)
      echo "Usage: $0 [--build-only|--update|--dry-run]"
      echo ""
      echo "  (default)    Full deploy: build + push + create runtime"
      echo "  --build-only Build + push image only, skip runtime create/update"
      echo "  --update     Update existing runtime with new image"
      echo "  --dry-run    Show plan without executing"
      exit 0
      ;;
    *) err "Unknown argument: $arg. Use --help for usage." ;;
  esac
done

# ── Step 0: Check prerequisites ──
info "Checking prerequisites..."

if ! command -v docker &>/dev/null; then
  err "Docker not found. Install Docker first."
fi

if [ ! -f "$PROJECT_DIR/.greennode.json" ]; then
  err ".greennode.json not found. Set up IAM credentials first:\n  echo '<secret>' | bash $SKILLS_DIR/save_iam_credentials.sh --client-id '<id>' --secret-stdin"
fi

IAM_STATUS=$(bash "$SKILLS_DIR/check_credentials.sh" iam 2>&1)
if ! echo "$IAM_STATUS" | grep -q "OK"; then
  err "IAM credentials not configured. Run: bash $SKILLS_DIR/save_iam_credentials.sh --client-id '<id>' --secret-stdin"
fi

if [ ! -f "$PROJECT_DIR/Dockerfile" ]; then
  err "Dockerfile not found in $PROJECT_DIR"
fi

ENV_ARGS=()
if [ -f "$ENV_FILE" ]; then
  ENV_ARGS=(--env-file "$ENV_FILE")
  ok "Runtime env file found: $ENV_FILE"
else
  warn "Runtime env file not found: $ENV_FILE"
  warn "LLM calls may fail unless LLM_API_KEY is configured another way."
fi

ok "Prerequisites OK"

# ── Step 1: Get CR repo info ──
info "Fetching CR repository info..."
CR_INFO=$(bash "$SKILLS_DIR/cr.sh" repo get 2>&1)
CR_REPO=$(echo "$CR_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['name'])")
CR_REGISTRY=$(echo "$CR_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin)['registryUrl'])")
ok "CR repo: $CR_REGISTRY/$CR_REPO"

# ── Step 2: Generate image tag ──
IMAGE_TAG="v$(date +%Y%m%d%H%M%S)"
FULL_IMAGE="$CR_REGISTRY/$CR_REPO/$IMAGE_NAME:$IMAGE_TAG"
info "Image: $FULL_IMAGE"

# ── Dry run ──
if [ "$DRY_RUN" = true ]; then
  echo ""
  echo "===== DRY RUN ====="
  echo "Image:     $FULL_IMAGE"
  echo "Platform:  $PLATFORM"
  echo "Runtime:   $RUNTIME_NAME"
  echo "Flavor:    $FLAVOR"
  echo "Network:   $NETWORK_MODE"
  echo "Replicas:  $MIN_REPLICAS-$MAX_REPLICAS"
  echo "Env file:  ${ENV_FILE:-none}"
  echo "Commands:"
  echo "  docker build --platform $PLATFORM -t $FULL_IMAGE $PROJECT_DIR"
  echo "  bash $SKILLS_DIR/cr.sh credentials docker-login"
  echo "  docker push $FULL_IMAGE"
  if [ "$UPDATE_RUNTIME" = true ]; then
    echo "  bash $SKILLS_DIR/runtime.sh update <RUNTIME_ID> --image $FULL_IMAGE --flavor $FLAVOR --from-cr ..."
  else
    echo "  bash $SKILLS_DIR/runtime.sh create --name $RUNTIME_NAME --image $FULL_IMAGE --flavor $FLAVOR --from-cr ..."
  fi
  exit 0
fi

# ── Step 3: Build Docker image ──
info "Building Docker image ($PLATFORM)..."
docker build --platform "$PLATFORM" -t "$FULL_IMAGE" "$PROJECT_DIR"
ok "Build complete: $FULL_IMAGE"

# ── Step 4: Login to CR + Push ──
info "Logging in to AgentBase CR..."
bash "$SKILLS_DIR/cr.sh" credentials docker-login
ok "Docker login OK"

info "Pushing image to CR..."
docker push "$FULL_IMAGE"
ok "Push complete: $FULL_IMAGE"

if [ "$BUILD_ONLY" = true ]; then
  ok "Build-only mode. Skipping runtime create/update."
  echo ""
  echo "Image pushed: $FULL_IMAGE"
  echo "To create/update runtime, run:"
  echo "  $0 --update"
  exit 0
fi

# ── Step 5: Create or Update Runtime ──
RUNTIME_ID=""

info "Checking for existing runtime '$RUNTIME_NAME'..."
RUNTIMES=$(bash "$SKILLS_DIR/runtime.sh" list --page 1 --size 100 2>&1)
EXISTING_ID=$(echo "$RUNTIMES" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for r in data.get('listData', []):
    if r['name'] == '$RUNTIME_NAME':
        print(r['id'])
        break
" 2>/dev/null || echo "")

if [ -n "$EXISTING_ID" ]; then
  RUNTIME_ID="$EXISTING_ID"
  if [ "$UPDATE_RUNTIME" = true ] || [ -n "$EXISTING_ID" ]; then
    info "Updating existing runtime: $RUNTIME_ID"
    bash "$SKILLS_DIR/runtime.sh" update "$RUNTIME_ID" \
      --image "$FULL_IMAGE" \
      --flavor "$FLAVOR" \
      --from-cr \
      "${ENV_ARGS[@]}" \
      --min-replicas "$MIN_REPLICAS" \
      --max-replicas "$MAX_REPLICAS" \
      --cpu-scale "$CPU_SCALE" \
      --mem-scale "$MEM_SCALE" 2>&1
    ok "Runtime update initiated"
  fi
else
  info "Creating new runtime: $RUNTIME_NAME"
  CREATE_OUTPUT=$(bash "$SKILLS_DIR/runtime.sh" create \
    --name "$RUNTIME_NAME" \
    --image "$FULL_IMAGE" \
    --flavor "$FLAVOR" \
    --from-cr \
    --min-replicas "$MIN_REPLICAS" \
    --max-replicas "$MAX_REPLICAS" \
    --cpu-scale "$CPU_SCALE" \
    --mem-scale "$MEM_SCALE" \
    --description "zvibe AI dating app - FastAPI + PostgreSQL/pgvector" 2>&1)
  RUNTIME_ID=$(echo "$CREATE_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  ok "Runtime created: $RUNTIME_ID"
fi

# ── Step 6: Wait for ACTIVE ──
info "Waiting for runtime to become ACTIVE..."
for i in $(seq 1 40); do
  STATUS=$(bash "$SKILLS_DIR/runtime.sh" get "$RUNTIME_ID" 2>&1 | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "  [$i] Status: $STATUS"
  if [ "$STATUS" = "ACTIVE" ]; then
    ok "Runtime is ACTIVE!"
    break
  fi
  if [ "$STATUS" = "ERROR" ]; then
    err "Runtime entered ERROR state. Check logs via /agentbase-monitor."
  fi
  sleep 15
done

# ── Step 7: Get endpoint + test health ──
info "Fetching endpoint URL..."
ENDPOINTS=$(bash "$SKILLS_DIR/runtime.sh" endpoints list "$RUNTIME_ID" 2>&1)
ENDPOINT_URL=$(echo "$ENDPOINTS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for e in data.get('listData', []):
    if e['name'] == 'DEFAULT':
        print(e['url'])
        break
")
ok "Endpoint: $ENDPOINT_URL"

info "Testing health endpoint..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$ENDPOINT_URL/health" 2>&1 || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
  ok "Health check passed (HTTP 200)"
else
  warn "Health check returned HTTP $HTTP_CODE (container may still be starting)"
  info "Retry: curl -s $ENDPOINT_URL/health"
fi

# ── Summary ──
echo ""
echo "=========================================="
echo "  Deployment Complete!"
echo "=========================================="
echo ""
echo "  Runtime:    $RUNTIME_NAME"
echo "  Runtime ID: $RUNTIME_ID"
echo "  Image:      $FULL_IMAGE"
echo "  Flavor:     $FLAVOR (4 CPU / 8 GB RAM)"
echo "  Network:    $NETWORK_MODE"
echo "  Status:     ACTIVE"
echo "  Endpoint:   $ENDPOINT_URL"
echo "  Health:     $ENDPOINT_URL/health"
echo ""
echo "  Console:    https://aiplatform.console.vngcloud.vn/agent-runtime?tab=runtime"
echo ""
