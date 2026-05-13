"""
Daily Planet FR — Pipeline principal
Usage : python pipeline/main_pipeline.py
"""

import sys
import os
import time
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

    costs = result.get("_costs", {})
    if any(v > 0 for v in costs.values()):
        print()
        print("  Coûts API :")
        print(f"    Perplexity  : ${costs.get('perplexity_usd', 0):.4f}")
        print(f"    Claude      : ${costs.get('claude_usd', 0):.4f}")
        print(f"    Image (kie) : ${costs.get('image_usd', 0):.4f}")
        print(f"    ─────────────────────────")
        print(f"    Total CRON  : ${costs.get('total_usd', 0):.4f}")

    print()
    print("  Article créé. En attente de déploiement Cloudflare.")
    print("=" * 55)
    print()


def run():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    run_id = os.getenv("RUN_ID", "")

    # Dashboard tracking — non-critical, wrapped in try/except
    tracker = None
    if run_id:
        try:
            import run_tracker
            run_tracker.init(run_id, STEPS)
            tracker = run_tracker
        except Exception as e:
            print(f"  [tracker] init échoué (non bloquant) : {e}")

    print_header()

    context = {}
    costs = {"perplexity_usd": 0.0, "claude_usd": 0.0, "image_usd": 0.0}

    for i, (module_name, label) in enumerate(STEPS, start=1):
        print_step(i, len(STEPS), label)

        if tracker:
            try:
                tracker.step_start(run_id, module_name)
            except Exception:
                pass

        t0 = time.time()
        try:
            module = __import__(module_name)
            result = module.run(context)
            duration = time.time() - t0

            if result:
                context.update(result)
                costs["perplexity_usd"] += result.get("_cost_perplexity_usd", 0.0)
                costs["claude_usd"]     += result.get("_cost_claude_usd", 0.0)
                costs["image_usd"]      += result.get("_cost_image_usd", 0.0)

            if tracker:
                try:
                    tracker.step_ok(run_id, module_name, duration)
                except Exception:
                    pass

            print_ok()

        except Exception as e:
            duration = time.time() - t0
            error_str = f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"

            if tracker:
                try:
                    tracker.step_fail(run_id, module_name, duration, error_str)
                    tracker.update_costs(
                        run_id,
                        perplexity=costs["perplexity_usd"],
                        claude=costs["claude_usd"],
                        image=costs["image_usd"],
                    )
                except Exception:
                    pass

            print(f"\n\n  ✗ Erreur à l'étape {i} ({label})")
            print(f"  {type(e).__name__}: {e}")
            print()
            print("  Détail :")
            traceback.print_exc()
            print()
            print("  Pipeline interrompu.")
            sys.exit(1)

    costs["total_usd"] = costs["perplexity_usd"] + costs["claude_usd"] + costs["image_usd"]
    context["_costs"] = costs

    if tracker:
        try:
            tracker.update_costs(
                run_id,
                perplexity=costs["perplexity_usd"],
                claude=costs["claude_usd"],
                image=costs["image_usd"],
            )
            # Mark as pipeline_ok — cron_pipeline.sh will finalize to "success" after git push
            tracker.finish(
                run_id,
                status="pipeline_ok",
                article_titre=context.get("article_titre"),
                article_slug=context.get("article_slug"),
            )
        except Exception:
            pass

    print_summary(context)


if __name__ == "__main__":
    run()
