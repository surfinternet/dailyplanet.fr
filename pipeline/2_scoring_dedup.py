"""
Étape 2 — Scoring, déduplication et sélection du meilleur sujet

Critères de score :
  - Mots-clés haute valeur Google Discover (+10 par match)
  - Chiffres concrets dans le titre (+5)
  - Pénalité titre trop court < 30 chars (-10)

Dédup (2 niveaux) :
  - Filtre SQL : sujets statut='traité' jamais reconsidérés
  - Analyse LLM : comparaison sémantique contre les articles publiés (7 derniers jours)
    → détecte les doublons même si les mots sont différents (ex: "8 milliards" ≠ "dix milliards"
      mais même événement Anthropic funding)
"""

import os
import re
import sys
import json
import sqlite3
import requests
import subprocess
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "dailyplanet.db")
OPENROUTER_URL = "https://openrouter.ai/api/v1"

HIGH_VALUE_KEYWORDS = [
    "milliard", "million", "$", "€",
    "openai", "anthropic", "google", "meta", "apple", "microsoft", "mistral", "xai",
    "gpt", "claude", "gemini", "llama", "deepseek",
    "régulation", "loi", "interdit", "enquête", "procès", "criminel",
    "licencie", "rachat", "acquisition", "fusion",
    "record", "premier", "nouveau", "exclusif",
]

DEDUP_PROMPT = """\
Tu es l'éditeur d'un site d'actualités IA/tech. Voici les articles déjà publiés ces 7 derniers jours :

{articles_recents}

Voici les sujets candidats pour le prochain article (avec leur ID) :

{candidats}

Pour chaque candidat, détermine s'il est un DOUBLON SÉMANTIQUE d'un article déjà publié.
Doublon = même événement principal + même acteur, même si les formulations sont différentes.
  - "Anthropic lève 10 milliards" ET "Anthropic encaisse 8 milliards" → DOUBLON (même entreprise, même levée de fonds)
  - "Google investit dans Anthropic" ET "Anthropic annonce son modèle Claude 4" → PAS doublon (événements différents)

Réponds UNIQUEMENT avec un JSON valide, sans markdown, sans commentaire.
Format : [{{"id": 1, "duplicate": false}}, {{"id": 2, "duplicate": true, "reason": "Même levée de fonds Anthropic que l'article du 13/05"}}]"""


def score_titre(titre: str) -> float:
    score = 0.0
    t = titre.lower()
    for kw in HIGH_VALUE_KEYWORDS:
        if kw in t:
            score += 10
    if re.search(r"\d+", titre):
        score += 5
    if len(titre) < 30:
        score -= 10
    return score


def openrouter_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://dailyplanet.fr",
    }


def llm_dedup(candidats: list, articles_recents: list) -> dict:
    """
    Ask LLM to detect semantic duplicates.
    Returns dict: {sujet_id: True/False (is_duplicate)}
    """
    if not articles_recents:
        return {sid: False for sid, _, _, _ in candidats}

    articles_str = "\n".join(f"- {t}" for t in articles_recents)
    candidats_str = "\n".join(f"- ID {sid}: {titre}" for sid, titre, _, _ in candidats)
    prompt = DEDUP_PROMPT.format(
        articles_recents=articles_str,
        candidats=candidats_str,
    )

    mode = os.getenv("MODE", "local")

    if mode == "local":
        cli_path = os.getenv("CLAUDE_CLI_PATH", "claude")
        result = subprocess.run(
            [cli_path, "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI erreur dédup : {result.stderr[:300]}")
        content = result.stdout.strip()
    else:
        payload = {
            "model": os.getenv("CLAUDE_MODEL", "anthropic/claude-sonnet-4-6"),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1500,
        }
        r = requests.post(
            f"{OPENROUTER_URL}/chat/completions",
            headers=openrouter_headers(),
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()

    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        results = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Réponse LLM dédup non parseable : {e}\nContenu : {content[:300]}")

    return {item["id"]: item.get("duplicate", False) for item in results}


def run(context: dict) -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Candidats : statut='trouvé' uniquement (les 'traité' sont déjà exclus par SQL)
    c.execute(
        "SELECT id, titre, source, url_source, resume FROM sujets WHERE statut = 'trouvé'"
    )
    candidats = c.fetchall()

    if not candidats:
        conn.close()
        raise RuntimeError(
            "Aucun sujet avec statut='trouvé' en base. "
            "Lance d'abord : python pipeline/1_recherche_sujets.py"
        )

    # Articles publiés dans les 7 derniers jours → référence pour la dédup LLM
    cutoff_7d = (datetime.utcnow() - timedelta(days=7)).isoformat()
    c.execute(
        "SELECT titre_final FROM articles WHERE date_creation > ? ORDER BY date_creation DESC",
        (cutoff_7d,),
    )
    articles_recents = [r[0] for r in c.fetchall() if r[0]]

    # Analyse LLM : détecte les doublons sémantiques (passe seulement id/titre/source/url)
    candidats_dedup = [(sid, titre, source, url) for sid, titre, source, url, resume in candidats]
    duplicates = llm_dedup(candidats_dedup, articles_recents)

    # Filtre + scoring
    scores = []
    for sujet_id, titre, source, url, resume in candidats:
        if duplicates.get(sujet_id, False):
            c.execute("UPDATE sujets SET statut = 'ignoré' WHERE id = ?", (sujet_id,))
            continue
        scores.append((score_titre(titre), sujet_id, titre, source, url, resume))

    conn.commit()

    if not scores:
        conn.close()
        raise RuntimeError(
            "Tous les sujets sont des doublons sémantiques d'articles récents."
        )

    # Meilleur score
    scores.sort(reverse=True)
    _, best_id, best_titre, best_source, best_url, best_resume = scores[0]

    c.execute("UPDATE sujets SET statut = 'sélectionné' WHERE id = ?", (best_id,))
    for _, sid, *_ in scores[1:]:
        c.execute("UPDATE sujets SET statut = 'ignoré' WHERE id = ?", (sid,))

    conn.commit()
    conn.close()

    return {
        "sujet_id":     best_id,
        "sujet_titre":  best_titre,
        "sujet_source": best_source,
        "sujet_url":    best_url,
        "sujet_resume": best_resume or "",
    }


# ── Test direct ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    # Simule un article récent pour tester la dédup sémantique
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fake_date = (datetime.utcnow() - timedelta(hours=2)).isoformat()
    c.execute("""
        INSERT INTO articles (sujet_id, titre_final, slug, statut, date_creation)
        VALUES (NULL, 'Anthropic encaisse 8 milliards et reste coincée entre deux géants',
                'test-anthropic-8b', 'publié', ?)
    """, (fake_date,))
    conn.commit()
    conn.close()

    print("Article test injecté : 'Anthropic encaisse 8 milliards...'\n")

    try:
        result = run({})
    except RuntimeError as e:
        print(f"Résultat : {e}")
    else:
        print(f"Sujet sélectionné : {result['sujet_titre']}")

    # Nettoyage
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM articles WHERE slug = 'test-anthropic-8b'")
    conn.commit()
    conn.close()
    print("\n✓ Article test supprimé.")
