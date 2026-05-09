import logging
import tempfile
import numpy as np
import soundfile as sf
from pathlib import Path

log = logging.getLogger(__name__)

_pipeline = None

def get_tts():
    global _pipeline
    if _pipeline is None:
        from kokoro import KPipeline
        log.info("Cargando Kokoro TTS...")
        _pipeline = KPipeline(lang_code='e')  # español
        log.info("✅ Kokoro TTS cargado")
    return _pipeline

def synthesize_dubbing(segments: list, voice_sample: str = None, target_lang: str = "es") -> Path:
    pipeline = get_tts()
    temp_dir = Path(tempfile.mkdtemp())
    sr = 24000
    parts = []

    for i, seg in enumerate(segments):
        text = seg["text"].strip()
        if not text:
            continue
        try:
            generator = pipeline(text, voice='af_heart', speed=1.0)
            audio_chunks = []
            for _, _, audio in generator:
                audio_chunks.append(audio)
            if audio_chunks:
                audio = np.concatenate(audio_chunks)
                out_wav = temp_dir / f"seg_{i:04d}.wav"
                sf.write(str(out_wav), audio, sr)
                parts.append((seg["start"], out_wav))
        except Exception as e:
            log.warning(f"Error en segmento {i}: {e}")

    if not parts:
        raise RuntimeError("No se generó audio")

    total_duration = segments[-1]["end"] if segments else 0
    total_samples = int(total_duration * sr) + sr
    full_audio = np.zeros(total_samples, dtype=np.float32)

    for start_sec, wav_path in parts:
        try:
            data, _ = sf.read(str(wav_path))
            start_sample = int(start_sec * sr)
            end_sample = min(start_sample + len(data), total_samples)
            full_audio[start_sample:end_sample] = data[:end_sample - start_sample]
        except Exception as e:
            log.warning(f"Error mezclando segmento: {e}")

    output_path = temp_dir / "dubbed_full.wav"
    sf.write(str(output_path), full_audio, sr)
    return output_path
