#!/bin/bash
# Kill Tony backfill — processes all pending episodes sequentially.
# Audio is automatically deleted after each episode (see batch_processor.py).
# Transcripts are kept in data/transcripts/ for reprocess_pass2.py.
#
# Usage:
#   nohup ./backend/run_batch.sh > data/batch.log 2>&1 &
#   tail -f data/batch.log   # monitor progress

set -e
cd "$(dirname "$0")/.."

echo "=== Kill Tony Batch Processor ==="
echo "Started: $(date)"
echo ""

python3 backend/batch_processor.py

echo ""
echo "=== Batch complete: $(date) ==="
