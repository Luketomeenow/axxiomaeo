from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/axxiom_aeo"

    peec_api_key: str = ""
    google_service_account_json: str = ""
    bing_api_key: str = ""

    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwks_url: str = ""

    slack_webhook_url: str = ""
    frontend_url: str = "http://localhost:5173"

    environment: str = "development"
    secret_key: str = "change-me"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    wp_app_password_axxiom: str = ""
    wp_app_password_ameritex: str = ""
    wp_app_password_arizona_es: str = ""
    wp_app_password_liftech: str = ""
    wp_app_password_motion: str = ""
    wp_app_password_quality: str = ""
    wp_app_password_evolution: str = ""
    wp_app_password_ironhawk: str = ""

    wp_username_axxiom: str = "admin"
    wp_username_ameritex: str = "admin"
    wp_username_arizona_es: str = "admin"
    wp_username_liftech: str = "admin"
    wp_username_motion: str = "admin"
    wp_username_quality: str = "admin"
    wp_username_evolution: str = "admin"
    wp_username_ironhawk: str = "admin"

    claude_model: str = "claude-sonnet-4-20250514"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def get_wp_password(self, brand_id: str) -> str:
        return getattr(self, f"wp_app_password_{brand_id}", "")

    def get_wp_username(self, brand_id: str) -> str:
        return getattr(self, f"wp_username_{brand_id}", "admin")


@lru_cache
def get_settings() -> Settings:
    return Settings()
