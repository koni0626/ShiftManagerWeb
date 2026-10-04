from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT.parent / ".env", extra="ignore")
    database_url: str
    migration_database_url: str = ""
    allowed_origins: str = "http://127.0.0.1:5194,http://localhost:5194"
    cookie_secure: bool = False
    session_hours: int = 12
    map_tile_url: str = ""
    map_attribution: str = ""
    mapbox_token: str = ""
    geocoding_permanent_enabled: bool = False


settings = Settings()
