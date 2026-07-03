from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/axxiom_aeo"
    db_schema: str = "aeo"
    supabase_project_ref: str = "cdlssoeqqfrgckpxewhn"
    supabase_db_region: str = ""
    db_password: str = ""

    peec_api_key: str = ""

    citation_provider: str = "geo_aeo"  # geo_aeo | peec | none | auto
    geo_aeo_tracker_url: str = "http://localhost:3000"
    geo_aeo_providers: str = "perplexity,chatgpt,google_ai"
    geo_aeo_concurrency: int = 2
    citation_sample_runs: int = 3

    google_service_account_json: str = ""
    bing_api_key: str = ""
    # Comma-separated override of AI-assistant referrer hosts for GA4 segmentation.
    ai_referrer_hosts: str = ""

    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwks_url: str = ""

    slack_webhook_url: str = ""
    frontend_url: str = "http://localhost:5173"

    environment: str = "development"
    # Explicit opt-in for the local no-auth shortcut (see app.auth.verify_token).
    auth_dev_bypass: bool = False
    secret_key: str = "change-me"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Optional regex for additional allowed origins (e.g. Netlify deploy previews):
    # https://([a-z0-9-]+--)?your-site\.netlify\.app
    cors_origin_regex: str = ""

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

    brand_ids: tuple[str, ...] = (
        "axxiom",
        "ameritex",
        "arizona_es",
        "liftech",
        "motion",
        "quality",
        "evolution",
        "ironhawk",
    )

    claude_model: str = "claude-sonnet-4-6"
    weekly_content_batch_size: int = 5

    # Weekly automated topic discovery (GSC demand + citation gaps + coverage).
    topic_discovery_enabled: bool = True
    topic_discovery_max_per_brand: int = 2
    topic_discovery_max_total: int = 10
    topic_discovery_min_impressions: int = 20

    openai_api_key: str = ""
    openai_image_model: str = "gpt-image-1"
    content_max_images: int = 3
    image_generation_enabled: bool = True
    content_generation_concurrency: int = 3

    @field_validator("supabase_jwt_secret", mode="before")
    @classmethod
    def strip_jwt_secret(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().strip('"').strip("'")
        return value

    @field_validator("database_url", "db_password", mode="before")
    @classmethod
    def strip_quotes(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().strip('"').strip("'")
        return value

    def _pooler_host(self) -> str:
        """Region may be ``ap-northeast-1`` or full pooler prefix ``aws-1-ap-northeast-1``."""
        region = self.supabase_db_region.strip()
        if region.startswith("aws-"):
            return f"{region}.pooler.supabase.com"
        return f"aws-0-{region}.pooler.supabase.com"

    def resolved_database_url(self) -> str:
        """Build pooler URL from DB_PASSWORD (avoids @/# breaking DATABASE_URL)."""
        if self.db_password and self.supabase_db_region:
            encoded = quote_plus(self.db_password)
            ref = self.supabase_project_ref
            host = self._pooler_host()
            return f"postgresql://postgres.{ref}:{encoded}@{host}:5432/postgres"
        return self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        # Always trust the configured frontend URL (Netlify production site).
        if self.frontend_url and self.frontend_url not in origins:
            origins.append(self.frontend_url.rstrip("/"))
        return origins

    def get_wp_password(self, brand_id: str) -> str:
        raw = getattr(self, f"wp_app_password_{brand_id}", "")
        # Application passwords are shown with spaces; strip for Basic auth.
        return raw.replace(" ", "") if isinstance(raw, str) else ""

    def get_wp_username(self, brand_id: str) -> str:
        return getattr(self, f"wp_username_{brand_id}", "admin")

    def wp_publish_configured(self, brand_id: str) -> bool:
        return bool(self.get_wp_password(brand_id).strip())

    def wp_configured_brand_ids(self) -> list[str]:
        return [brand_id for brand_id in self.brand_ids if self.wp_publish_configured(brand_id)]


@lru_cache
def get_settings() -> Settings:
    return Settings()
