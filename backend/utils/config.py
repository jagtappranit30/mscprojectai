import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    GROQ_API_KEY: str
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_JWT_SECRET: Optional[str] = None
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    APP_NAME: str = "SME Productivity Assessment Platform"
    RENDER_EXTERNAL_URL: str = "http://localhost:8000"

    # Support loading from .env in project root
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate settings
try:
    settings = Settings()
except Exception:
    # Fallback to placeholders if .env is missing or invalid (e.g. during build/tests)
    class FallbackSettings:
        GROQ_API_KEY = os.getenv("GROQ_API_KEY", "placeholder")
        SUPABASE_URL = os.getenv("SUPABASE_URL", "https://placeholder.supabase.co")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY", "placeholder")
        SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "placeholder")
        ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
        DEBUG = os.getenv("DEBUG", "true").lower() == "true"
        APP_NAME = os.getenv("APP_NAME", "SME Productivity Assessment Platform")
        RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000")
    settings = FallbackSettings()
