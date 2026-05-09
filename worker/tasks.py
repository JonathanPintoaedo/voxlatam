import os
import logging
from celery import Celery
from pathlib import Path

from transcribe import transcribe_audio, save_srt, save_txt
from translate import translate_segments
from tts import synthesize_dubbing
from video import burn_subtitles, merge_audio, extract_audio
from db import update_job_status, deduct_credits

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
app = Celery("voxlatam", broker=REDIS_URL, backend=REDIS_URL)
app.conf.task_queues = {"voxlatam": {}}

log = logging.getLogger(__name__)

# Precios USD/minuto
PRICES = {
    "transcription": 0.10,
    "translation":   0.18,
    "subtitles":     0.18,
    "dubbing":       0.50,
}

@app.task(bind=True, max_retries=2, queue="voxlatam")
def process_job(self, job_id: str, options: dict):
    """
    Pipeline principal de procesamiento de audio/video.

    options = {
        'mode': 'transcription' | 'translation' | 'subtitles' | 'dubbing',
        'lang_source': 'auto' | 'en' | 'es' | ...,
        'lang_target': 'es',
        'input_path': '/storage/JOB_ID/input.mp4',
        'voice_sample': '/storage/JOB_ID/voice.wav'  # opcional
    }
    """
    storage = Path(os.getenv("STORAGE_PATH", "/storage")) / job_id
    mode = options.get("mode", "transcription")

    try:
        # ── 1. Extraer audio ──────────────────────────
        update_job_status(job_id, "extracting", 5)
        audio_path = storage / "audio.wav"
        input_path = Path(options["input_path"])
        extract_audio(input_path, audio_path)
        log.info(f"[{job_id}] Audio extraído: {audio_path}")

        # ── 2. Transcripción con Whisper ──────────────
        update_job_status(job_id, "transcribing", 20)
        segments = transcribe_audio(
            audio_path,
            language=None if options.get("lang_source") == "auto" else options.get("lang_source"),
            word_timestamps=True
        )
        save_srt(segments, storage / "original.srt")
        save_txt(segments, storage / "original.txt")
        log.info(f"[{job_id}] Transcripción completa: {len(segments)} segmentos")

        if mode == "transcription":
            cost = _calculate_cost(segments, "transcription")
            deduct_credits(job_id, cost, {
                "srt": str(storage / "original.srt"),
                "txt": str(storage / "original.txt"),
            })
            return

        # ── 3. Traducción con Mistral ─────────────────
        update_job_status(job_id, "translating", 45)
        translated = translate_segments(
            segments,
            source=options.get("lang_source", "auto"),
            target=options.get("lang_target", "es")
        )
        save_srt(translated, storage / "translated.srt")
        log.info(f"[{job_id}] Traducción completa")

        if mode in ("translation", "subtitles"):
            update_job_status(job_id, "rendering", 75)
            subtitled_path = storage / "subtitled.mp4"
            burn_subtitles(input_path, storage / "translated.srt", subtitled_path)
            cost = _calculate_cost(segments, "subtitles")
            deduct_credits(job_id, cost, {
                "srt": str(storage / "translated.srt"),
                "subtitled": str(subtitled_path),
            })
            return

        # ── 4. Doblaje con Coqui XTTS-v2 ─────────────
        update_job_status(job_id, "dubbing", 65)
        dubbed_audio = synthesize_dubbing(
            translated,
            voice_sample=options.get("voice_sample"),
            target_lang=options.get("lang_target", "es")
        )
        log.info(f"[{job_id}] Doblaje completo")

        # ── 5. Mezclar con video ──────────────────────
        update_job_status(job_id, "rendering", 85)
        dubbed_path = storage / "dubbed.mp4"
        merge_audio(input_path, dubbed_audio, dubbed_path)

        cost = _calculate_cost(segments, "dubbing")
        deduct_credits(job_id, cost, {
            "srt":       str(storage / "original.srt"),
            "txt":       str(storage / "original.txt"),
            "subtitled": str(storage / "subtitled.mp4") if (storage / "subtitled.mp4").exists() else None,
            "dubbed":    str(dubbed_path),
        })
        log.info(f"[{job_id}] ✅ Job completado. Costo: ${cost:.2f}")

    except Exception as e:
        log.error(f"[{job_id}] ❌ Error: {e}", exc_info=True)
        update_job_status(job_id, "failed", 0, error=str(e))
        raise self.retry(exc=e, countdown=30)


def _calculate_cost(segments: list, mode: str) -> float:
    if not segments:
        return 0.0
    total_seconds = segments[-1].get("end", 0)
    total_minutes = total_seconds / 60
    return round(total_minutes * PRICES.get(mode, 0.10), 4)
