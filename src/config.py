"""
E-Commerce Support Agent - Configuration
"""
from pathlib import Path

from pydantic_settings import BaseSettings

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    temperature: float = 0.0

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Storage
    db_path: str = str(ROOT / "data" / "ecommerce.db")

    # Langfuse Observability (optional — set to enable tracing)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    model_config = {"env_file": str(ROOT / ".env"), "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
