import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "MedCare Pharma Supply Chain Control Tower"
    API_V1_STR: str = "/api"
    
    # Database
    DATABASE_URL: str = "sqlite:///./medcare_pharma.db"
    
    # Optional MySQL configuration if DATABASE_URL is not set
    MYSQL_HOST: Optional[str] = None
    MYSQL_PORT: Optional[int] = None
    MYSQL_USER: Optional[str] = None
    MYSQL_PASSWORD: Optional[str] = None
    MYSQL_DATABASE: Optional[str] = None

    # LLM Settings — Ollama Cloud (https://ollama.com)
    OLLAMA_HOST: str = "https://ollama.com"
    OLLAMA_MODEL:str = "llama3.2"
    OLLAMA_API_KEY: Optional[str] = None  # from https://ollama.com/settings/keys

    # API Base URL
    API_BASE_URL: str = "http://localhost:8000"

    # Business defaults
    DEFAULT_SERVICE_LEVEL: float = 0.95
    DEFAULT_Z_SCORE: float = 1.96  # Corresponds to 95% service level
    DEFAULT_REVIEW_PERIOD_DAYS: int = 7
    DEFAULT_LEAD_TIME_DAYS: int = 5
    
    # Expiry Risk Thresholds
    EXPIRY_WARNING_DAYS: int = 90
    EXPIRY_CRITICAL_DAYS: int = 30
    EXPIRY_EXTREME_DAYS: int = 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_db_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if self.MYSQL_HOST and self.MYSQL_USER and self.MYSQL_DATABASE:
            port = self.MYSQL_PORT or 3306
            pwd = f":{self.MYSQL_PASSWORD}" if self.MYSQL_PASSWORD else ""
            return f"mysql+pymysql://{self.MYSQL_USER}{pwd}@{self.MYSQL_HOST}:{port}/{self.MYSQL_DATABASE}"
        return url

settings = Settings()
# Ensure models/ and data/ folders exist
os.makedirs("models", exist_ok=True)
os.makedirs("data/raw", exist_ok=True)
os.makedirs("data/processed", exist_ok=True)
os.makedirs("data/synthetic", exist_ok=True)
