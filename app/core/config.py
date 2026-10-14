"""Configuración centralizada; carga .env solo en el servidor."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()

@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    drive_folder_id: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    vector_store_id: str = os.getenv("VECTOR_STORE_ID", "")
    local_admin_key: str = os.getenv("LOCAL_ADMIN_KEY", "")

settings = Settings()
