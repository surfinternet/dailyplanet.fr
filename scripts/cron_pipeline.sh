#!/bin/bash
set -euo pipefail

LOG=/app/logs/pipeline.log
RUN_ID="$(date '+%Y%m%d-%H%M%S')"

# Redirect all output (stdout + stderr) to log AND terminal in one place — no double write
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$RUN_ID] $1"; }

log "════════════════════════════════════════════"
log "RUN START"
log "════════════════════════════════════════════"

cd /app

# Step 1: Sync latest layouts/templates from main (Mac dev work)
log "Git: récupération des derniers templates depuis main..."
git checkout content 2>&1 || true
git fetch origin main 2>&1
git merge origin/main --no-edit 2>&1
log "Git: HEAD = $(git rev-parse --short HEAD)"

# Step 2: Run the Python pipeline
log "Python: lancement du pipeline..."
python pipeline/main_pipeline.py
EXIT_CODE=$?

if [ "$EXIT_CODE" -ne 0 ]; then
  log "ERREUR: pipeline terminé avec code $EXIT_CODE"
  log "════════════════════════════════════════════"
  log "RUN FAILED (code $EXIT_CODE)"
  log "════════════════════════════════════════════"
  exit "$EXIT_CODE"
fi

log "Python: pipeline terminé avec succès"

# Step 3: Stage ONLY generated content (never layouts, CSS, scripts, prompts)
log "Git: staging du contenu généré..."
git add content/posts/ assets/images/ static/images/ 2>&1

if git diff --cached --quiet; then
  log "Git: rien à committer (pipeline n'a rien produit de nouveau)"
  log "════════════════════════════════════════════"
  log "RUN END — aucun article publié"
  log "════════════════════════════════════════════"
  exit 0
fi

COMMIT_MSG="[auto] Article — $(date '+%Y-%m-%d %H:%M') Paris"
git commit -m "$COMMIT_MSG" 2>&1
log "Git: commit créé — $COMMIT_MSG"

# Step 4: Push to content branch (triggers GitHub Actions → merge into main → Cloudflare deploy)
log "Git: push vers origin/content..."
git push origin content 2>&1

log "════════════════════════════════════════════"
log "RUN END — article publié, GitHub Actions merge dans main"
log "Cloudflare Pages déploiera automatiquement"
log "════════════════════════════════════════════"
