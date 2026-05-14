"""
Étape 3 — Rédaction de l'article

Mode local      : Claude Code CLI  (CLAUDE_CLI_PATH dans .env)
Mode production : OpenRouter API   (OPENROUTER_API_KEY + CLAUDE_MODEL dans .env)

Deux appels LLM :
  1. Rédaction selon prompts/article-system.md
  2. Pass anti-footprint : corrige les patterns IA détectés
"""

import os
import re
import sys
import sqlite3
import unicodedata
import subprocess
import requests
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from cost import usage_cost

_claude_cost_usd = 0.0

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "dailyplanet.db")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")

ANTIFOOT_PROMPT = """\
Tu es un éditeur exigeant. Lis l'article ci-dessous et corrige UNIQUEMENT \
les patterns de style listés. Ne change rien d'autre — pas de reformulation, \
pas de contenu ajouté ou supprimé, même longueur approximative.

PATTERNS À SUPPRIMER OU REFORMULER :
- Tiret long (—) → virgule, point, ou reformulation
- "Il est important de noter que" → supprimer
- "Dans un monde en constante évolution" → supprimer
- "En conclusion" / "Pour conclure" → supprimer
- Listes à puces dans le corps du texte → prose fluide
- Adverbes vides : vraiment, totalement, clairement, évidemment, simplement
- Superlatifs creux : révolutionnaire, extraordinaire, sans précédent, game-changer
- Transitions académiques en début de paragraphe : Par ailleurs, De plus, En outre, Ainsi

IMPORTANT : Retourne UNIQUEMENT le texte Markdown de l'article, rien d'autre.
Aucun commentaire, aucune explication, aucun séparateur. Même si l'article est déjà propre, retourne-le tel quel sans rien ajouter.

---

ARTICLE :

{article}"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    path = os.path.join(PROMPTS_DIR, "article-system.md")
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def slugify(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:80]


def extract_title(content: str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


# ── Appels LLM ────────────────────────────────────────────────────────────────

def call_claude_cli(prompt: str) -> str:
    cli_path = os.getenv("CLAUDE_CLI_PATH", "claude")
    result = subprocess.run(
        [cli_path, "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Claude CLI erreur (code {result.returncode}) :\n{result.stderr[:500]}"
        )
    output = result.stdout.strip()
    if not output:
        raise RuntimeError("Claude CLI n'a rien retourné (sortie vide).")
    return output


def call_openrouter(system: str, user: str) -> str:
    global _claude_cost_usd
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    model = os.getenv("CLAUDE_MODEL", "anthropic/claude-sonnet-4-6")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://dailyplanet.fr",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 2000,
    }
    response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    resp_data = response.json()
    _claude_cost_usd += usage_cost(model, resp_data.get("usage", {}))
    return resp_data["choices"][0]["message"]["content"].strip()


def llm_call(system: str, user: str) -> str:
    """Appel LLM selon MODE (.env) : local = Claude CLI, production = OpenRouter."""
    mode = os.getenv("MODE", "local")
    if mode == "local":
        return call_claude_cli(f"{system}\n\n---\n\n{user}")
    else:
        return call_openrouter(system, user)


DEEP_RESEARCH_PROMPT = """\
Nous sommes le {date_today}. Tu es un journaliste qui prépare un article sur le sujet suivant :

Sujet : {sujet_titre}
Source principale : {sujet_source}
URL : {sujet_url}

Effectue une recherche approfondie et retourne UNIQUEMENT un bloc de faits structuré en français contenant :
- Les chiffres clés précis avec leur date (ex: "40 milliards de dollars investis en mai 2026")
- Les citations directes des personnes impliquées (avec nom, fonction, date)
- Le contexte récent : événements des 3 derniers mois qui éclairent ce sujet
- Les acteurs principaux concernés et leur rôle
- Les enjeux concrets pour la France et l'Europe si pertinent

