import asyncio
import logging
import tempfile
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

# Voces en español disponibles en edge-tts
VOICES = {
    "es": "es-CL-CatalinaNeural",   # Español Chile
    "en": "en-US-JennyNeural",
    "pt": "pt-BR-FranciscaNeural",
}

def synthesize_dubbing(segments: list, voice_sample: str = None, target_lang: str = "es") -> Path:
    """Genera audio doblado usando edge-tts (Microsoft TTS - gratis, sin GPU)."""
    voice = VOICES.get(target_lang, "es-CL-CatalinaNeural")
    temp_dir = Path(tempfile.mkdtemp())
    parts = []

    for i, seg in enumerate(segments):
        text = seg["text"].strip()
        if not text:
            continue
        out_mp3 = temp_dir / f"seg_{i:04d}.mp3"
        try:
            asyncio.run(_generate_segment(text, voice, str(out_mp3)))
            if out_mp3.exists():
                parts.append((seg["start"], out_mp3))
        except Exception as e:
            log.warning(f"Error en segmento {i}: {e}")

    if not parts:
        raise RuntimeError("No se generó audio")

    output_path = temp_dir / "dubbed_full.mp3"
    _concat_segments(parts, segments[-1]["end"] if segments else 0, output_path)
    return output_path


async def _generate_segment(text: str, voice: str, output: str) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output)


def _concat_segments(parts: list, total_duration: float, output_path: Path) -> None:
    """Concatena segmentos con silencios usando ffmpeg."""
    temp_dir = output_path.parent
    filter_parts = []
    inputs = []

    for i, (start_sec, mp3_path) in enumerate(parts):
        inputs.extend(["-i", str(mp3_path)])
        filter_parts.append(f"[{i}]adelay={int(start_sec*1000)}|{int(start_sec*1000)}[a{i}]")

    if not filter_parts:
        return

    mix_inputs = "".join(f"[a{i}]" for i in range(len(parts)))
    filter_complex = ";".join(filter_parts) + f";{mix_inputs}amix=inputs={len(parts)}:duration=longest[out]"

    cmd = ["ffmpeg"] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-y", str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error: {result.stderr.decode()[:200]}")
