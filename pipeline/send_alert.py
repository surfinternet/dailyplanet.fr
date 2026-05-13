"""
Sends an email alert on pipeline failure.
Usage: python pipeline/send_alert.py RUN_ID
Requires SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_EMAIL in .env
"""
import sys
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))


def send_failure_email(run_id: str) -> None:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    alert_to  = os.getenv("ALERT_EMAIL", "")

    if not all([smtp_host, smtp_user, smtp_pass, alert_to]):
        print("[alert] Email non configuré — ajouter SMTP_HOST/SMTP_USER/SMTP_PASS/ALERT_EMAIL dans .env")
        return

    logs_dir = os.getenv("LOGS_DIR", "/app/logs")
    run_file = Path(logs_dir) / "runs" / f"{run_id}.json"
    run_data = {}
    if run_file.exists():
        with open(run_file) as f:
            run_data = json.load(f)

    failed_step = next(
        (s for s in run_data.get("steps", []) if s["status"] == "failed"),
        None,
    )

    subject = f"[Daily Planet] Pipeline ÉCHOUÉ — {run_id}"

    lines = [
        "Le pipeline Daily Planet FR a échoué.",
        "",
        f"Run ID    : {run_id}",
        f"Démarré   : {run_data.get('started_at', 'inconnu')}",
        f"Terminé   : {run_data.get('finished_at', 'inconnu')}",
        "",
    ]

    if failed_step:
        lines += [
            f"Étape en échec : {failed_step.get('label', failed_step.get('name'))}",
            f"Durée          : {failed_step.get('duration_s', '?')}s",
            "",
            "Erreur :",
            "─" * 60,
            (failed_step.get("error") or "(pas de détail)"),
            "─" * 60,
        ]

    lines += [
        "",
        f"Voir le dashboard : http://{os.getenv('VPS_HOST', 'votre-vps')}:8080",
    ]

    body = "\n".join(lines)
    msg = MIMEMultipart()
    msg["From"]    = smtp_user
    msg["To"]      = alert_to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [alert_to], msg.as_string())
        print(f"[alert] Email envoyé à {alert_to}")
    except Exception as e:
        print(f"[alert] Échec envoi email : {e}")


if __name__ == "__main__":
    run_id = sys.argv[1] if len(sys.argv) > 1 else os.getenv("RUN_ID", "unknown")
    send_failure_email(run_id)
