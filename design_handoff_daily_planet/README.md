# Handoff : Daily Planet FR — Templates éditoriaux

## Overview

Daily Planet FR est un média tech francophone couvrant l'intelligence artificielle. Ce handoff contient les **3 templates HTML haute fidélité** du site : Homepage, page Article et pages statiques (À propos, Mentions légales, Contact, Charte éditoriale).

L'objectif est d'intégrer ces designs dans un projet **Hugo** (générateur de sites statiques), en utilisant les composants et les conventions du projet existant.

---

## About the Design Files

Les fichiers HTML de ce bundle sont des **références de design haute fidélité** créées sous forme de prototypes — ils montrent le rendu visuel et le comportement attendu, mais **ne sont pas du code de production à copier directement**.

La tâche du développeur est de **recréer ces designs dans Hugo** (layouts Golang, partials, shortcodes, SCSS ou CSS custom properties) en suivant les conventions du projet existant. Les valeurs exactes de couleurs, typographie et espacements sont documentées ci-dessous et dans `shared.css`.

---

## Fidelity

**Haute fidélité (hifi)** — Les maquettes sont pixel-perfect avec couleurs finales, typographie, espacements et interactions. Le développeur doit recréer l'UI fidèlement en utilisant les patterns du projet.

---

## Design Tokens

### Couleurs
```css
--bg:      #FAFAF7;   /* Fond principal — blanc chaud */
--fg:      #0A0A0A;   /* Texte principal — presque noir */
--accent:  #BE1C28;   /* Rouge masthead — accent unique */
--muted:   #5A5558;   /* Texte secondaire / méta */
--border:  #E5E0D8;   /* Séparateurs */
```

### Typographie
| Rôle | Famille | Poids | Usage |
|---|---|---|---|
| Titres éditoriaux | Playfair Display | 800–900 | H1, H2, titres de cartes |
| Corps | DM Sans | 300–600 | Paragraphes, UI générale |
| Labels / Tags / Nav | Barlow Condensed | 600–800 | Tags, navigation, masthead |

**Import Google Fonts :**
```
https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,800;0,900;1,700;1,800;1,900&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&family=Barlow+Condensed:wght@500;600;700;800&display=swap
```

### Espacement & Layout
```css
--max:  1200px;                    /* Largeur max du contenu */
--col:  clamp(16px, 4vw, 24px);   /* Padding latéral responsive */
```

### Bordures & Ombres
- Séparateurs de section : `border-top: 3px solid var(--fg)` (heavy) ou `1.5px solid var(--border)` (light)
- Pas d'ombres portées — design flat presse
- Pas de border-radius sur les éléments principaux

---

## Screens / Views

### 1. Homepage (`Homepage.html`)

**Purpose :** Page d'accueil listant les derniers articles avec hero, grille et sidebar.

#### Layout global
- Barre de date plein-écran (fond `#0A0A0A`, texte `#FAFAF7`)
- Masthead sticky 64px de hauteur, `border-bottom: 3px solid #0A0A0A`
- Contenu : `max-width: 1200px`, centré, `padding: 0 var(--col)`
- Footer : fond `#0A0A0A`, texte `#FAFAF7`

#### Sections
1. **Date bar** — `background: #0A0A0A`, `font-family: Barlow Condensed`, `font-size: 11px`, `letter-spacing: 0.15em`, `text-transform: uppercase`
2. **Masthead** — sticky, logo centré-gauche (`Barlow Condensed 800`, `text-transform: uppercase`), nav droite (`Barlow Condensed 600`, `font-size: 15px`, `letter-spacing: 0.08em`), bouton recherche SVG
3. **Hero** — image `aspect-ratio: 21/9` sur desktop, tag filled rouge, H1 `Playfair Display 900` `font-size: clamp(32px, 6vw, 72px)` `letter-spacing: -0.02em`, chapô `DM Sans 400` `font-size: clamp(15px, 1.8vw, 18px)`, méta `Barlow Condensed` `font-size: 13px`
4. **Main content** — grid `1fr 300px` sur desktop (>900px), `1fr` sur mobile
5. **Grille articles** — `1fr 1fr` sur >580px, cartes avec `border-top: 1.5px solid #E5E0D8`, `padding: 24px 0`
6. **Carte large** (première) — `grid-column: 1 / -1`, image `4:3` + texte côte à côte sur desktop
7. **Sidebar "Les plus lus"** — numéros `Playfair Display 800` `font-size: 28px` `color: #E5E0D8`, titres `Playfair Display 700` `font-size: 16px`
8. **Bande newsletter** — `background: #0A0A0A`, titre `Playfair Display 900` `font-size: clamp(24px, 4vw, 40px)`, formulaire email inline, bouton `background: #BE1C28`

#### Section header pattern (réutilisable)
```css
display: flex;
align-items: baseline;
justify-content: space-between;
border-top: 3px solid #0A0A0A;
padding-top: 12px;
margin-bottom: 24px;
```
- Label : `Barlow Condensed 800`, `13px`, `letter-spacing: 0.15em`, `text-transform: uppercase`
- Lien "Voir tout" : `Barlow Condensed 600`, `12px`, `color: #BE1C28`

