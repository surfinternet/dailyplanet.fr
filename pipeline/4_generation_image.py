"""
Étape 4 — Génération de l'image via kie.ai / flux-kontext-max

Flux :
  1. LLM call → extrait SUJET_VISUEL, EMOTION, COULEUR_DOMINANTE du titre
  2. Construit le prompt image selon image-system.md
  3. kie.ai async : POST → taskId → polling → URL → download PNG
  4. Convertit en WebP → assets/images/[slug].webp (16:9, ~2K)
  5. Met à jour SQLite : image_locale + statut='image_ok'
"""

import os
import sys
import json
import time
import sqlite3
import requests
from io import BytesIO
from datetime import datetime, timezone

try:
    from PIL import Image
except ImportError:
    Image = None

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "dailyplanet.db")
OPENROUTER_URL = "https://openrouter.ai/api/v1"
KIE_AI_BASE = "https://api.kie.ai/api/v1"
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")
ASSETS_IMAGES = os.path.join(os.path.dirname(__file__), "..", "assets", "images")
STATIC_IMAGES = os.path.join(os.path.dirname(__file__), "..", "static", "images")

IMAGE_TEMPLATE = (
    "Comic book illustration, editorial style. {sujet_visuel}. "
    "Bold black ink outlines, flat {couleur_dominante} color palette with complementary "
    "accent tones, subtle halftone dot texture in shadows and midtones. "
    "Dynamic composition with strong diagonal lines. {emotion} mood. "
    "1970s Marvel Comics cover aesthetic, Jack Kirby influence. "
    "Company logos and brand marks rendered in comics style are encouraged — stylized, bold, integrated into the scene as background elements, signs, or props. "
    "Any text visible in the scene (signs, screens, banners, labels, amounts) must be written in French — use French number formatting (e.g. '8 milliards de $' not '$8 billion', '40 Md$' not '$40B'). "
    "No speech bubbles, no watermarks. "
    "High contrast, professional editorial quality."
)

