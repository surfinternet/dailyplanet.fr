#!/bin/bash
set -euo pipefail

echo "[entrypoint] Démarrage Daily Planet FR pipeline..."
echo "[entrypoint] Date: $(date)"

# Git configuration (from .env)
git config --global user.name  "${GIT_USER_NAME:-Daily Planet Bot}"
git config --global user.email "${GIT_USER_EMAIL:-bot@dailyplanet.fr}"
git config --global --add safe.directory /app

# Setup SSH — copy host keys to /root/.ssh with correct root ownership
# (SSH refuses config/keys not owned by the current user)
mkdir -p /root/.ssh
chmod 700 /root/.ssh

if [ -f /host-ssh/github_deploy ]; then
  cp /host-ssh/github_deploy /root/.ssh/github_deploy
  chmod 600 /root/.ssh/github_deploy
fi

if [ -f /host-ssh/known_hosts ]; then
  cp /host-ssh/known_hosts /root/.ssh/known_hosts
  chmod 644 /root/.ssh/known_hosts
fi

cat > /root/.ssh/config << 'SSHEOF'
Host github.com
  HostName github.com
  User git
  IdentityFile /root/.ssh/github_deploy
  IdentitiesOnly yes
SSHEOF
chmod 600 /root/.ssh/config

echo "[entrypoint] SSH configuré pour GitHub"

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
