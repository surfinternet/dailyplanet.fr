"""
Writes and updates a per-run JSON file in logs/runs/.
Called by main_pipeline.py and run_finish.py.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

RUNS_DIR = Path(os.getenv("LOGS_DIR", "/app/logs")) / "runs"


def _path(run_id: str) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return RUNS_DIR / f"{run_id}.json"


def _read(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _write(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def init(run_id: str, steps_meta: list) -> None:
    data = {
        "run_id": run_id,
        "started_at": _now(),
        "finished_at": None,
        "status": "running",
        "git_note": None,
        "article_titre": None,
        "article_slug": None,
        "steps": [
            {
                "name": s[0],
                "label": s[1],
                "status": "pending",
                "started_at": None,
                "duration_s": None,
                "error": None,
            }
            for s in steps_meta
        ],
        "costs": {
            "perplexity_usd": 0.0,
            "claude_usd": 0.0,
            "image_usd": 0.0,
            "total_usd": 0.0,
        },
    }
    _write(_path(run_id), data)


def step_start(run_id: str, step_name: str) -> None:
    p = _path(run_id)
    data = _read(p)
    for s in data["steps"]:
        if s["name"] == step_name:
            s["status"] = "running"
            s["started_at"] = _now()
    _write(p, data)


def step_ok(run_id: str, step_name: str, duration_s: float) -> None:
    p = _path(run_id)
    data = _read(p)
    for s in data["steps"]:
        if s["name"] == step_name:
            s["status"] = "ok"
            s["duration_s"] = round(duration_s, 2)
    _write(p, data)


def step_fail(run_id: str, step_name: str, duration_s: float, error: str) -> None:
    p = _path(run_id)
    data = _read(p)
    for s in data["steps"]:
        if s["name"] == step_name:
            s["status"] = "failed"
            s["duration_s"] = round(duration_s, 2)
            s["error"] = error
    _write(p, data)


def update_costs(
    run_id: str,
    perplexity: float = 0.0,
    claude: float = 0.0,
    image: float = 0.0,
) -> None:
    p = _path(run_id)
    data = _read(p)
    data["costs"]["perplexity_usd"] = round(perplexity, 6)
    data["costs"]["claude_usd"]     = round(claude, 6)
    data["costs"]["image_usd"]      = round(image, 6)
    data["costs"]["total_usd"]      = round(perplexity + claude + image, 6)
    _write(p, data)


def finish(
    run_id: str,
    status: str,
    git_note: str = None,
    article_titre: str = None,
    article_slug: str = None,
) -> None:
    p = _path(run_id)
    data = _read(p)
    data["status"]      = status
    data["finished_at"] = _now()
    if git_note:
        data["git_note"] = git_note
    if article_titre:
        data["article_titre"] = article_titre
    if article_slug:
        data["article_slug"] = article_slug
    _write(p, data)
