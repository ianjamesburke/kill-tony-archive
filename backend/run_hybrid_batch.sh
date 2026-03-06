#!/bin/bash
# Run hybrid pipeline on multiple episodes sequentially
# Usage: ./run_hybrid_batch.sh 755 756 757 758 748

cd "$(dirname "$0")"

for ep in "$@"; do
    echo "=============================================="
    echo "Starting episode #$ep at $(date)"
    echo "=============================================="
    python3 hybrid_processor.py "$ep" 2>&1 | tee "../data/hybrid_ep${ep}_log.txt"
    echo "Episode #$ep finished at $(date)"
    echo ""
done

echo "All episodes complete!"
