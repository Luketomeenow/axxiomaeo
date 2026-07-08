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

    # Default is brightdata — the platform's live provider. The retired geo_aeo
    # default silently health-checked a self-hosted tracker on localhost:3000
    # that no deploy runs, so audits were skipped with a misleading message.
    citation_provider: str = "brightdata"  # brightdata | geo_aeo | peec | none | auto
    geo_aeo_tracker_url: str = "http://localhost:3000"
    geo_aeo_providers: str = "perplexity,chatgpt,google_ai"
    geo_aeo_concurrency: int = 2
    citation_sample_runs: int = 3

    # Bright Data native AI-search APIs (CITATION_PROVIDER=brightdata) — calls
    # api.brightdata.com directly, no self-hosted tracker app needed.
    bright_data_api_key: str = ""
    bright_data_providers: str = "chatgpt,gemini,perplexity"
    bright_data_concurrency: int = 2
    # Async snapshot polling: ChatGPT (and batched scrapes) return 202 + a
    # snapshot_id that must be polled to "ready" then downloaded. Defaults give
    # a batch up to poll_interval*max_polls = 10 min to finish before giving up.
    bright_data_poll_interval_seconds: int = 10
    bright_data_max_polls: int = 60
    # Dataset ids from the Bright Data Scrapers Library (override if reassigned).
    bright_data_dataset_chatgpt: str = "gd_m7aof0k82r803d5bjm"
    bright_data_dataset_gemini: str = "gd_mbz66arm2mf9cu856y"
    bright_data_dataset_perplexity: str = "gd_m7dhdot1vw9a7gc1n"

    google_service_account_json: str = ""
    bing_api_key: str = ""
    # Comma-separated override of AI-assistant referrer hosts for GA4 segmentation.
    ai_referrer_hosts: str = ""

    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwks_url: str = ""

    slack_webhook_url: str = ""
    # Discord channel webhook — receives published-post notifications with links.
    discord_webhook_url: str = ""
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
    wp_app_password_quality: str = ""

    wp_username_axxiom: str = "admin"
    wp_username_ameritex: str = "admin"
    wp_username_arizona_es: str = "admin"
    wp_username_liftech: str = "admin"
    wp_username_quality: str = "admin"

    # Discussion settings applied to every post we publish (and re-applied on
    # every update), so it never depends on each WP site's inconsistent
    # Settings -> Discussion defaults. Both default off:
    #  - comments off: prevents spam-bot comments on unattended auto-posts.
    #  - pings off: ping_status=open only invites inbound trackback spam (it
    #    does NOT earn backlinks — that's a separate outbound setting) and is
    #    a dead SEO/AEO signal. Flip WP_ALLOW_PINGS=true to experiment.
    wp_allow_comments: bool = False
    wp_allow_pings: bool = False

    # WP user ID to set as the post author (byline) per brand; 0 = default to
    # the account behind the application password.
    wp_author_id_axxiom: int = 0
    wp_author_id_ameritex: int = 0
    wp_author_id_arizona_es: int = 0
    wp_author_id_liftech: int = 0
    wp_author_id_quality: int = 0

    # Retired 2026-07-06: motion, evolution, ironhawk (see alter_aeo_v9.sql).
    brand_ids: tuple[str, ...] = (
        "axxiom",
        "ameritex",
        "arizona_es",
        "liftech",
        "quality",
    )

    claude_model: str = "claude-sonnet-4-6"
    # Max pending queue items generated per brand, each daily content run.
    content_generation_max_per_brand: int = 1
    # Publish drafts automatically when they pass validation (monitor-after
    # model). Set false to restore the approve-before-publish gate — drafts
    # then wait in Content Review as before.
    auto_publish_enabled: bool = True

    # Daily automated topic discovery (GSC demand + citation gaps + coverage).
    # max_per_brand=1 -> alternate trend/AEO-gap picks day-to-day (recommended
    # starting cadence). max_per_brand>=2 -> pick one of each, same day.
    topic_discovery_enabled: bool = True
    topic_discovery_max_per_brand: int = 1
    topic_discovery_max_total: int = 10
    topic_discovery_min_impressions: int = 20

    openai_api_key: str = ""
    openai_image_model: str = "gpt-image-1"
    openai_image_size: str = "1536x1024"
    openai_image_quality: str = "medium"
    content_max_images: int = 3
    image_generation_enabled: bool = True
    content_generation_concurrency: int = 3

    # Image provider: "ideogram" (Ideogram 3.0), "fal" (fal.ai Flux 2 Pro /
    # Imagen 4), or "openai" (gpt-image). If the chosen provider has no key, the
    # pipeline falls back to any other configured provider (logged) so images
    # never silently stop on a misconfig.
    image_provider: str = "ideogram"
    fal_api_key: str = ""
    fal_image_model: str = "fal-ai/flux-2-pro"   # or e.g. fal-ai/imagen4
    fal_image_size: str = "landscape_4_3"
    fal_output_format: str = "jpeg"

    # Ideogram 3.0 — multipart POST to /v1/ideogram-v3/generate, Api-Key header,
    # returns an ephemeral data[0].url we download. Tuned for quality/realism:
    #  - rendering_speed QUALITY = best fidelity (FLASH/TURBO/DEFAULT are faster
    #    but softer; QUALITY is the point of switching providers). Drop to
    #    DEFAULT to cut cost/latency if volume grows.
    #  - style_type REALISTIC = photographic look, not illustration.
    #  - magic_prompt OFF = honor our detailed, realism-tuned briefs verbatim
    #    (MagicPrompt rewrites prompts, which helps short prompts but reduces
    #    accuracy for the rich briefs the planner already writes).
    ideogram_api_key: str = ""
    ideogram_endpoint: str = "https://api.ideogram.ai/v1/ideogram-v3/generate"
    ideogram_aspect_ratio: str = "16x10"
    ideogram_rendering_speed: str = "QUALITY"
    ideogram_style_type: str = "REALISTIC"
    ideogram_magic_prompt: str = "OFF"

    # Estimated API-spend rates shown on Reports (per-unit, USD). These are
    # tracking/budgeting estimates — set them to your actual observed rates.
    #  - content: per generated draft (article + its planning/correction Claude
    #    calls); ~$0.10-0.15 for a full Sonnet article.
    #  - image: per generated image (Ideogram QUALITY ~$0.08-0.10).
    #  - citation record: per Bright Data AI-search result.
    cost_per_content_generation_usd: float = 0.12
    cost_per_image_usd: float = 0.09
    cost_per_citation_record_usd: float = 0.002

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

    @property
    def wp_comment_status(self) -> str:
        return "open" if self.wp_allow_comments else "closed"

    @property
    def wp_ping_status(self) -> str:
        return "open" if self.wp_allow_pings else "closed"

    def get_wp_password(self, brand_id: str) -> str:
        raw = getattr(self, f"wp_app_password_{brand_id}", "")
        # Application passwords are shown with spaces; strip for Basic auth.
        return raw.replace(" ", "") if isinstance(raw, str) else ""

    def get_wp_username(self, brand_id: str) -> str:
        return getattr(self, f"wp_username_{brand_id}", "admin")

    def get_wp_author_id(self, brand_id: str) -> int:
        return getattr(self, f"wp_author_id_{brand_id}", 0) or 0

    def wp_publish_configured(self, brand_id: str) -> bool:
        return bool(self.get_wp_password(brand_id).strip())

    def wp_configured_brand_ids(self) -> list[str]:
        return [brand_id for brand_id in self.brand_ids if self.wp_publish_configured(brand_id)]


@lru_cache
def get_settings() -> Settings:
    return Settings()
