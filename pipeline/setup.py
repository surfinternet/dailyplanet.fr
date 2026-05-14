"""
Daily Planet FR — Pipeline setup
Creates SQLite database and tables.
Run once before first pipeline execution: python pipeline/setup.py
"""

import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "dailyplanet.db")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS sujets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            titre       TEXT NOT NULL,
            source      TEXT,
            url_source  TEXT,
            resume      TEXT,
            score       REAL DEFAULT 0,
            date_trouve TEXT NOT NULL,
            statut      TEXT NOT NULL DEFAULT 'trouvé'
        )
    """)
    # statut lifecycle: trouvé → sélectionné → traité → ignoré

    c.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            sujet_id      INTEGER REFERENCES sujets(id),
            titre_final   TEXT,
            slug          TEXT UNIQUE,
            contenu       TEXT,
            image_locale  TEXT,
            statut        TEXT NOT NULL DEFAULT 'rédigé',
            date_creation TEXT NOT NULL
        )
    """)
    # statut lifecycle: rédigé → image_ok → publié

    conn.commit()
    conn.close()
    print(f"✓ Base de données initialisée : {DB_PATH}")


if __name__ == "__main__":
    init_db()
    print("✓ Setup terminé. Lance le pipeline avec : python pipeline/main_pipeline.py")
