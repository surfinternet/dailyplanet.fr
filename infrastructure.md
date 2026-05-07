INFOS VPS
─────────
IP        : à compléter
OS        : Ubuntu 24.04
User dédié : dailyplanet

PRÉREQUIS SUR TON MAC
──────────────────────
Clé SSH : ~/.ssh/id_ed25519 (déjà créée)

# ÉTAPE 1 — Efface l'ancienne clé SSH si IP déjà connue
ssh-keygen -R IP_DU_VPS

# ÉTAPE 2 — Connecte-toi en root
ssh root@IP_DU_VPS

# ÉTAPE 3 — Crée l'utilisateur dédié (sur le VPS)
adduser dailyplanet
usermod -aG sudo dailyplanet
usermod -aG docker dailyplanet

# Vérifie
groups dailyplanet
# attendu : dailyplanet sudo users docker

# ÉTAPE 4 — Depuis ton Mac (nouveau terminal)
ssh-copy-id -i ~/.ssh/id_ed25519.pub dailyplanet@IP_DU_VPS

# ÉTAPE 5 — Teste la connexion sans mot de passe
ssh dailyplanet@IP_DU_VPS