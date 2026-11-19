#!/usr/bin/env bash
# One-shot setup: creates .env, starts n8n in Docker, imports the workflow.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
  key=$(openssl rand -hex 32)
  sed -i "s/^N8N_ENCRYPTION_KEY=.*/N8N_ENCRYPTION_KEY=${key}/" .env
  echo "Created .env - add ANTHROPIC_API_KEY and FAL_KEY to it, then re-run: docker compose up -d"
fi

python3 scripts/build_workflow.py
docker compose up -d

echo -n "Waiting for n8n"
for _ in $(seq 1 60); do
  if curl -fs http://localhost:5678/healthz >/dev/null 2>&1; then echo " - up"; break; fi
  echo -n "."; sleep 2
done

docker compose exec -T n8n n8n import:workflow --input=/workflows/tech-to-shorts.json
echo "Done. Open http://localhost:5678 (first visit asks you to create the owner account)."
