#!/bin/bash
set -euo pipefail

LOG=/app/logs/pipeline.log
TS=$(date '+%Y-%m-%d %H:%M:%S')
log() { echo "[$TS] $1" | tee -a "$LOG"; }

log "========================================"
log "Pipeline démarré"
log "========================================"

cd /app

# Step 1: Sync latest layouts/templates from main (Mac dev work)
log "Git: récupération des derniers templates depuis main..."
git checkout content 2>&1 | tee -a "$LOG" || true
git fetch origin main 2>&1 | tee -a "$LOG"
git merge origin/main --no-edit 2>&1 | tee -a "$LOG"
log "Git: HEAD = $(git rev-parse --short HEAD)"

# Step 2: Run the Python pipeline
log "Python: lancement du pipeline..."
python pipeline/main_pipeline.py 2>&1 | tee -a "$LOG"
EXIT_CODE=${PIPESTATUS[0]}

if [ "$EXIT_CODE" -ne 0 ]; then
  log "ERREUR: pipeline terminé avec code $EXIT_CODE"
  exit "$EXIT_CODE"
fi

log "Python: pipeline terminé avec succès"

# Step 3: Stage ONLY generated content (never layouts, CSS, scripts, prompts)
log "Git: staging du contenu généré..."
git add content/posts/ assets/images/ static/images/ 2>&1 | tee -a "$LOG"

if git diff --cached --quiet; then
  log "Git: rien à committer (pipeline n'a rien produit de nouveau)"
  log "========================================"
  exit 0
fi

COMMIT_MSG="[auto] Article — $(date '+%Y-%m-%d %H:%M') Paris"
git commit -m "$COMMIT_MSG" 2>&1 | tee -a "$LOG"
log "Git: commit créé — $COMMIT_MSG"

# Step 4: Push to content branch (triggers GitHub Actions → merge into main → Cloudflare deploy)
log "Git: push vers origin/content..."
git push origin content 2>&1 | tee -a "$LOG"

log "========================================"
log "Pipeline terminé — GitHub Actions va merger dans main"
log "Cloudflare Pages déploiera automatiquement"
log "========================================"
