"""
Étape 5 — Construction du fichier Markdown Hugo avec frontmatter complet

- Génère description SEO, catégories, tags via LLM
- Sélectionne un auteur depuis pipeline/authors.json
- Calcule le readtime
- Insère <!--more--> après le premier paragraphe
- Sauvegarde dans content/posts/[slug].md
- Met à jour SQLite : statut → 'publié'
"""

import os
import re
import sys
import json
import random
import sqlite3
import subprocess
import requests
from datetime import datetime, timezone, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "dailyplanet.db")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CONTENT_POSTS = os.path.join(os.path.dirname(__file__), "..", "content", "posts")
AUTHORS_FILE = os.path.join(os.path.dirname(__file__), "authors.json")


def load_authors() -> list:
    with open(AUTHORS_FILE, encoding="utf-8") as f:
        return json.load(f)


AUTEURS = load_authors()

META_PROMPT = """\
À partir du titre et de l'extrait d'article ci-dessous, génère les métadonnées SEO.
Réponds UNIQUEMENT avec un JSON valide, sans markdown, sans commentaire.

Format exact :
{{
  "description": "Meta description SEO, 120-155 caractères, informative et incitative, se termine sur une idée complète, sans guillemets internes, sans troncature",
  "seo_title": "Titre SEO optimisé, max 60 caractères, keyword-first, sans le nom du site",
  "chapo": "Accroche éditoriale 2-3 phrases complètes, annonce ce qu'on trouvera dans l'article, richesse informative, pas de limite de longueur",
  "seo_slug": "4-5 mots-clés en kebab-case, sans mots vides (de à et le la un une son sa les des qui que), max 45 caractères",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "image_caption": "Légende courte pour l'illustration (max 80 caractères)"
}}

Titre : {titre}

Extrait :
{extrait}"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def calc_readtime(contenu: str) -> int:
    words = len(re.sub(r"[#\-*`>\[\]()]", "", contenu).split())
    return max(3, round(words / 200))


def strip_title_heading(contenu: str) -> str:
    """Remove first '# Title' line — it goes into frontmatter instead."""
    lines = contenu.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    # Strip leading blank lines
    while lines and not lines[0].strip():
        lines = lines[1:]
    return "\n".join(lines)


def insert_more_tag(contenu: str) -> str:
    """Insert <!--more--> after the first non-empty paragraph."""
    paragraphs = contenu.split("\n\n")
    if len(paragraphs) > 1:
        paragraphs.insert(1, "<!--more-->")
    return "\n\n".join(paragraphs)


def generate_metadata(titre: str, contenu: str) -> dict:
    extrait = contenu[:1200].strip()
    prompt = META_PROMPT.format(titre=titre, extrait=extrait)
    mode = os.getenv("MODE", "local")

    if mode == "local":
        cli_path = os.getenv("CLAUDE_CLI_PATH", "claude")
        result = subprocess.run(
            [cli_path, "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI erreur : {result.stderr[:300]}")
        content = result.stdout.strip()
    else:
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        model = os.getenv("CLAUDE_MODEL", "anthropic/claude-sonnet-4-6")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://dailyplanet.fr",
        }
        r = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 700,
            },
            timeout=60,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown code blocks
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        meta = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Métadonnées non parseable : {e}\nContenu : {content[:400]}")

    # Validation + fallbacks
    if not isinstance(meta.get("tags"), list) or not meta["tags"]:
        meta["tags"] = []
    desc = meta.get("description", "")
    if len(desc) > 160:
        meta["description"] = desc[:157] + "..."
    seo_title = meta.get("seo_title", "")
    if len(seo_title) > 65:
        meta["seo_title"] = seo_title[:62] + "..."
    seo_slug = meta.get("seo_slug", "")
    if seo_slug:
        import re as _re
        meta["seo_slug"] = _re.sub(r"[^a-z0-9-]", "", seo_slug.lower().strip("-"))[:50]

    return meta


def build_frontmatter(
    titre: str,
    slug: str,
    meta: dict,
    image_path: str,
    image_display: str,
    image_width: int,
    image_height: int,
    readtime: int,
    auteur: dict,
) -> str:
    # Paris timezone offset
    now = datetime.now(timezone(timedelta(hours=2)))
    date_str = now.strftime("%Y-%m-%dT%H:%M:%S+02:00")

    tags_yaml = "\n".join(f'  - "{t}"' for t in meta["tags"])

    # Use SEO slug if LLM generated one, otherwise keep the original
    slug_final = meta.get("seo_slug") or slug

    image_val = image_path or ""
    caption = meta.get("image_caption", "Illustration : Daily Planet FR / Génération IA")
    display_line = f'\nimage_display: "{image_display}"' if image_display else ""
    dim_lines = (
        f"\nimage_width: {image_width}\nimage_height: {image_height}"
        if image_display and image_width and image_height else ""
    )

    seo_title = meta.get("seo_title", "")
    chapo = meta.get("chapo", "").replace('"', '\\"')

    lines = [
        "---",
        f'title: "{titre}"',
        f'slug: "{slug_final}"',
        f"date: {date_str}",
        "draft: false",
        f'description: "{meta["description"]}"',
    ]
    if seo_title:
        lines.append(f'seo_title: "{seo_title}"')
    if chapo:
        lines.append(f'chapo: "{chapo}"')
    lines += [
        f'author: "{auteur["author"]}"',
        f'author_role: "{auteur["author_role"]}"',
        f'author_bio: "{auteur["author_bio"]}"',
        f'author_initials: "{auteur["author_initials"]}"',
    ]
    if auteur.get("author_url"):
        lines.append(f'author_url: "{auteur["author_url"]}"')
    if auteur.get("author_linkedin"):
        lines.append(f'author_linkedin: "{auteur["author_linkedin"]}"')
    if auteur.get("author_x"):
        lines.append(f'author_x: "{auteur["author_x"]}"')
    lines += [
        "tags:",
        tags_yaml,
        f"readtime: {readtime}",
        f'image: "{image_val}"' + display_line + dim_lines,
        f'image_caption: "{caption}"',
        "featured: false",
        "---",
    ]
    return "\n".join(lines)


def write_article_file(slug: str, frontmatter: str, body: str) -> str:
    os.makedirs(CONTENT_POSTS, exist_ok=True)
    filepath = os.path.join(CONTENT_POSTS, f"{slug}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(frontmatter)
        f.write("\n\n")
        f.write(body)
        f.write("\n")
    return filepath


def update_db(article_id: int):
    if not article_id:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE articles SET statut = 'publié' WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()


# ── Interface pipeline ────────────────────────────────────────────────────────

def run(context: dict) -> dict:
    article_id      = context.get("article_id")
    article_titre   = context.get("article_titre", "")
    article_slug    = context.get("article_slug", "")
    article_contenu = context.get("article_contenu", "")
    article_image   = context.get("article_image", "")
    article_image_display = context.get("article_image_display", "")
    article_image_width   = context.get("article_image_width", 0)
    article_image_height  = context.get("article_image_height", 0)

    if not article_contenu:
        # Fallback : lire depuis SQLite si contenu absent du contexte
        if article_id:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                "SELECT titre_final, slug, contenu, image_locale FROM articles WHERE id = ?",
                (article_id,),
            )
            row = c.fetchone()
            conn.close()
            if row:
                article_titre, article_slug, article_contenu, article_image = row
        if not article_contenu:
            raise ValueError(
                "Aucun article_contenu dans le contexte. Étape 3 a-t-elle tourné ?"
            )

    meta    = generate_metadata(article_titre, article_contenu)
    auteur  = random.choice(AUTEURS)
    readtime = calc_readtime(article_contenu)

    body = strip_title_heading(article_contenu)
    body = insert_more_tag(body)

    frontmatter = build_frontmatter(
        article_titre, article_slug, meta,
        article_image, article_image_display,
        article_image_width, article_image_height,
        readtime, auteur,
    )

    filepath = write_article_file(article_slug, frontmatter, body)
    update_db(article_id)

    return {
        "article_filepath": filepath,
        "article_titre": article_titre,
        "article_slug": article_slug,
    }


# ── Test direct ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    # Lit le dernier article rédigé en base
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, titre_final, slug, contenu, image_locale "
        "FROM articles ORDER BY id DESC LIMIT 1"
    )
    row = c.fetchone()
    conn.close()

    if not row:
        print("Aucun article en base. Lance d'abord python pipeline/3_redaction.py")
        sys.exit(1)

    article_id, titre, slug, contenu, image = row
    print(f"\nArticle en base : [{article_id}] {titre}")
    print(f"Slug : {slug}\n")

    context = {
        "article_id": article_id,
        "article_titre": titre,
        "article_slug": slug,
        "article_contenu": contenu,
        "article_image": image or "",
    }

    print("Génération des métadonnées SEO...", flush=True)
    result = run(context)

    filepath = result["article_filepath"]
    print(f"\n✓ Fichier créé : {filepath}")
    print()

    # Affiche le frontmatter généré
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    end_fm = content.find("---", 3)
    print(content[:end_fm + 3])
    print()

    # Vérifie avec hugo
    hugo_check = subprocess.run(
        ["hugo", "--minify", "--quiet"],
        capture_output=True, text=True,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )
    if hugo_check.returncode == 0:
        print("✓ Hugo build OK — article valide.")
    else:
        print("✗ Hugo build erreur :")
        print(hugo_check.stderr[:500])
