import torch
import torchaudio
import logging
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

_tts_model = None

def get_tts():
    global _tts_model
    if _tts_model is None:
        from TTS.api import TTS
        log.info("Cargando Coqui XTTS-v2...")
        _tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
        _tts_model.to("cuda" if torch.cuda.is_available() else "cpu")
        log.info("✅ XTTS-v2 cargado")
    return _tts_model

def unload_tts():
    global _tts_model
    if _tts_model is not None:
        del _tts_model
        _tts_model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        log.info("XTTS-v2 descargado de VRAM")

def synthesize_dubbing(segments: list, voice_sample: str = None, target_lang: str = "es") -> Path:
    """
    Genera audio doblado sincronizado con los timestamps del SRT.
    Si no hay voice_sample, usa voz predeterminada en español.
    """
    from transcribe import unload_model
    # ⚠️ CRÍTICO: Liberar Whisper de VRAM antes de cargar TTS
    unload_model()

    tts = get_tts()
    temp_dir = Path(tempfile.mkdtemp())
    parts = []  # [(start_seconds, wav_path)]

    # Voz por defecto si no hay sample
    default_speaker = "Claribel Dervla" if not voice_sample else None

    for i, seg in enumerate(segments):
        if not seg["text"].strip():
            continue

        out_wav = temp_dir / f"seg_{i:04d}.wav"
        duration = seg["end"] - seg["start"]

        try:
            if voice_sample and Path(voice_sample).exists():
                tts.tts_to_file(
                    text=seg["text"],
                    speaker_wav=voice_sample,
                    language=target_lang,
                    file_path=str(out_wav),
                )
            else:
                tts.tts_to_file(
                    text=seg["text"],
                    speaker=default_speaker,
                    language=target_lang,
                    file_path=str(out_wav),
                )

            # Ajustar velocidad si el audio no cabe en el tiempo del segmento
            _fit_audio_to_duration(out_wav, duration)
            parts.append((seg["start"], out_wav))

        except Exception as e:
            log.warning(f"Error en segmento {i}: {e}")
            continue

    if not parts:
        raise RuntimeError("No se generó ningún segmento de audio")

    total_duration = segments[-1]["end"] if segments else 0
    output_path = temp_dir / "dubbed_full.wav"
    _concat_with_timing(parts, total_duration, output_path)

    return output_path


def _fit_audio_to_duration(wav_path: Path, target_duration: float, max_speed: float = 1.5) -> None:
    """Acelera el audio si es más largo que el hueco del segmento."""
    try:
        audio, sr = torchaudio.load(str(wav_path))
        actual_duration = audio.shape[1] / sr
        if actual_duration <= 0:
            return
        speed = actual_duration / target_duration
        if speed > max_speed:
            speed = max_speed
        if speed > 1.05:
            # Resample para cambiar velocidad
            new_sr = int(sr * speed)
            resampled = torchaudio.functional.resample(audio, sr, new_sr)
            torchaudio.save(str(wav_path), resampled, sr)
    except Exception as e:
        log.warning(f"No se pudo ajustar duración: {e}")


def _concat_with_timing(parts: list, total_duration: float, output_path: Path) -> None:
    """Concatena segmentos en sus posiciones de tiempo correctas con silencios."""
    import numpy as np
    import soundfile as sf

    sr = 22050
    total_samples = int(total_duration * sr) + sr  # +1 segundo de margen
    full_audio = np.zeros(total_samples, dtype=np.float32)

    for start_sec, wav_path in parts:
        try:
            data, file_sr = sf.read(str(wav_path))
            if len(data.shape) > 1:
                data = data.mean(axis=1)
            if file_sr != sr:
                # Resample simple
                ratio = sr / file_sr
                new_len = int(len(data) * ratio)
                data = np.interp(
                    np.linspace(0, len(data), new_len),
                    np.arange(len(data)),
                    data
                )
            start_sample = int(start_sec * sr)
            end_sample = min(start_sample + len(data), total_samples)
            length = end_sample - start_sample
            full_audio[start_sample:end_sample] = data[:length]
        except Exception as e:
            log.warning(f"Error mezclando segmento {wav_path}: {e}")

    sf.write(str(output_path), full_audio, sr)