#### Tag pattern
```css
/* Outlined */
font-family: Barlow Condensed 700;
font-size: 11px;
letter-spacing: 0.12em;
text-transform: uppercase;
color: #BE1C28;
border: 1.5px solid #BE1C28;
padding: 3px 8px;

/* Filled */
background: #BE1C28;
color: #fff;
```

---

### 2. Article (`Article.html`)

**Purpose :** Page de lecture d'un article individuel.

#### Layout global
- Wrapper `max-width: 1200px`, `padding: 0 var(--col)`
- Header article : pleine largeur du wrapper (titre, chapô, méta, partage)
- Image hero : pleine largeur du wrapper (`max-width: 1200px`, même padding)
- Corps : grid `1fr 260px` sur desktop (>900px), `1fr` sur mobile
- Corps texte : `max-width: 68ch`

#### Composants spécifiques

**Barre de progression de lecture**
```css
position: fixed;
top: 0; left: 0;
height: 3px;
background: #BE1C28;
z-index: 200;
width: 0%; /* mis à jour via JS scroll */
transition: width 0.1s linear;
```

**Breadcrumb**
- `Barlow Condensed 600`, `12px`, `letter-spacing: 0.1em`, `text-transform: uppercase`
- Lien courant : `color: #BE1C28`

**Titre article**
- `Playfair Display 900`, `font-size: clamp(30px, 5.5vw, 64px)`, `line-height: 1.06`, `letter-spacing: -0.025em`
- Pleine largeur du wrapper (pas de max-width sur le titre)

**Chapô**
- `Playfair Display` italic, `font-size: clamp(17px, 2vw, 22px)`, `color: #5A5558`
- `border-left: 3px solid #BE1C28`, `padding-left: 16px`
- Pleine largeur du wrapper

**Méta article**
- `Barlow Condensed`, `13px`, `letter-spacing: 0.08em`, `text-transform: uppercase`, `color: #5A5558`

**Boutons de partage**
```css
font-family: Barlow Condensed 700;
font-size: 12px;
letter-spacing: 0.1em;
text-transform: uppercase;
padding: 7px 14px;
border: 1.5px solid #E5E0D8;
background: none;
/* Version primary */
background: #0A0A0A;
color: #FAFAF7;
```

**Image hero**
- Wrapper : `max-width: 1200px`, `margin: 0 auto`, `padding: 0 var(--col)`
- Image : `aspect-ratio: 2/1` mobile, `21/9` desktop (>768px)
- Légende : `Barlow Condensed`, `12px`, `letter-spacing: 0.06em`, `color: #5A5558`

**Corps de l'article**
- `font-size: clamp(16px, 1.8vw, 18px)`, `line-height: 1.75`
- Drop cap premier paragraphe : `Playfair Display 900`, `font-size: 4.2em`, `float: left`, `color: #BE1C28`
- H2 intertitres : `Playfair Display 800`, `font-size: clamp(20px, 2.5vw, 26px)`, `letter-spacing: -0.015em`
- Blockquote : `border-left: 4px solid #BE1C28`, `padding: 12px 0 12px 24px`
- Citation blockquote : `Playfair Display italic`, `font-size: clamp(18px, 2.2vw, 22px)`

**Sidebar sticky** (desktop uniquement)
```css
position: sticky;
top: 80px;
```
- Label section : `Barlow Condensed 800`, `11px`, `letter-spacing: 0.18em`, `border-top: 2px solid #0A0A0A`

**Author box**
- `border-top: 3px solid #0A0A0A`, `border-bottom: 1.5px solid #E5E0D8`, `padding: 28px 0`
- Avatar : `64px × 64px`, `border-radius: 50%`, `border: 2px solid #0A0A0A`, initiales en `Barlow Condensed 800`
- Nom : `Playfair Display 800`, `18px`
- Rôle : `Barlow Condensed 700`, `12px`, `letter-spacing: 0.1em`, `color: #BE1C28`

**Articles connexes**
- Grid `repeat(3, 1fr)` sur >600px, `1fr` sur mobile
- `border-top: 1.5px solid #E5E0D8`, `padding-top: 16px`

---

### 3. Pages statiques (`Static Page.html`)

**Purpose :** Pages institutionnelles (À propos, Mentions légales, Contact, Charte éditoriale) avec navigation par onglets.

