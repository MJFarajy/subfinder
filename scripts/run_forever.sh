#!/bin/bash
# Run Bale Subdomain Finder Bot with automatic restart on failure
# Save this as scripts/run_forever.sh
# Usage: chmod +x scripts/run_forever.sh && ./scripts/run_forever.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

echo "[$(date)] Starting Subdomain Finder Bot (Bale)..."

while true; do
    echo "[$(date)] Starting bot..."
    venv/bin/python -m bot.bale_main
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "[$(date)] Bot stopped gracefully (exit code 0). Exiting."
        exit 0
    else
        echo "[$(date)] Bot crashed with exit code $EXIT_CODE. Restarting in 10 seconds..."
        sleep 10
    fi
done