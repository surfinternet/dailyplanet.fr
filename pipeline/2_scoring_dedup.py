"""
Étape 2 — Scoring, déduplication et sélection du meilleur sujet

Critères de score :
  - Mots-clés haute valeur Google Discover (+10 par match)
  - Chiffres concrets dans le titre (+5)
  - Pénalité titre trop court < 30 chars (-10)

Dédup (3 niveaux) :
  - Sujets statut='traité' jamais reconsidérés (filtre SQL)
  - Titres trop similaires à un 'traité' existant : ignorés (overlap > 60 %)
  - Titres trop similaires aux articles publiés dans les 7 derniers jours (overlap > 35 %)
  - Combo entité+événement identique dans un article publié dans les 48h : ignoré
"""

import os
import re
import sys
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "dailyplanet.db")

HIGH_VALUE_KEYWORDS = [
    "milliard", "million", "$", "€",
    "openai", "anthropic", "google", "meta", "apple", "microsoft", "mistral", "xai",
    "gpt", "claude", "gemini", "llama", "deepseek",
    "régulation", "loi", "interdit", "enquête", "procès", "criminel",
    "licencie", "rachat", "acquisition", "fusion",
    "record", "premier", "nouveau", "exclusif",
]

STOP_WORDS = {
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "en",
    "à", "au", "aux", "sur", "par", "pour", "dans", "avec", "sans",
    "qui", "que", "est", "sont", "ses", "son", "sa",
}

# Entités : si même entité + même groupe d'événement trouvés dans un article < 48h → doublon
ENTITIES = [
    "anthropic", "openai", "google", "meta", "apple", "microsoft", "mistral",
    "xai", "nvidia", "amazon", "aws", "deepseek", "grok", "chatgpt", "gemini",
    "claude", "llama", "sora", "copilot", "hugging face", "cohere",
]

EVENT_GROUPS = {
    "financement":   ["milliard", "million", "levée", "lève", "encaisse", "fonds",
                      "investissement", "valorisation", "tour de table", "raises",
                      "funding", "invest"],
    "acquisition":   ["rachète", "acquiert", "acquisition", "fusion", "achat", "buys",
                      "acquires", "merges"],
    "licenciement":  ["licencie", "supprime", "postes", "emplois", "layoff", "cuts"],
    "procès":        ["procès", "enquête", "amende", "condamné", "jugement",
                      "lawsuit", "fine", "sued"],
    "lancement":     ["lance", "dévoile", "annonce", "présente", "launches",
                      "reveals", "announces"],
}


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


def words(titre: str) -> set:
    return set(titre.lower().split()) - STOP_WORDS


def too_similar(titre_a: str, titre_b: str, threshold: float = 0.6) -> bool:
    wa, wb = words(titre_a), words(titre_b)
    if not wa or not wb:
        return False
    overlap = len(wa & wb) / min(len(wa), len(wb))
    return overlap > threshold


def entity_event_combo(titre: str) -> set:
    """Return set of (entity, event_group) tuples found in title."""
    t = titre.lower()
    combos = set()
    for entity in ENTITIES:
        if entity in t:
            for group_name, keywords in EVENT_GROUPS.items():
                if any(kw in t for kw in keywords):
                    combos.add((entity, group_name))
    return combos


