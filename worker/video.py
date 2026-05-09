import subprocess
import logging
from pathlib import Path

log = logging.getLogger(__name__)

def extract_audio(input_path: Path, output_wav: Path) -> None:
    """Extrae audio de video y lo convierte a WAV mono 16kHz (requerido por Whisper)."""
    _run([
        "ffmpeg", "-i", str(input_path),
        "-ac", "1",       # mono
        "-ar", "16000",   # 16 kHz
        "-y", str(output_wav)
    ])
    log.info(f"Audio extraído: {output_wav}")


def burn_subtitles(video_path: Path, srt_path: Path, output_path: Path) -> None:
    """Quema subtítulos directamente en el video (hardcoded subtitles)."""
    style = "FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Bold=1"
    _run([
        "ffmpeg", "-i", str(video_path),
        "-vf", f"subtitles={srt_path}:force_style='{style}'",
        "-c:a", "copy",
        "-y", str(output_path)
    ])
    log.info(f"Subtítulos quemados: {output_path}")


def merge_audio(video_path: Path, dubbed_audio: Path, output_path: Path, original_vol: float = 0.08) -> None:
    """
    Mezcla el audio doblado con el video.
    Baja el audio original al 8% (efectos de sonido) y sube el doblaje al 100%.
    """
    _run([
        "ffmpeg",
        "-i", str(video_path),
        "-i", str(dubbed_audio),
        "-filter_complex",
        f"[0:a]volume={original_vol}[orig];[1:a]volume=1.0[dub];[orig][dub]amix=inputs=2:duration=first[out]",
        "-map", "0:v",
        "-map", "[out]",
        "-c:v", "copy",
        "-shortest",
        "-y", str(output_path)
    ])
    log.info(f"Audio doblado mezclado: {output_path}")


def get_duration_seconds(file_path: Path) -> float:
    """Obtiene la duración de un archivo de audio/video en segundos."""
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 0.0


def _run(cmd: list) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error:\n{result.stderr}")
