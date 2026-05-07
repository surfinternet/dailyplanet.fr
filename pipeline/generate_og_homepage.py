"""
Génère l'image Open Graph de la homepage de Daily Planet FR.

Usage :
  cd /path/to/dailyplanet.fr
  python pipeline/generate_og_homepage.py

Sortie :
  assets/images/og-magazine-ia-tech.webp  ← Hugo la traite pour l'og:image
  static/images/og-magazine-ia-tech.avif  ← version display directe

Après génération : committer les deux fichiers puis pousser sur main.
"""

import os
import sys
import json
import time
import requests
from io import BytesIO

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

ROOT = os.path.join(os.path.dirname(__file__), "..")
ASSETS_IMAGES = os.path.join(ROOT, "assets", "images")
STATIC_IMAGES = os.path.join(ROOT, "static", "images")
KIE_AI_BASE   = "https://api.kie.ai/api/v1"

# ── Slug SEO ──────────────────────────────────────────────────────────────────
SLUG = "og-magazine-ia-tech"

# ── Prompt ────────────────────────────────────────────────────────────────────
SUJET_VISUEL = (
    "A dramatic futuristic editorial newsroom. A lone French journalist stands before "
    "a towering wall of glowing screens displaying AI headlines and breaking tech news. "
    "Holographic neural networks and circuit diagrams float in the air. "
    "Bold 'DAILY PLANET' masthead on the wall. Logos of OpenAI, Google, Anthropic, "
    "Mistral visible as glowing signs and badges throughout the scene. "
    "Newspaper printing presses merge with server racks in the background. "
    "A sense of urgency — the future is happening right now."
)
EMOTION          = "awe"
COULEUR_DOMINANTE = "crimson red"

IMAGE_TEMPLATE = (
    "Comic book illustration, editorial style. {sujet_visuel}. "
    "Bold black ink outlines, flat {couleur_dominante} color palette with complementary "
    "accent tones, subtle halftone dot texture in shadows and midtones. "
    "Dynamic composition with strong diagonal lines. {emotion} mood. "
    "1970s Marvel Comics cover aesthetic, Jack Kirby influence. "
    "Company logos and brand marks rendered in comics style are encouraged — stylized, bold, "
    "integrated into the scene as background elements, signs, or props. "
    "No speech bubbles, no watermarks. "
    "High contrast, professional editorial quality."
)


# ── Helpers (copie de 4_generation_image.py) ──────────────────────────────────

def _is_flux_kontext(model: str) -> bool:
    return model.startswith("flux-kontext")


def call_image_api(prompt: str) -> bytes:
    api_key = os.getenv("KIE_AI_API_KEY", "")
    if not api_key:
        raise ValueError("KIE_AI_API_KEY manquante dans .env")

    model   = os.getenv("KIE_AI_MODEL", "gpt-image-2-text-to-image")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    if _is_flux_kontext(model):
        payload = {
            "prompt": prompt, "model": model,
            "aspectRatio": "16:9", "outputFormat": "png",
            "promptUpsampling": False, "enableTranslation": False, "safetyTolerance": 2,
        }
        r = requests.post(f"{KIE_AI_BASE}/flux/kontext/generate", headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        task_id = r.json()["data"]["taskId"]
        for _ in range(60):
            time.sleep(5)
            r = requests.get(f"{KIE_AI_BASE}/flux/kontext/record-info?taskId={task_id}", headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()["data"]
            if data.get("successFlag") == 1:
                image_url = data["response"]["resultImageUrl"]
                break
            elif data.get("successFlag") in (2, 3):
                raise RuntimeError("kie.ai flux-kontext : échec")
        else:
            raise TimeoutError("Timeout kie.ai > 5 min")
    else:
        payload = {"model": model, "input": {"prompt": prompt, "aspect_ratio": "16:9", "output_format": "png"}}
        r = requests.post(f"{KIE_AI_BASE}/jobs/createTask", headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        task_id = r.json()["data"]["taskId"]
        for _ in range(60):
            time.sleep(5)
            r = requests.get(f"{KIE_AI_BASE}/jobs/recordInfo?taskId={task_id}", headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()["data"]
            state = data.get("state", "")
            if state == "success":
                image_url = json.loads(data["resultJson"])["resultUrls"][0]
                break
            elif state in ("fail", "failed", "error"):
                raise RuntimeError(f"kie.ai : échec state={state}")
        else:
            raise TimeoutError("Timeout kie.ai > 5 min")

    img_r = requests.get(image_url, timeout=60)
    img_r.raise_for_status()
    return img_r.content


def save_as_webp(image_bytes: bytes, slug: str) -> str:
    if Image is None:
        raise RuntimeError("Pillow non installé : pip install Pillow")
    os.makedirs(ASSETS_IMAGES, exist_ok=True)
    dest = os.path.join(ASSETS_IMAGES, f"{slug}.webp")
    Image.open(BytesIO(image_bytes)).convert("RGB").save(dest, "WEBP", quality=88, method=6)
    return f"images/{slug}.webp"


def save_as_avif(image_bytes: bytes, slug: str) -> tuple:
    if Image is None:
        raise RuntimeError("Pillow non installé : pip install Pillow")
    os.makedirs(STATIC_IMAGES, exist_ok=True)
    dest = os.path.join(STATIC_IMAGES, f"{slug}.avif")
    img  = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.save(dest, "AVIF", quality=80)
    return f"/images/{slug}.avif", img.width, img.height


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print("  Daily Planet FR — Génération image OG Homepage")
    print(f"  Slug  : {SLUG}")
    print(f"  Model : {os.getenv('KIE_AI_MODEL', 'gpt-image-2-text-to-image')}")
    print(f"{'='*60}\n")

    prompt = IMAGE_TEMPLATE.format(
        sujet_visuel=SUJET_VISUEL,
        emotion=EMOTION,
        couleur_dominante=COULEUR_DOMINANTE,
    )
    print(f"Prompt : {prompt[:100]}...\n")

    print("1/3 — Appel kie.ai...", flush=True)
    image_bytes = call_image_api(prompt)
    print(f"      {len(image_bytes) // 1024} Ko reçus\n")

    print("2/3 — WebP → assets/images/...", flush=True)
    webp_path = save_as_webp(image_bytes, SLUG)
    print(f"      ✓ {webp_path}\n")

    print("3/3 — AVIF → static/images/...", flush=True)
    avif_url, w, h = save_as_avif(image_bytes, SLUG)
    print(f"      ✓ {avif_url} ({w}x{h}px)\n")

    print("="*60)
    print("  ✓ Prochaines étapes :")
    print(f"    git add assets/images/{SLUG}.webp static/images/{SLUG}.avif")
    print("    git commit -m 'Asset: OG image homepage'")
    print("    git checkout main && git merge dev && git push origin main")
    print("="*60)


if __name__ == "__main__":
    main()
