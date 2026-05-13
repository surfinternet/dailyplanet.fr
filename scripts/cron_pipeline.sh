#!/bin/bash
# Daily Planet FR — Cron wrapper du pipeline Python
# Gère : tracking dashboard, email d'alerte, git push

LOG=/app/logs/pipeline.log
export RUN_ID="$(date '+%Y%m%d-%H%M%S')"

# All output → log file AND terminal
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$RUN_ID] $1"; }

# ── Trap : fired on any exit (success or failure) ────────────────────────────
_on_exit() {
  local code=$?
  if [ "$code" -ne 0 ]; then
    log "RUN FAILED (code $code)"
    log "════════════════════════════════════════════"
    # Update dashboard JSON (non-blocking)
    python /app/pipeline/run_finish.py "$RUN_ID" failed 2>/dev/null || true
    # Send email alert (non-blocking)
    python /app/pipeline/send_alert.py "$RUN_ID" 2>/dev/null || true
  fi
}
trap '_on_exit' EXIT

set -euo pipefail

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

log "Python: pipeline terminé avec succès"

# Step 3: Stage ONLY generated content (never layouts, CSS, scripts, prompts)
log "Git: staging du contenu généré..."
git add content/posts/ assets/images/ static/images/ 2>&1

if git diff --cached --quiet; then
  log "Git: rien à committer (pipeline n'a rien produit de nouveau)"
  python /app/pipeline/run_finish.py "$RUN_ID" no_content \
    --git-note "Pipeline OK — aucun nouveau contenu à publier" 2>/dev/null || true
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

# Mark run as fully successful in dashboard
python /app/pipeline/run_finish.py "$RUN_ID" success \
  --git-note "Article publié → GitHub/content (Cloudflare déploiera automatiquement)" 2>/dev/null || true

log "════════════════════════════════════════════"
log "RUN END — article publié, GitHub Actions merge dans main"
log "Cloudflare Pages déploiera automatiquement"
log "════════════════════════════════════════════"
