#!/usr/bin/env bash
# Деплой на VPS: pull → build → pm2 reload
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB="$REPO_ROOT/web"

echo "==> repo: $REPO_ROOT"

cd "$REPO_ROOT"
git pull --ff-only

cd "$WEB"
npm ci
npm run build

if pm2 describe music-exile >/dev/null 2>&1; then
  pm2 reload ecosystem.config.cjs --update-env
  echo "==> pm2: reloaded music-exile"
else
  pm2 start ecosystem.config.cjs
  pm2 save
  echo "==> pm2: started music-exile (run 'pm2 startup' once if not done)"
fi

pm2 status music-exile
echo "==> OK: $(date -Iseconds)"
