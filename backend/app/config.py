from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_cloud_project: str | None = None
    google_cloud_location: str = "us-central1"
    google_genai_use_vertexai: bool = False
    gemini_api_key: str | None = None
    firestore_database: str = "(default)"
    local_data_file: str = ".data/agentsphere.json"
    gemini_model: str = "gemini-flash-latest"
    gemini_timeout_seconds: float = 45.0
    gemini_max_retries: int = 2
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=(".env", "backend/.env"), env_file_encoding="utf-8", extra="ignore")


settings = Settings()

