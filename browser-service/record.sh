#!/usr/bin/env bash
# Opens a Playwright-controlled Firefox with the code recorder.
# First run: log in to VEED (the session is saved to auth/veed.json for the service).
# Then create one video the way you normally do and download it; the steps are recorded.
set -euo pipefail
cd "$(dirname "$0")"
args=(--browser firefox --target python --save-storage auth/veed.json -o recordings/veed_recording.py)
[ -f auth/veed.json ] && args+=(--load-storage auth/veed.json)
.venv/bin/playwright codegen "${args[@]}" https://www.veed.io/workspaces
echo "Saved: recordings/veed_recording.py and auth/veed.json"
