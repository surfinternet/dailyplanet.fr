"""
Étape 1 — Recherche des sujets d'actualité IA/tech via OpenRouter/Perplexity
"""

import os
import sys
import json
import sqlite3
import requests
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from cost import usage_cost

_perplexity_cost_usd = 0.0

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "dailyplanet.db")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SEARCH_PROMPT = """Tu es un veilleur spécialisé en intelligence artificielle et technologies numériques.

Utilise ta capacité de recherche en temps réel pour trouver les 8 actualités les plus importantes et récentes sur l'IA et la tech publiées au cours des 48 dernières heures. Privilégie :
- Les annonces de nouveaux modèles ou produits IA
- Les développements réglementaires (Europe, USA, Chine)
- Les levées de fonds et mouvements stratégiques dans l'industrie IA
- Les controverses, études ou rapports marquants sur l'IA

IMPORTANT : N'inclus QUE des actualités publiées dans les 48 dernières heures. Rejette toute news antérieure même si elle est pertinente.

Pour chaque sujet, fournis :
- titre : un titre descriptif et informatif (max 120 caractères)
- source : nom du média ou de l'organisation source
- url_source : URL directe de l'article ou du communiqué
- date_publiee : date de publication (format YYYY-MM-DD)

Retourne UNIQUEMENT un tableau JSON valide, sans texte avant ni après, sans bloc markdown.
Format exact : [{"titre": "...", "source": "...", "url_source": "...", "date_publiee": "..."}, ...]"""


def build_search_prompt() -> str:
    return SEARCH_PROMPT


def call_perplexity(api_key: str) -> list:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://dailyplanet.fr",
    }
    payload = {
        "model": "perplexity/sonar-pro",
        "messages": [{"role": "user", "content": build_search_prompt()}],
    }

    response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    global _perplexity_cost_usd
    resp_data = response.json()
    _perplexity_cost_usd += usage_cost("perplexity/sonar-pro", resp_data.get("usage", {}))
    content = resp_data["choices"][0]["message"]["content"].strip()

    # Strip markdown code blocks if Perplexity wraps the JSON
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        sujets = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Réponse non parseable en JSON : {e}\nContenu reçu : {content[:500]}"
        )

    if not isinstance(sujets, list):
        raise ValueError(f"Attendu : liste JSON. Reçu : {type(sujets).__name__}")

    return sujets


def save_to_db(sujets: list) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    saved = 0
    date_today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for s in sujets:
        titre = (s.get("titre") or "").strip()
        url   = (s.get("url_source") or "").strip()
        source = (s.get("source") or "").strip()

        if not titre:
            continue

        # Dédup : même URL déjà en base → on passe
        if url:
            c.execute("SELECT id FROM sujets WHERE url_source = ?", (url,))
            if c.fetchone():
                continue

        c.execute(
            """INSERT INTO sujets (titre, source, url_source, score, date_trouve, statut)
               VALUES (?, ?, ?, 0, ?, 'trouvé')""",
            (titre, source, url, date_today),
        )
        saved += 1

    conn.commit()
    conn.close()
    return saved


def recycle_stale(conn: sqlite3.Connection) -> int:
    """Reset 'ignoré' and stuck 'sélectionné' subjects back to 'trouvé'."""
    c = conn.cursor()
    c.execute(
        "UPDATE sujets SET statut = 'trouvé' WHERE statut IN ('ignoré', 'sélectionné')"
    )
    recycled = c.rowcount
    conn.commit()
    return recycled


def recycle_treated(conn: sqlite3.Connection) -> int:
    """Last resort: reset all 'traité' subjects to 'trouvé' so the pipeline never stalls."""
    c = conn.cursor()
    c.execute("UPDATE sujets SET statut = 'trouvé' WHERE statut = 'traité'")
    recycled = c.rowcount
    conn.commit()
    return recycled


def run(context: dict) -> dict:
    global _perplexity_cost_usd
    _perplexity_cost_usd = 0.0

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key or api_key.startswith("sk-or-remplacez"):
        raise ValueError("OPENROUTER_API_KEY manquante ou non configurée dans .env")

    sujets = call_perplexity(api_key)
    nb_saved = save_to_db(sujets)

    if nb_saved == 0:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # If 'trouvé' subjects already exist, no action needed — step 2 will pick one
        c.execute("SELECT COUNT(*) FROM sujets WHERE statut = 'trouvé'")
        already_available = c.fetchone()[0]

        if already_available > 0:
            print(f"  ⚠ 0 nouveau sujet (doublons API) — {already_available} sujet(s) 'trouvé' déjà disponibles")
            conn.close()
        else:
            recycled = recycle_stale(conn)
            if recycled == 0:
                # All subjects treated — recycle them so pipeline never stalls
                recycled = recycle_treated(conn)
                if recycled > 0:
                    print(f"  ⚠ DB épuisée — {recycled} sujet(s) 'traité' recyclé(s) vers 'trouvé'")
            else:
                print(f"  ⚠ 0 nouveau sujet (doublons API) — {recycled} sujet(s) recyclé(s) vers 'trouvé'")
            conn.close()
            if recycled == 0:
                raise RuntimeError(
                    "Base de données vide et aucun sujet récupérable. "
                    "Vérifier la connexion à l'API Perplexity."
                )

    return {
        "nb_sujets_trouves": nb_saved,
        "_sujets_raw": sujets,
        "_cost_perplexity_usd": _perplexity_cost_usd,
    }


# ── Test direct ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    print("\nRecherche en cours (Perplexity/sonar-pro)...\n")

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key or api_key.startswith("sk-or-remplacez"):
        print("Erreur : OPENROUTER_API_KEY manquante dans .env")
        sys.exit(1)

    try:
        sujets = call_perplexity(api_key)
    except Exception as e:
        print(f"Erreur appel API : {e}")
        sys.exit(1)

    print(f"{len(sujets)} sujet(s) trouvé(s) :\n")
    for i, s in enumerate(sujets, 1):
        print(f"  {i}. {s.get('titre', '?')}")
        print(f"     Source : {s.get('source', '?')}")
        print(f"     URL    : {s.get('url_source', '?')}")
        print()

    nb = save_to_db(sujets)
    print(f"✓ {nb} nouveau(x) sauvegardé(s) en base (doublons ignorés).")
