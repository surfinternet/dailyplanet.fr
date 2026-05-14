"""
Migration — ajoute la colonne `resume` à la table sujets.
À exécuter une seule fois sur le VPS après déploiement.

Usage : python pipeline/db/migrate_add_resume.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "dailyplanet.db")


def migrate():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Vérifie si la colonne existe déjà
    c.execute("PRAGMA table_info(sujets)")
    columns = [row[1] for row in c.fetchall()]

    if "resume" in columns:
        print("✓ Colonne 'resume' déjà présente — rien à faire.")
        conn.close()
        return

    c.execute("ALTER TABLE sujets ADD COLUMN resume TEXT")
    conn.commit()
    conn.close()
    print("✓ Colonne 'resume' ajoutée à la table sujets.")


if __name__ == "__main__":
    migrate()
