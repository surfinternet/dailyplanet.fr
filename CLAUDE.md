# CLAUDE.md — Daily Planet FR

## Présentation
Site Hugo statique pour Daily Planet FR, média français IA/tech.  
Hugo 0.158.0 extended — pas de thème externe, tous les layouts sont à la racine.  
Déployé sur Cloudflare Pages depuis GitHub `surfinternet/dailyplanet.fr`.

## Commandes essentielles
```bash
# Développement local (inclut les drafts)
hugo server -D

# Build production
hugo

# Créer un nouvel article
hugo new content posts/mon-titre-en-kebab-case.md

# Répertoire de sortie (gitignore)
public/
```

## Structure des fichiers
```
layouts/             # Tous les layouts (pas de dossier themes/)
  _default/          # baseof.html, single.html (pages statiques), list.html
  posts/             # single.html (page article)
  partials/          # Tous les composants réutilisables
assets/css/main.css  # CSS unique, 24 sections commentées
assets/js/           # progress.js uniquement (vanilla JS, pas de framework)
content/posts/       # Articles (frontmatter requis voir ci-dessous)
content/about|legal|contact|charter/  # Pages statiques (leaf bundles)
data/trending.json   # "Les plus lus" sidebar (mise à jour manuelle)
static/images/       # Images source (non traitées)
```

## Frontmatter requis pour les articles (`content/posts/`)
```yaml
title: ""
date: YYYY-MM-DDTHH:MM:SS+02:00
draft: false
description: ""           # meta description (max 155 caractères)
author: ""
author_role: ""
author_bio: ""
author_initials: ""       # 2 lettres pour l'avatar
category: ""              # une seule catégorie principale
categories: []
tags: []
readtime: 5               # minutes
image: ""                 # chemin depuis assets/ ex: "images/mon-image.jpg"
image_caption: ""
featured: false           # true = article hero homepage
```

## Tokens design (ne jamais modifier)
```css
--bg: #FAFAF7    --fg: #0A0A0A    --accent: #BE1C28
--muted: #5A5558  --border: #E5E0D8
--serif: Playfair Display  --sans: DM Sans  --cond: Barlow Condensed
--max: 1200px    --col: clamp(16px, 4vw, 24px)
```

## Breakpoints
- < 580px : 1 colonne, nav masquée
- 580px   : 2 colonnes grille articles
- 768px   : hero image 21:9
- 900px   : layout 2 colonnes (contenu + sidebar)

## Déploiement Cloudflare Pages
- Repo : `surfinternet/dailyplanet.fr`
- Build command : `hugo`
- Output directory : `public`
- Variable d'environnement : `HUGO_VERSION=0.158.0`
- Pas de GitHub Actions — Cloudflare Pages gère le CI/CD nativement

## Règles importantes
- NE PAS ajouter de npm, node_modules, Sass ou framework JS
- NE PAS créer de dossier `themes/`
- NE PAS modifier les tokens CSS sans mettre à jour toutes les références
- Les images doivent être dans `assets/images/` pour bénéficier du traitement WebP Hugo
- `markup.goldmark.renderer.unsafe = true` dans hugo.toml permet le HTML brut dans les .md

## SEO auto-généré
- Canonical URLs, sitemap.xml, robots.txt : automatiques (Hugo)
- Open Graph + Twitter Card + Schema.org Article + BreadcrumbList : `layouts/partials/seo.html`

## Référence design
`design_handoff_daily_planet/` — conserver en référence, ne jamais supprimer ni déployer
