# Kill Tony Data Project — Justfile
# Run `just` to list all commands.
#
# Required env vars (set in shell or .env):
#   RAILWAY_BACKEND_URL  — public URL of the Railway backend (no trailing slash)
#                          e.g. https://kill-tony-backend.railway.app
#   ADMIN_SECRET         — matches the ADMIN_SECRET set on the Railway backend service

backend_service := "kill-tony-backend"
frontend_service := "kill-tony-frontend"

# ── Default: list commands ────────────────────────────────────────────────────

default:
    @just --list

# ── Local dev ─────────────────────────────────────────────────────────────────

# Start backend dev server
dev-backend:
    cd backend && .venv/bin/uvicorn main:app --reload --port 8000

# Start frontend dev server
dev-frontend:
    cd frontend && npm run dev

# Start both (requires: brew install tmux)
dev:
    tmux new-session -d -s kt 'just dev-backend' \; \
      split-window -h 'just dev-frontend' \; \
      attach

# ── Pipeline ──────────────────────────────────────────────────────────────────

# Process a single episode through the full pipeline
#   just process 742
process EP:
    cd backend && .venv/bin/python batch_processor.py --episode {{EP}}

# Re-run Pass 2 only (uses cached transcript, skips audio download)
#   just reprocess 742
reprocess EP:
    cd backend && .venv/bin/python reprocess_pass2.py --episode {{EP}}

# Process a batch with a limit (default 5 at a time)
#   just batch 10
batch LIMIT="5":
    cd backend && .venv/bin/python batch_processor.py --limit {{LIMIT}}

# ── Deploy ────────────────────────────────────────────────────────────────────

# Deploy both services to Railway (uploads from local — no GitHub required)
deploy:
    cd backend && railway up --detach
    cd frontend && railway up --detach

# Deploy backend only
deploy-backend:
    cd backend && railway up --detach

# Deploy frontend only
deploy-frontend:
    cd frontend && railway up --detach

# Upload local SQLite DB to Railway via the admin endpoint.
# Requires: ADMIN_SECRET env var (copy from `just show-secrets`).
upload-db:
    #!/usr/bin/env bash
    set -euo pipefail
    RAILWAY_BACKEND_URL="https://kill-tony-backend-production.up.railway.app"
    : "${ADMIN_SECRET:?Set ADMIN_SECRET in your shell — run: just show-secrets}"
    echo "Uploading data/kill_tony.db → $RAILWAY_BACKEND_URL/admin/upload-db ..."
    curl -fS \
      -H "x-admin-secret: $ADMIN_SECRET" \
      -F "file=@data/kill_tony.db" \
      "$RAILWAY_BACKEND_URL/admin/upload-db"
    echo ""
    echo "Done."

# Show Railway env vars for both services
show-secrets:
    @echo "=== Backend ==="
    cd backend && railway variable
    @echo "=== Frontend ==="
    cd frontend && railway variable

# ── Railway logs ──────────────────────────────────────────────────────────────

# Tail backend logs
logs-backend:
    railway logs --service {{backend_service}}

# Tail frontend logs
logs-frontend:
    railway logs --service {{frontend_service}}

# ── Railway shell / status ────────────────────────────────────────────────────

# Open a shell on the running backend container (volume is mounted)
shell:
    railway shell --service {{backend_service}}

# Show Railway deployment status
status:
    railway status

# ── Deps ──────────────────────────────────────────────────────────────────────

# Install/update frontend npm packages
install-frontend:
    cd frontend && npm install

# Install pipeline Python deps into the local .venv
install-pipeline:
    cd backend && .venv/bin/pip install -r requirements-pipeline.txt

# Create and activate Python venv, install backend deps
venv:
    python3 -m venv backend/.venv
    backend/.venv/bin/pip install -r backend/requirements.txt

# Activate Python venv
activate:
    source backend/.venv/bin/activate

# ── Misc ──────────────────────────────────────────────────────────────────────

# Check DB row counts
db-stats:
    sqlite3 data/kill_tony.db "SELECT 'episodes', COUNT(*) FROM episodes UNION ALL SELECT 'sets', COUNT(*) FROM sets;"