Format : texte structuré en 4-6 paragraphes courts. Pas de titres, pas de listes à puces. Chaque fait doit être daté ou sourcé.
Si un chiffre ou fait n'est pas confirmé par tes sources, ne l'invente pas — omets-le."""


# ── Appel Perplexity pour recherche approfondie ───────────────────────────────

def recherche_approfondie(sujet_titre: str, sujet_source: str, sujet_url: str) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key or api_key.startswith("sk-or-remplacez"):
        return ""

    date_today = datetime.now(timezone.utc).strftime("%d %B %Y")
    prompt = DEEP_RESEARCH_PROMPT.format(
        date_today=date_today,
        sujet_titre=sujet_titre,
        sujet_source=sujet_source,
        sujet_url=sujet_url,
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://dailyplanet.fr",
    }
    payload = {
        "model": "perplexity/sonar-pro",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 800,
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        global _claude_cost_usd
        from cost import usage_cost
        _claude_cost_usd += usage_cost("perplexity/sonar-pro", response.json().get("usage", {}))
        return content
    except Exception as e:
        print(f"  ⚠ Recherche approfondie Perplexity échouée : {e}")
        return ""


# ── Logique métier ────────────────────────────────────────────────────────────

def rediger(sujet_titre: str, sujet_source: str, sujet_url: str, sujet_resume: str = "") -> str:
    system = load_system_prompt()
    date_today = datetime.now(timezone.utc).strftime("%d %B %Y")

    # Recherche approfondie via Perplexity (mode production uniquement — CLI n'a pas accès API)
    mode = os.getenv("MODE", "local")
    recherche = ""
    if mode != "local":
        print("  → Recherche approfondie Perplexity en cours...", flush=True)
        recherche = recherche_approfondie(sujet_titre, sujet_source, sujet_url)
        if recherche:
            print(f"  ✓ Recherche obtenue ({len(recherche)} caractères)", flush=True)

    # Construire le bloc de faits disponibles
    faits_blocs = []
    if sujet_resume:
        faits_blocs.append(f"Résumé initial (Perplexity, étape 1) :\n{sujet_resume}")
    if recherche:
        faits_blocs.append(f"Recherche approfondie (Perplexity, {date_today}) :\n{recherche}")

    faits_section = ""
    if faits_blocs:
        faits_section = (
            "\n\nFAITS VÉRIFIÉS POUR CET ARTICLE :\n"
            + "\n\n".join(faits_blocs)
            + "\n\nCes faits sont vérifiés et récents. Appuie-toi dessus. "
            "N'invente pas de statistiques absentes de cette recherche."
        )

    user = (
        f"Date du jour : {date_today}\n"
        f"Sujet : {sujet_titre}\n"
        f"Source : {sujet_source}\n"
        f"URL de référence : {sujet_url}"
        f"{faits_section}\n\n"
        "Rédige l'article complet selon les instructions. "
        "Commence immédiatement par la ligne `# Titre de l'article`."
    )
    return llm_call(system, user)


def strip_trailing_commentary(text: str) -> str:
    """Remove any editor commentary appended after a trailing '---' separator."""
    lines = text.splitlines()
    # Walk backwards to find the last '---' that is followed only by non-article text
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == "---":
            # Keep only the content before this separator
            return "\n".join(lines[:i]).rstrip()
    return text


def antifoot_pass(contenu: str) -> str:
    system = (
        "Tu es un éditeur qui corrige uniquement les patterns IA listés. "
        "Retourne uniquement le Markdown corrigé, rien d'autre."
    )
    user = ANTIFOOT_PROMPT.format(article=contenu)
    result = llm_call(system, user)
    return strip_trailing_commentary(result)


def save_to_db(sujet_id: int, titre: str, slug: str, contenu: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    date_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    c.execute(
        """INSERT INTO articles (sujet_id, titre_final, slug, contenu, statut, date_creation)
           VALUES (?, ?, ?, ?, 'rédigé', ?)""",
        (sujet_id, titre, slug, contenu, date_now),
    )
    article_id = c.lastrowid
    c.execute("UPDATE sujets SET statut = 'traité' WHERE id = ?", (sujet_id,))

    conn.commit()
    conn.close()
    return article_id


# ── Interface pipeline ────────────────────────────────────────────────────────

def run(context: dict) -> dict:
    global _claude_cost_usd
    _claude_cost_usd = 0.0

    sujet_id     = context.get("sujet_id")
    sujet_titre  = context.get("sujet_titre", "")
    sujet_source = context.get("sujet_source", "")
    sujet_url    = context.get("sujet_url", "")
    sujet_resume = context.get("sujet_resume", "")

    if not sujet_titre:
        raise ValueError("Aucun sujet_titre dans le contexte. Étape 2 a-t-elle tourné ?")

    contenu = rediger(sujet_titre, sujet_source, sujet_url, sujet_resume)
    contenu = antifoot_pass(contenu)

    titre = extract_title(contenu)
    if not titre:
        # Debug: show first 300 chars to diagnose the format issue
        preview = repr(contenu[:300]) if contenu else "(vide)"
        raise ValueError(
            f"Article généré sans titre (ligne '# ...' introuvable).\n"
            f"Début du contenu reçu : {preview}"
        )

    slug = slugify(titre)
    article_id = save_to_db(sujet_id, titre, slug, contenu)

    return {
        "article_id": article_id,
        "article_titre": titre,
        "article_slug": slug,
        "article_contenu": contenu,
        "_cost_claude_usd": _claude_cost_usd,
    }


# ── Test direct ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    SUJET_TEST = {
        "sujet_id": None,
        "sujet_titre": "Google investit 40 Md$ dans Anthropic, 10 Md$ immédiats",
        "sujet_source": "Le Figaro",
        "sujet_url": "https://www.lefigaro.fr/secteur/high-tech",
    }

    print(f"\nMode : {os.getenv('MODE', 'local')}")
    print(f"Sujet : {SUJET_TEST['sujet_titre']}\n")
    print("Rédaction en cours (appel 1/2)...", flush=True)

    contenu = rediger(
        SUJET_TEST["sujet_titre"],
        SUJET_TEST["sujet_source"],
        SUJET_TEST["sujet_url"],
    )

    print("Pass anti-footprint (appel 2/2)...", flush=True)
    contenu_final = antifoot_pass(contenu)

    titre = extract_title(contenu_final)
    slug  = slugify(titre)

    print(f"\n{'='*60}")
    print(f"Titre : {titre}")
    print(f"Slug  : {slug}")
    print(f"{'='*60}\n")
    print(contenu_final)
    print(f"\n{'='*60}")
    print("Test OK — article non sauvegardé en base (mode test).")