VARS_PROMPT = """\
À partir du titre et de l'extrait d'article ci-dessous, génère les trois variables pour le prompt image.
Réponds UNIQUEMENT avec un JSON valide, sans markdown, sans commentaire.

Format : {{"sujet_visuel": "...", "emotion": "...", "couleur_dominante": "..."}}

Règles pour sujet_visuel :
- EN ANGLAIS, 2-3 phrases narratives, scène concrète et précise
- Utilise les CHIFFRES EXACTS quand l'article en mentionne — IMPORTANT : formate les montants à l'anglaise pour le prompt image mais ajoute la note (French format on screen) ex: "a screen showing '8 milliards de $'" pas "a screen showing '$8 billion'"
- Place les logos des entreprises citées comme éléments visuels dans la scène : sur des murs, enseignes, écrans, drapeaux, badges — ex: "Google logo on the wall", "Anthropic badge on the door"
- Traduis les institutions en personnages/lieux concrets (ex: militaires pour le Pentagone, chercheurs en blouse pour un labo IA)
- Inclus systématiquement un élément d'inclusion ET un élément d'exclusion si l'article parle de sélection/rejet
- Exemple : "A Pentagon war room, seven tech logos (Amazon, Google, Meta, Microsoft, OpenAI, Palantir, Scale AI) displayed on a glowing tactical screen. Outside the heavy closed door, a figure with an Anthropic badge walks away, briefcase in hand."

- emotion : UN mot parmi — tension, curiosity, danger, hope, irony, awe, defiance
- couleur_dominante : UN choix parmi — deep blue, crimson red, emerald green, burnt orange, dark purple, golden yellow

Titre : {titre}

Extrait :
{extrait}"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def openrouter_headers() -> dict:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://dailyplanet.fr",
    }


def llm_vars(titre: str, extrait: str = "") -> dict:
    """Ask LLM to generate image prompt variables from article title + extract."""
    mode = os.getenv("MODE", "local")
    prompt = VARS_PROMPT.format(titre=titre, extrait=extrait[:800] if extrait else "(non disponible)")

    if mode == "local":
        import subprocess
        cli_path = os.getenv("CLAUDE_CLI_PATH", "claude")
        result = subprocess.run(
            [cli_path, "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI erreur : {result.stderr[:300]}")
        content = result.stdout.strip()
    else:
        payload = {
            "model": os.getenv("CLAUDE_MODEL", "anthropic/claude-sonnet-4-6"),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300,
        }
        r = requests.post(
            f"{OPENROUTER_URL}/chat/completions",
            headers=openrouter_headers(),
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown code blocks if present
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Variables image non parseable : {e}\nContenu : {content[:300]}")

    required = {"sujet_visuel", "emotion", "couleur_dominante"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Variables manquantes dans la réponse LLM : {missing}")

    return data


def build_image_prompt(vars_dict: dict) -> str:
    return IMAGE_TEMPLATE.format(**vars_dict)


def _is_flux_kontext(model: str) -> bool:
    return model.startswith("flux-kontext")


def call_image_api(prompt: str) -> bytes:
    """
    kie.ai image generation — modèle lu depuis KIE_AI_MODEL (.env).
    Deux familles d'endpoints :
      flux-kontext-*          → /flux/kontext/generate  + /flux/kontext/record-info
      tous les autres modèles → /jobs/createTask        + /jobs/recordInfo
    """
    api_key = os.getenv("KIE_AI_API_KEY", "")
    if not api_key:
        raise ValueError("KIE_AI_API_KEY manquante dans .env")

    model = os.getenv("KIE_AI_MODEL", "gpt-image-2-text-to-image")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # ── Flux Kontext ──────────────────────────────────────────────────────────
    if _is_flux_kontext(model):
        payload = {
            "prompt": prompt,
            "model": model,
            "aspectRatio": "16:9",
            "outputFormat": "png",
            "promptUpsampling": False,
            "enableTranslation": False,
            "safetyTolerance": 2,
        }
        r = requests.post(
            f"{KIE_AI_BASE}/flux/kontext/generate",
            headers=headers, json=payload, timeout=30,
        )
        r.raise_for_status()
        task_id = r.json()["data"]["taskId"]

        for _ in range(60):
            time.sleep(5)
            r = requests.get(
                f"{KIE_AI_BASE}/flux/kontext/record-info?taskId={task_id}",
                headers=headers, timeout=15,
            )
            r.raise_for_status()
            data = r.json()["data"]
            flag = data.get("successFlag", 0)
            if flag == 1:
                image_url = data["response"]["resultImageUrl"]
                break
            elif flag in (2, 3):
                raise RuntimeError(f"kie.ai flux-kontext : échec (successFlag={flag})")
        else:
            raise TimeoutError("Timeout — kie.ai flux-kontext > 5 min")

    # ── Market models (gpt-image-2-text-to-image, nano-banana-pro, etc.) ─────
    else:
        payload = {
            "model": model,
            "input": {
                "prompt": prompt,
                "aspect_ratio": "16:9",
                "output_format": "png",
            },
        }
        r = requests.post(
            f"{KIE_AI_BASE}/jobs/createTask",
            headers=headers, json=payload, timeout=30,
        )
        r.raise_for_status()
        task_id = r.json()["data"]["taskId"]

        for _ in range(60):
            time.sleep(5)
            r = requests.get(
                f"{KIE_AI_BASE}/jobs/recordInfo?taskId={task_id}",
                headers=headers, timeout=15,
            )
            r.raise_for_status()
            data = r.json()["data"]
            state = data.get("state", "")
            if state == "success":
                result = json.loads(data["resultJson"])
                image_url = result["resultUrls"][0]
                break
            elif state in ("fail", "failed", "error"):
                raise RuntimeError(
                    f"kie.ai market : échec (state={state}, msg={data.get('failMsg')})"
                )
        else:
            raise TimeoutError("Timeout — kie.ai market model > 5 min")

    # ── Download ──────────────────────────────────────────────────────────────
    img_r = requests.get(image_url, timeout=60)
    img_r.raise_for_status()
    return img_r.content


def save_as_webp(image_bytes: bytes, slug: str) -> str:
    """Convert PNG bytes → WebP, save to assets/images/ (og:image only). Returns relative path."""
    if Image is None:
        raise RuntimeError("Pillow non installé. Lance : pip3 install Pillow")

    os.makedirs(ASSETS_IMAGES, exist_ok=True)
    dest_path = os.path.join(ASSETS_IMAGES, f"{slug}.webp")

    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.save(dest_path, "WEBP", quality=88, method=6)

    return f"images/{slug}.webp"


def save_as_avif(image_bytes: bytes, slug: str) -> tuple:
    """Convert PNG bytes → AVIF, save to static/images/ (display). Returns (url, width, height)."""
    if Image is None:
        raise RuntimeError("Pillow non installé. Lance : pip3 install Pillow")

    os.makedirs(STATIC_IMAGES, exist_ok=True)
    dest_path = os.path.join(STATIC_IMAGES, f"{slug}.avif")

    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.save(dest_path, "AVIF", quality=80)

    return f"/images/{slug}.avif", img.width, img.height


def update_db(article_id: int, image_path: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE articles SET image_locale = ?, statut = 'image_ok' WHERE id = ?",
        (image_path, article_id),
    )
    conn.commit()
    conn.close()


# ── Interface pipeline ────────────────────────────────────────────────────────

def run(context: dict) -> dict:
    article_id      = context.get("article_id")
    article_titre   = context.get("article_titre", "")
    article_slug    = context.get("article_slug", "")
    article_contenu = context.get("article_contenu", "")

    if not article_titre:
        raise ValueError("Aucun article_titre dans le contexte. Étape 3 a-t-elle tourné ?")

    vars_dict    = llm_vars(article_titre, article_contenu)
    image_prompt = build_image_prompt(vars_dict)
    image_bytes  = call_image_api(image_prompt)

    webp_path                   = save_as_webp(image_bytes, article_slug)
    avif_url, img_w, img_h      = save_as_avif(image_bytes, article_slug)

    if article_id:
        update_db(article_id, webp_path)

    return {
        "article_image":         webp_path,
        "article_image_display": avif_url,
        "article_image_width":   img_w,
        "article_image_height":  img_h,
        "_cost_image_usd":       float(os.getenv("PRICE_IMAGE_USD", "0.04")),
    }


# ── Test direct ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    TITRE_TEST = "Google injecte 40 milliards dans Anthropic et s'offre un pied dans les deux camps"
    SLUG_TEST  = "test-image-google-anthropic"

    print(f"\nMode  : {os.getenv('MODE', 'local')}")
    print(f"Titre : {TITRE_TEST}\n")

    print("1/3 — Génération des variables visuelles...", flush=True)
    vars_dict = llm_vars(TITRE_TEST)
    print(f"      sujet_visuel      : {vars_dict['sujet_visuel']}")
    print(f"      emotion           : {vars_dict['emotion']}")
    print(f"      couleur_dominante : {vars_dict['couleur_dominante']}")

    image_prompt = build_image_prompt(vars_dict)
    print(f"\nPrompt image :\n  {image_prompt}\n")

    print("2/3 — Génération de l'image (kie.ai flux-kontext-max)...", flush=True)
    image_bytes = call_image_api(image_prompt)
    print(f"      {len(image_bytes) // 1024} Ko reçus")

    print("3/3 — Conversion WebP + sauvegarde...", flush=True)
    image_path = save_as_webp(image_bytes, SLUG_TEST)
    dest = os.path.join(ASSETS_IMAGES, f"{SLUG_TEST}.webp")

    if Image:
        img = Image.open(dest)
        print(f"      Dimensions : {img.size[0]}x{img.size[1]}px")
        print(f"      Format     : {img.format or 'WEBP'}")

    print(f"\n✓ Image sauvegardée : assets/images/{SLUG_TEST}.webp")
    print("  (fichier test — à supprimer manuellement)")
