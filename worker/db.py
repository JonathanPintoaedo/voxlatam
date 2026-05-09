import os
import logging
import requests
from pathlib import Path
from sqlalchemy import create_engine, text

log = logging.getLogger(__name__)

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        db_url = os.getenv("DATABASE_URL", "")
        _engine = create_engine(db_url)
    return _engine


def update_job_status(job_id: str, status: str, progress: int, error: str = None) -> None:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("""
                UPDATE jobs
                SET status = :status,
                    progress = :progress,
                    error_msg = :error,
                    updated_at = NOW()
                WHERE id = :job_id
            """), {"status": status, "progress": progress, "error": error, "job_id": job_id})
            conn.commit()
    except Exception as e:
        log.error(f"Error actualizando job {job_id}: {e}")


def notify_telegram(telegram_user_id: str, job_id: str, files: dict) -> None:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token or not telegram_user_id:
        return

    api_url = f"https://api.telegram.org/bot{bot_token}"

    try:
        msg = f"✅ *¡Tu archivo está listo!*\n\n`{job_id[:8]}...`\n\n"
        if files.get("srt"):       msg += "📄 Transcripción SRT\n"
        if files.get("txt"):       msg += "📝 Texto completo\n"
        if files.get("subtitled"): msg += "🎬 Video con subtítulos\n"
        if files.get("dubbed"):    msg += "🗣 Video doblado\n"
        msg += "\nEnviando archivos... 👇"

        requests.post(f"{api_url}/sendMessage", json={
            "chat_id": telegram_user_id,
            "text": msg,
            "parse_mode": "Markdown"
        }, timeout=10)

        file_map = {
            "txt":       ("sendDocument", "document"),
            "srt":       ("sendDocument", "document"),
            "subtitled": ("sendVideo",    "video"),
            "dubbed":    ("sendVideo",    "video"),
        }

        for key, (method, field) in file_map.items():
            path = files.get(key)
            if path and Path(path).exists():
                with open(path, "rb") as f:
                    r = requests.post(
                        f"{api_url}/{method}",
                        data={"chat_id": telegram_user_id},
                        files={field: f},
                        timeout=180
                    )
                if r.status_code == 200:
                    log.info(f"Archivo {key} enviado a {telegram_user_id}")
                else:
                    log.warning(f"Error enviando {key}: {r.text[:200]}")

    except Exception as e:
        log.error(f"Error notificando Telegram: {e}")


def deduct_credits(job_id: str, cost_usd: float, files: dict) -> None:
    try:
        with get_engine().connect() as conn:
            result = conn.execute(
                text("SELECT user_id FROM jobs WHERE id = :job_id"),
                {"job_id": job_id}
            ).fetchone()

            telegram_id = None

            if result and result[0]:
                conn.execute(text("""
                    UPDATE users
                    SET credits_usd = credits_usd - :cost
                    WHERE id = :user_id AND credits_usd >= :cost
                """), {"cost": cost_usd, "user_id": str(result[0])})

                user_result = conn.execute(
                    text("SELECT telegram_id FROM users WHERE id = :uid"),
                    {"uid": str(result[0])}
                ).fetchone()
                if user_result:
                    telegram_id = user_result[0]

            conn.execute(text("""
                UPDATE jobs SET
                    status = 'completed',
                    progress = 100,
                    cost_usd = :cost,
                    file_srt = :srt,
                    file_txt = :txt,
                    file_subtitled = :subtitled,
                    file_dubbed = :dubbed,
                    updated_at = NOW()
                WHERE id = :job_id
            """), {
                "cost":      cost_usd,
                "srt":       files.get("srt"),
                "txt":       files.get("txt"),
                "subtitled": files.get("subtitled"),
                "dubbed":    files.get("dubbed"),
                "job_id":    job_id
            })
            conn.commit()
            log.info(f"Job {job_id} completado. Costo: ${cost_usd:.4f}")

        if telegram_id:
            notify_telegram(telegram_id, job_id, files)

    except Exception as e:
        log.error(f"Error en deduct_credits {job_id}: {e}")
