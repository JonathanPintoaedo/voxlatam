import torch
import logging
from pathlib import Path
from faster_whisper import WhisperModel

log = logging.getLogger(__name__)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE = "int8"
log.info(f"Whisper usará: {DEVICE.upper()} / {COMPUTE}")

_model = None

def get_model():
    global _model
    if _model is None:
        log.info("Cargando faster-whisper large-v3...")
        _model = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=8)
        log.info("✅ Whisper cargado")
    return _model

def unload_model():
    global _model
    if _model is not None:
        del _model
        _model = None
        if DEVICE == "cuda":
            torch.cuda.empty_cache()
        log.info("Whisper descargado de VRAM")

def transcribe_audio(audio_path: Path, language: str = None, word_timestamps: bool = True) -> list:
    model = get_model()
    segments_gen, info = model.transcribe(
        str(audio_path),
        language=language,
        word_timestamps=word_timestamps,
        vad_filter=True,  # filtra silencios automáticamente
    )
    log.info(f"Idioma detectado: {info.language} ({info.language_probability:.0%})")

    segments = []
    for seg in segments_gen:
        segments.append({
            "start": seg.start,
            "end":   seg.end,
            "text":  seg.text,
            "words": [{"start": w.start, "end": w.end, "word": w.word}
                      for w in (seg.words or [])]
        })
    return segments

def save_srt(segments: list, output_path: Path) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start = _fmt(seg["start"])
            end   = _fmt(seg["end"])
            f.write(f"{i}\n{start} --> {end}\n{seg['text'].strip()}\n\n")

def save_txt(segments: list, output_path: Path) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(seg["text"].strip() + "\n")

def _fmt(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sc = int(s % 60)
    ms = int((s % 1) * 1000)
    return f"{h:02d}:{m:02d}:{sc:02d},{ms:03d}"