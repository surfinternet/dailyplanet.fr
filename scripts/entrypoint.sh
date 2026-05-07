#!/bin/bash
set -euo pipefail

echo "[entrypoint] Démarrage Daily Planet FR pipeline..."
echo "[entrypoint] Date: $(date)"

# Git configuration (from .env)
git config --global user.name  "${GIT_USER_NAME:-Daily Planet Bot}"
git config --global user.email "${GIT_USER_EMAIL:-bot@dailyplanet.fr}"
git config --global --add safe.directory /app

# Pre-accept GitHub host key (avoids interactive prompt in cron)
mkdir -p /root/.ssh
ssh-keyscan -H github.com >> /root/.ssh/known_hosts 2>/dev/null
echo "[entrypoint] GitHub host key configuré"

# Init SQLite DB on first run
if [ ! -f /app/pipeline/db/dailyplanet.db ]; then
  echo "[entrypoint] Initialisation de la base de données..."
  python /app/pipeline/setup.py
fi

mkdir -p /app/logs
touch /app/logs/pipeline.log

echo "[entrypoint] Démarrage cron..."
cron

echo "[entrypoint] Container prêt. Logs : /app/logs/pipeline.log"
exec tail -f /app/logs/pipeline.log
