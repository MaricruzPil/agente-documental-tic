"""Configuración centralizada; carga .env solo en el servidor."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()

def _is_true(value: str) -> bool:
    return value.strip().lower() == "true"

def _timeout(value: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 30.0
    return parsed if 1.0 <= parsed <= 120.0 else 30.0

@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "local").strip().lower()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    drive_folder_id: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    vector_store_id: str = os.getenv("VECTOR_STORE_ID", "")
    local_admin_key: str = os.getenv("LOCAL_ADMIN_KEY", "")
    openai_timeout_seconds: float = _timeout(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
    sync_enabled: bool = (
        app_env == "local" and _is_true(os.getenv("SYNC_ENABLED", "true"))
    )
    ask_enabled: bool = (
        app_env == "local"
        or (app_env == "production" and _is_true(os.getenv("PUBLIC_ASK_ENABLED", "false")))
    )

settings = Settings()
