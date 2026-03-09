#!/usr/bin/env bash
# sync-db-to-railway.sh
#
# Pushes the local SQLite database to the Railway backend via the /admin/upload-db endpoint.
# Run this after a successful episode processing batch.
#
# Required env vars (add to .env or export before running):
#   RAILWAY_BACKEND_URL  - e.g. https://your-backend.railway.app
#   ADMIN_SECRET         - must match the secret set on the Railway service
#
# Usage:
#   ./scripts/sync-db-to-railway.sh
#   RAILWAY_BACKEND_URL=https://... ADMIN_SECRET=... ./scripts/sync-db-to-railway.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load .env if present
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

RAILWAY_BACKEND_URL="${RAILWAY_BACKEND_URL:-}"
ADMIN_SECRET="${ADMIN_SECRET:-}"
DB_PATH="${DB_PATH_LOCAL:-$ROOT/data/kill_tony.db}"

# Validate
if [[ -z "$RAILWAY_BACKEND_URL" ]]; then
  echo "ERROR: RAILWAY_BACKEND_URL is not set."
  echo "  Export it or add it to .env: RAILWAY_BACKEND_URL=https://your-backend.railway.app"
  exit 1
fi

if [[ -z "$ADMIN_SECRET" ]]; then
  echo "ERROR: ADMIN_SECRET is not set."
  echo "  Export it or add it to .env: ADMIN_SECRET=your-secret"
  exit 1
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "ERROR: Database not found at $DB_PATH"
  exit 1
fi

DB_SIZE=$(du -sh "$DB_PATH" | cut -f1)
echo "Syncing $DB_PATH ($DB_SIZE) → $RAILWAY_BACKEND_URL/admin/upload-db"

HTTP_STATUS=$(curl -s -o /tmp/railway_upload_response.json -w "%{http_code}" \
  -X POST \
  -H "x-admin-secret: $ADMIN_SECRET" \
  -F "file=@$DB_PATH" \
  "$RAILWAY_BACKEND_URL/admin/upload-db")

RESPONSE=$(cat /tmp/railway_upload_response.json)

if [[ "$HTTP_STATUS" == "200" ]]; then
  echo "✓ Database synced successfully."
  echo "  Response: $RESPONSE"
else
  echo "ERROR: Upload failed (HTTP $HTTP_STATUS)"
  echo "  Response: $RESPONSE"
  exit 1
fi
