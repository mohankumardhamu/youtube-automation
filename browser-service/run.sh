#!/usr/bin/env bash
# Starts the VEED browser service on port 8765 (reachable from the n8n container).
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/uvicorn service:app --host 0.0.0.0 --port 8765
