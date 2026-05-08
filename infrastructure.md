# Infrastructure Daily Planet FR

## VPS ACTUEL
```
IP         : 46.202.130.138
OS         : Ubuntu 24.04
User dédié : dailyplanet
Docker     : v29.4.1
Repo cloné : /home/dailyplanet/dailyplanet.fr
Branche    : content
```

---

## SETUP INITIAL D'UN NOUVEAU VPS
> Utilise cette section quand tu changes de serveur.
> Donne cette section à Claude Code avec la nouvelle IP — il peut tout faire sauf l'étape GitHub (navigateur).
<!-- instruction à demander à Claude Code : Je change de VPS, nouvelle IP : X.X.X.X — suis la procédure dans infrastructure.md -->
### Étape 1 — Préparer le VPS (depuis ton Mac, donner à Claude Code)

```bash
# Remplace NEW_IP par la nouvelle IP
NEW_IP=X.X.X.X

# Efface l'ancienne empreinte si IP déjà connue
ssh-keygen -R $NEW_IP

# Connexion root initiale
ssh root@$NEW_IP

# Sur le VPS en root :
adduser dailyplanet
usermod -aG sudo dailyplanet
usermod -aG docker dailyplanet

# Vérification
groups dailyplanet
# attendu : dailyplanet sudo users docker
```

### Étape 2 — Copier ta clé SSH Mac → nouveau VPS (depuis ton Mac)

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub dailyplanet@NEW_IP

# Test connexion sans mot de passe
ssh dailyplanet@NEW_IP
```

### Étape 3 — Générer la clé deploy GitHub (sur le nouveau VPS)

```bash
ssh-keygen -t ed25519 -C "dailyplanet-vps" -f ~/.ssh/github_deploy -N ""

# Configurer SSH pour utiliser cette clé pour GitHub
cat >> ~/.ssh/config << 'EOF'

Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/github_deploy
  IdentitiesOnly yes
EOF

chmod 600 ~/.ssh/config

# Afficher la clé publique à copier
cat ~/.ssh/github_deploy.pub
```

### Étape 4 — Ajouter la clé sur GitHub (ACTION MANUELLE — navigateur requis)

**URL directe :** https://github.com/surfinternet/dailyplanet.fr/settings/keys

1. Clique **"Add deploy key"**
2. Title : `VPS Hostinger — dailyplanet`
3. Key : colle le contenu de `github_deploy.pub` (étape 3)
4. ✓ **Allow write access**
5. Clique **"Add key"**

> **Important :** Supprimer l'ancienne clé du VPS précédent dans la même page (elle ne sera plus valide).

**Test depuis le nouveau VPS :**
```bash
ssh -T git@github.com
# attendu : Hi surfinternet/dailyplanet.fr! You've successfully authenticated...
```

### Étape 5 — Cloner le repo et démarrer le container (donner à Claude Code)

```bash
# Sur le nouveau VPS
git clone git@github.com:surfinternet/dailyplanet.fr.git /home/dailyplanet/dailyplanet.fr
cd /home/dailyplanet/dailyplanet.fr
git checkout content

# Créer le .env (copier depuis l'ancien VPS ou remplir depuis .env.example)
cp .env.example .env
nano .env
# Valeurs obligatoires à renseigner :
#   MODE=production
#   OPENROUTER_API_KEY=...
#   KIE_AI_API_KEY=...
#   HUGO_SITE_PATH=/app
#   GIT_USER_NAME=Daily Planet Bot
#   GIT_USER_EMAIL=bot@dailyplanet.fr

# Créer le dossier logs
mkdir -p logs

# Build et démarrage
docker compose build
docker compose up -d

# Vérification
docker compose ps
docker compose logs -f
```

### Étape 6 — Tester le pipeline manuellement

```bash
docker exec -it dailyplanet-pipeline python /app/pipeline/main_pipeline.py
```

Si ça tourne → pipeline OK. Attendre le prochain cron (7h, 10h40, 14h15, 17h Paris) pour confirmer le git push automatique.

### Étape 7 — Couper l'ancien VPS

Une fois le nouveau VPS validé (pipeline tourne, articles pushés, GitHub Actions merge bien) :
- Supprimer le container sur l'ancien VPS : `docker compose down`
- Supprimer l'ancienne deploy key GitHub (Settings → Deploy keys)
- Mettre à jour la section "VPS ACTUEL" ci-dessus avec la nouvelle IP

---

## OPÉRATIONS COURANTES

**Voir les logs en direct (depuis ton Mac) :**
```bash
ssh dailyplanet@46.202.130.138 "tail -f /home/dailyplanet/dailyplanet.fr/logs/pipeline.log"
```

**Lancer le pipeline manuellement hors planning :**
```bash
ssh dailyplanet@46.202.130.138
docker exec -it dailyplanet-pipeline /app/scripts/cron_pipeline.sh
```

**Relancer le container après une mise à jour du code :**
```bash
ssh dailyplanet@46.202.130.138
cd /home/dailyplanet/dailyplanet.fr
git pull origin content
docker compose down && docker compose build && docker compose up -d
```

**Pousser des modifs de design depuis le Mac :**
```bash
git checkout dev
# ... modifier layouts/, CSS, prompts/ ...
git add <fichiers>
git commit -m "Update: ..."
git push origin dev

# Déployer en production :
git checkout main && git merge dev && git push origin main
# Le VPS récupère automatiquement ces modifs au prochain cron via git merge origin/main
git checkout dev
```

---

## ARCHITECTURE RÉSUMÉE
```
Mac (dev branch)
    └── git push → GitHub/dev
                       │
                    merge manuel → GitHub/main → Cloudflare Pages → dailyplanet.fr

VPS (content branch)
    └── cron 4x/jour
        └── git merge origin/main  (récupère les derniers layouts)
        └── python main_pipeline.py
        └── git push → GitHub/content
                           │
                        GitHub Actions → merge dans main → Cloudflare Pages build
```
