from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str
    storage_path: str = "/storage"
    ollama_url: str = "http://ollama:11434"

    # Precios en USD por minuto
    price_transcription: float = 0.10
    price_translation: float = 0.18
    price_subtitles: float = 0.18
    price_dubbing: float = 0.50

    class Config:
        env_file = ".env"

settings = Settings()
