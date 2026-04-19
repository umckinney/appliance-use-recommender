from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./flowshift.db"
    secret_key: str = "change-me-in-production"
    env: str = "development"

    # SolarEdge
    solaredge_site_id: str = ""
    solaredge_api_key: str = ""

    # External APIs
    bpa_api_base_url: str = "https://transmission.bpa.gov/business/operations/Wind/baltwg.txt"
    eia_api_key: str = ""


settings = Settings()
