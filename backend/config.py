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
    nrel_api_key: str = ""  # free key at https://developer.nlr.gov/signup/

    # OAuth providers — client ID + secret from each provider's developer console
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    apple_client_id: str = ""  # Apple Service ID (com.yourapp.web)
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_private_key: str = ""  # PEM contents of AuthKey_XXXXXXXX.p8

    # Magic link email — Resend API key (free tier: 100 emails/day)
    resend_api_key: str = ""
    magic_link_from_email: str = "noreply@flowshift.app"

    # Session config
    session_secret_key: str = "change-me-in-production"  # for itsdangerous signing
    session_max_age_days: int = 30
    frontend_url: str = "http://localhost:3000"  # used to build magic link redirect URLs


settings = Settings()