#### Layout
- Wrapper `max-width: 1200px`, `padding: 0 var(--col)` — pleine largeur
- Contenu textuel : pas de contrainte de largeur (s'adapte au wrapper)

#### Navigation par onglets (switcher JS)
- `font-family: Barlow Condensed 700`, `13px`, `letter-spacing: 0.1em`, `text-transform: uppercase`
- Onglet actif : `color: #0A0A0A`, `border-bottom: 3px solid #BE1C28`
- `border-bottom: 2px solid #E5E0D8` sur le conteneur

#### Page header
- Eyebrow : `Barlow Condensed 700`, `12px`, `letter-spacing: 0.15em`, `color: #BE1C28`
- Titre : `Playfair Display 900`, `font-size: clamp(36px, 6vw, 60px)`, `letter-spacing: -0.025em`
- Sous-titre : `DM Sans 400`, `font-size: clamp(16px, 1.8vw, 19px)`, `color: #5A5558`
- `border-bottom: 2px solid #E5E0D8`

#### Contenu riche
- Paragraphes : `DM Sans 400`, `font-size: clamp(16px, 1.8vw, 18px)`, `line-height: 1.8`
- H2 : `Playfair Display 800`, `font-size: clamp(22px, 2.8vw, 30px)`, `border-top: 2px solid #0A0A0A`, `padding-top: 20px`
- H3 : `Barlow Condensed 700`, `16px`, `letter-spacing: 0.1em`, `text-transform: uppercase`

#### Values grid (4 valeurs)
- Grid `1fr 1fr` sur >580px
- Numéro : `Barlow Condensed 800`, `32px`, `color: #BE1C28`
- Label : `Playfair Display 800`, `18px`
- `border-top: 1.5px solid #E5E0D8`

#### Team row
- Flex, gap `20px`, `padding: 24px 0`, `border-top: 1.5px solid #E5E0D8`
- Avatar : `56px × 56px`, `border-radius: 50%`, `border: 2px solid #0A0A0A`
- Nom : `Playfair Display 800`, `17px`
- Rôle : `Barlow Condensed 700`, `12px`, `letter-spacing: 0.1em`, `color: #BE1C28`

#### Contact box
- `background: #0A0A0A`, `color: #FAFAF7`, `padding: 32px`
- Titre : `Playfair Display 800`, `22px`
- Bouton lien : `Barlow Condensed 700`, `13px`, `border: 1.5px solid #FAFAF7`, hover `background: #BE1C28`

---

## Interactions & Behavior

### Navigation
- Masthead sticky (position: sticky, top: 0, z-index: 100)
- Liens nav : hover `color: #BE1C28`, transition 0.15s

### Article
- **Barre de progression** : JS scroll event → `width = (scrollY / (docHeight - innerHeight)) * 100 + '%'`
- **Partage** : boutons Copier le lien, Twitter, LinkedIn (implémentation à adapter)

### Pages statiques
- **Switcher d'onglets** : JS vanilla — afficher/masquer `.page-section`, gérer `.active` sur les items nav

### Newsletter
- Formulaire email : validation HTML5 `type="email"` minimum, soumission à connecter au service newsletter (Mailchimp, Brevo, etc.)

### Responsive breakpoints
| Breakpoint | Comportement |
|---|---|
| `< 580px` | Grille 1 colonne, navigation masquée |
| `580px` | Grille 2 colonnes |
| `768px` | Image hero ratio 21/9 |
| `900px` | Layout 2 colonnes (contenu + sidebar) |

---

## Footer (partagé entre tous les templates)

```
background: #0A0A0A
color: #FAFAF7
padding: 40px [col] 0
```
- Grid `1fr 1fr 1fr` desktop, `1fr` mobile
- Logo : `Barlow Condensed 800`, `22px`, `text-transform: uppercase`
- Liens : `Barlow Condensed 600`, `13px`, `letter-spacing: 0.1em`, `color: #CCC`, hover `#fff`
- Bottom bar : `border-top: 1px solid #333`, `font-size: 11px`, `color: #666`
- Tagline italique : `color: #888`

---

## Assets

- **Placeholders images** : à remplacer par de vraies illustrations de style comics/éditorial. Format conseillé : ratio `16:9` pour les cartes, `21:9` pour le hero homepage, `2:1` ou `21:9` pour le hero article, `4:3` pour la carte large.
- **Icône recherche** : SVG inline `feather-icons` (circle 11 11 8 + path 21 21 → 16.65 16.65)
- **Icône partage** : SVG inline

---

## Files

| Fichier | Rôle |
|---|---|
| `shared.css` | Tokens CSS (couleurs, typo, max-width), masthead, footer, tags, placeholders — base commune à tous les templates |
| `Homepage.html` | Template page d'accueil |
| `Article.html` | Template page article |
| `Static Page.html` | Template pages statiques (4 pages en 1 via JS) |

---

## Notes pour l'intégration Hugo

- `shared.css` → à transformer en `assets/css/base.scss` ou équivalent, avec les variables CSS dans `:root`
- `Homepage.html` → `layouts/index.html`
- `Article.html` → `layouts/posts/single.html`
- `Static Page.html` → `layouts/_default/single.html` ou pages spécifiques via `layouts/[section]/single.html`
- Les sections "Les plus lus" et "Trending" → à alimenter via une taxonomie Hugo ou un partial avec `.Site.RegularPages`
- La navigation par onglets des pages statiques → peut être remplacée par des pages Hugo séparées avec un partial de navigation commun
- Les placeholders d'images → à remplacer par des shortcodes Hugo ou des paramètres front matter `image:`

---

*Handoff généré le 1er mai 2026 — Daily Planet FR*
