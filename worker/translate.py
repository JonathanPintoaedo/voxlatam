import os
import requests
import logging

log = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
MODEL      = "llama3.2:3b"

SYSTEM_PROMPT = """Eres un traductor profesional especializado en contenido para 
creadores latinoamericanos de YouTube y podcasts. 

Reglas:
- Traduce SOLO el texto, sin explicaciones ni comentarios
- Usa español neutro latinoamericano (no España)
- Preserva el tono, energía y jerga del original
- Mantén exactamente los separadores ---
- Si el texto ya está en el idioma destino, devuélvelo igual
- Responde SOLO con el texto traducido"""

def translate_segments(segments: list, source: str = "auto", target: str = "es") -> list:
    """
    Traduce segmentos en batches de 10 para eficiencia.
    Preserva timestamps originales.
    """
    if not segments:
        return segments

    # Si ya está en español, retornar igual
    if source == "es" and target == "es":
        return segments

    translated = []
    batch_size = 5

    for i in range(0, len(segments), batch_size):
        batch = segments[i : i + batch_size]
        texts = [s["text"].strip() for s in batch]
        combined = "\n---\n".join(texts)

        prompt = f"Traduce del {_lang_name(source)} al {_lang_name(target)}:\n\n{combined}"

        try:
            response = _ollama_generate(prompt)
            parts = response.split("\n---\n")

            for j, seg in enumerate(batch):
                translated_text = parts[j].strip() if j < len(parts) else seg["text"]
                translated.append({**seg, "text": translated_text})

            log.info(f"Traducidos segmentos {i+1}–{i+len(batch)}/{len(segments)}")

        except Exception as e:
            log.warning(f"Error traduciendo batch {i}: {e}. Usando texto original.")
            translated.extend(batch)

    return translated


def _ollama_generate(prompt: str) -> str:
    # Primer intento con timeout largo
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":   MODEL,
                "prompt":  prompt,
                "system":  SYSTEM_PROMPT,
                "stream":  False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 1024,
                    "num_ctx": 2048       # Reducir contexto = más rápido
                }
            },
            timeout=600   # 10 minutos
        )
        r.raise_for_status()
        return r.json()["response"]
    except Exception as e:
        log.warning(f"Ollama falló: {e}")
        raise


def _lang_name(code: str) -> str:
    names = {
        "en": "inglés", "es": "español", "pt": "portugués",
        "fr": "francés", "de": "alemán", "it": "italiano",
        "ja": "japonés", "ko": "coreano", "zh": "chino",
        "auto": "idioma detectado automáticamente"
    }
    return names.get(code, code)