def run(context: dict) -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Tous les sujets déjà traités → référence pour dédup (overlap > 60%)
    c.execute("SELECT titre FROM sujets WHERE statut = 'traité'")
    traites = [r[0] for r in c.fetchall()]

    # Articles publiés dans les 7 derniers jours → dédup élargi (overlap > 35%)
    cutoff_7d = (datetime.utcnow() - timedelta(days=7)).isoformat()
    c.execute(
        "SELECT titre_final FROM articles WHERE date_creation > ?", (cutoff_7d,)
    )
    articles_recents = [r[0] for r in c.fetchall() if r[0]]

    # Articles publiés dans les 48h → dédup entité+événement
    cutoff_48h = (datetime.utcnow() - timedelta(hours=48)).isoformat()
    c.execute(
        "SELECT titre_final FROM articles WHERE date_creation > ?", (cutoff_48h,)
    )
    articles_48h = [r[0] for r in c.fetchall() if r[0]]
    combos_48h = set()
    for t in articles_48h:
        combos_48h.update(entity_event_combo(t))

    # Candidats : statut='trouvé' uniquement
    c.execute(
        "SELECT id, titre, source, url_source FROM sujets WHERE statut = 'trouvé'"
    )
    candidats = c.fetchall()

    if not candidats:
        conn.close()
        raise RuntimeError(
            "Aucun sujet avec statut='trouvé' en base. "
            "Lance d'abord : python pipeline/1_recherche_sujets.py"
        )

    # Score + filtre doublons (3 niveaux)
    scores = []
    for sujet_id, titre, source, url in candidats:
        # Niveau 1 : overlap > 60% avec sujets traités
        if any(too_similar(titre, t, threshold=0.6) for t in traites):
            c.execute("UPDATE sujets SET statut = 'ignoré' WHERE id = ?", (sujet_id,))
            continue

        # Niveau 2 : overlap > 35% avec articles récents (7j)
        if any(too_similar(titre, t, threshold=0.35) for t in articles_recents):
            c.execute("UPDATE sujets SET statut = 'ignoré' WHERE id = ?", (sujet_id,))
            continue

        # Niveau 3 : combo entité+événement identique dans les 48h
        candidate_combos = entity_event_combo(titre)
        if candidate_combos & combos_48h:
            c.execute("UPDATE sujets SET statut = 'ignoré' WHERE id = ?", (sujet_id,))
            continue

        scores.append((score_titre(titre), sujet_id, titre, source, url))

    conn.commit()

    if not scores:
        conn.close()
        raise RuntimeError(
            "Tous les sujets sont trop similaires à des articles déjà traités."
        )

    # Meilleur score
    scores.sort(reverse=True)
    _, best_id, best_titre, best_source, best_url = scores[0]

    # Marque le gagnant sélectionné, ignore les autres
    c.execute("UPDATE sujets SET statut = 'sélectionné' WHERE id = ?", (best_id,))
    for _, sid, *_ in scores[1:]:
        c.execute("UPDATE sujets SET statut = 'ignoré' WHERE id = ?", (sid,))

    conn.commit()
    conn.close()

    return {
        "sujet_id": best_id,
        "sujet_titre": best_titre,
        "sujet_source": best_source,
        "sujet_url": best_url,
    }


# ── Test direct ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Injecte un sujet fictif statut='traité' pour tester la dédup
    c.execute("""
        INSERT INTO sujets (titre, source, url_source, score, date_trouve, statut)
        VALUES ('Google investit dans Anthropic milliards', 'test', 'http://test.com', 0, '2026-01-01', 'traité')
    """)
    conn.commit()
    conn.close()

    print("Sujet 'traité' injecté pour test dédup.\n")

    try:
        result = run({})
    except RuntimeError as e:
        print(f"Erreur attendue (ou pas de candidats) : {e}")
        sys.exit(0)

    print(f"Sujet sélectionné :")
    print(f"  ID     : {result['sujet_id']}")
    print(f"  Titre  : {result['sujet_titre']}")
    print(f"  Source : {result['sujet_source']}")
    print()

    # Vérifie que le sujet traité n'a pas été sélectionné
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT titre, statut FROM sujets ORDER BY id")
    rows = c.fetchall()
    conn.close()

    print("État final de la base :")
    for titre, statut in rows:
        marker = "← SÉLECTIONNÉ" if statut == "sélectionné" else ""
        print(f"  [{statut:12}] {titre[:70]} {marker}")

    # Nettoyage sujet test
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM sujets WHERE url_source = 'http://test.com'")
    conn.commit()
    conn.close()
    print("\n✓ Sujet test supprimé.")
