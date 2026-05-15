"""
Étape 1 — Recherche des sujets d'actualité IA/tech via flux RSS
"""

import os
import re
import sys
import sqlite3
import feedparser
from datetime import datetime, timezone, timedelta
from calendar import timegm

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "dailyplanet.db")

RSS_FEEDS = [
    ("TechCrunch AI",   "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge AI",    "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"),
    ("VentureBeat AI",  "https://venturebeat.com/ai/feed/"),
    ("Wired AI",        "https://www.wired.com/feed/tag/artificial-intelligence/latest/rss"),
    ("Ars Technica",    "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
]

MAX_ARTICLES = 15


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _entry_pub_datetime(entry):
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if t is None:
        return None
    return datetime.fromtimestamp(timegm(t), tz=timezone.utc)


def fetch_rss_articles(max_age_hours: int = 48) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    articles = []
    seen_urls = set()

    for feed_name, feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url, request_headers={"User-Agent": "DailyPlanetFR/1.0"})
        except Exception as e:
            print(f"  ⚠ Flux {feed_name} inaccessible : {e}")
            continue

        for entry in feed.entries:
            url = (entry.get("link") or "").strip()
            if not url or url in seen_urls:
                continue

            pub_dt = _entry_pub_datetime(entry)
            if pub_dt is None or pub_dt < cutoff:
                continue

            titre = (entry.get("title") or "").strip()
            if not titre:
                continue

            summary = _strip_html(entry.get("summary") or entry.get("description") or "")
            # Tronquer le résumé à 500 chars
            if len(summary) > 500:
                summary = summary[:497] + "..."

            articles.append({
                "titre": titre,
                "source": feed_name,
                "url_source": url,
                "resume": summary,
                "date_publiee": pub_dt.strftime("%Y-%m-%d"),
            })
            seen_urls.add(url)

    # Fallback : si trop peu de résultats, élargir à 72h
    if len(articles) < 5 and max_age_hours < 72:
        print(f"  ⚠ Seulement {len(articles)} article(s) sur {max_age_hours}h — élargissement à 72h")
        return fetch_rss_articles(max_age_hours=72)

    # Trier par date décroissante, limiter
    articles.sort(key=lambda a: a["date_publiee"], reverse=True)
    return articles[:MAX_ARTICLES]


def save_to_db(sujets: list) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    saved = 0
    date_today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for s in sujets:
        titre = (s.get("titre") or "").strip()
        url   = (s.get("url_source") or "").strip()
        source = (s.get("source") or "").strip()
        resume = (s.get("resume") or "").strip()

        if not titre:
            continue

        # Dédup : même URL déjà en base → on passe
        if url:
            c.execute("SELECT id FROM sujets WHERE url_source = ?", (url,))
            if c.fetchone():
                continue

        c.execute(
            """INSERT INTO sujets (titre, source, url_source, resume, score, date_trouve, statut)
               VALUES (?, ?, ?, ?, 0, ?, 'trouvé')""",
            (titre, source, url, resume, date_today),
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
    sujets = fetch_rss_articles()
    nb_saved = save_to_db(sujets)

    if nb_saved == 0:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM sujets WHERE statut = 'trouvé'")
        already_available = c.fetchone()[0]

        if already_available > 0:
            print(f"  ⚠ 0 nouveau sujet (doublons RSS) — {already_available} sujet(s) 'trouvé' déjà disponibles")
            conn.close()
        else:
            recycled = recycle_stale(conn)
            if recycled == 0:
                recycled = recycle_treated(conn)
                if recycled > 0:
                    print(f"  ⚠ DB épuisée — {recycled} sujet(s) 'traité' recyclé(s) vers 'trouvé'")
            else:
                print(f"  ⚠ 0 nouveau sujet (doublons RSS) — {recycled} sujet(s) recyclé(s) vers 'trouvé'")
            conn.close()
            if recycled == 0:
                raise RuntimeError(
                    "Base de données vide et aucun sujet récupérable. "
                    "Vérifier la connectivité réseau (flux RSS inaccessibles)."
                )

    return {
        "nb_sujets_trouves": nb_saved,
        "_sujets_raw": sujets,
        "_cost_perplexity_usd": 0.0,  # plus d'API payante en step 1
    }


# ── Test direct ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nRecherche en cours (flux RSS)...\n")

    try:
        sujets = fetch_rss_articles()
    except Exception as e:
        print(f"Erreur : {e}")
        sys.exit(1)

    print(f"{len(sujets)} article(s) trouvé(s) :\n")
    for i, s in enumerate(sujets, 1):
        print(f"  {i}. [{s['date_publiee']}] {s['titre']}")
        print(f"     Source : {s['source']}")
        print(f"     URL    : {s['url_source']}")
        print()

    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    nb = save_to_db(sujets)
    print(f"✓ {nb} nouveau(x) sauvegardé(s) en base (doublons ignorés).")
