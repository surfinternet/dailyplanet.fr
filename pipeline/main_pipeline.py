"""
Daily Planet FR — Pipeline principal
Usage : python pipeline/main_pipeline.py
"""

import sys
import os
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

STEPS = [
    ("1_recherche_sujets",    "Recherche des sujets d'actualité"),
    ("2_scoring_dedup",       "Scoring et sélection du meilleur sujet"),
    ("3_redaction",           "Rédaction de l'article"),
    ("4_generation_image",    "Génération de l'image"),
    ("5_construction_article","Construction du fichier Hugo"),
]


def print_header():
    print()
    print("=" * 55)
    print("  DAILY PLANET FR — Pipeline de publication")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 55)
    print()


def print_step(index, total, label):
    print(f"  [{index}/{total}] {label}...", end=" ", flush=True)


def print_ok():
    print("✓")


def print_summary(result: dict):
    print()
    print("=" * 55)
    print("  RÉSUMÉ")
    print("=" * 55)
    titre = result.get("article_titre", "(non disponible)")
    slug  = result.get("article_slug", "")
    url   = f"{os.getenv('SITE_BASE_URL', 'https://dailyplanet.fr')}/posts/{slug}/" if slug else ""
    print(f"  Titre   : {titre}")
    if url:
        print(f"  URL     : {url}")
    image = result.get("article_image", "")
    if image:
        print(f"  Image   : {image}")
    print()
    print("  Article créé. En attente de déploiement Cloudflare.")
    print("=" * 55)
    print()


def run():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    print_header()

    context = {}  # données partagées entre les étapes

    for i, (module_name, label) in enumerate(STEPS, start=1):
        print_step(i, len(STEPS), label)
        try:
            module = __import__(module_name)
            result = module.run(context)
            if result:
                context.update(result)
            print_ok()
        except Exception as e:
            print(f"\n\n  ✗ Erreur à l'étape {i} ({label})")
            print(f"  {type(e).__name__}: {e}")
            print()
            print("  Détail :")
            traceback.print_exc()
            print()
            print("  Pipeline interrompu.")
            sys.exit(1)

    print_summary(context)


if __name__ == "__main__":
    run()
