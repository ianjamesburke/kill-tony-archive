#!/usr/bin/env bash
# backup-db.sh
#
# Snapshots data/kill_tony.db into data/backups/ with a timestamp.
# Keeps the last N backups and deletes older ones.
#
# Usage:
#   ./scripts/backup-db.sh            # manual run
#   crontab -e  →  0 * * * * /path/to/scripts/backup-db.sh  (hourly)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="$ROOT/data/kill_tony.db"
BACKUP_DIR="$ROOT/data/backups"
KEEP=20  # number of snapshots to retain

mkdir -p "$BACKUP_DIR"

if [[ ! -f "$DB_PATH" ]]; then
  echo "ERROR: $DB_PATH not found"
  exit 1
fi

TIMESTAMP=$(date +"%Y-%m-%dT%H-%M-%S")
DEST="$BACKUP_DIR/kill_tony_$TIMESTAMP.db"

# sqlite3 backup is safe even while the DB is open
sqlite3 "$DB_PATH" ".backup '$DEST'"

SIZE=$(du -sh "$DEST" | cut -f1)
echo "Backed up → $DEST ($SIZE)"

# Prune old backups beyond KEEP
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/kill_tony_*.db 2>/dev/null | wc -l)
if (( BACKUP_COUNT > KEEP )); then
  TO_DELETE=$(( BACKUP_COUNT - KEEP ))
  ls -1t "$BACKUP_DIR"/kill_tony_*.db | tail -n "$TO_DELETE" | while read -r f; do
    rm "$f"
    echo "Pruned: $(basename "$f")"
  done
fi

echo "Backups retained: $(ls -1 "$BACKUP_DIR"/kill_tony_*.db 2>/dev/null | wc -l)/$KEEP"
