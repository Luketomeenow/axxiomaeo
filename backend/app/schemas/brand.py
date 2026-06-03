from pydantic import BaseModel, field_validator


def normalize_ga4_property_id(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.startswith("properties/"):
        cleaned = cleaned.removeprefix("properties/").strip()
    return cleaned or None


class BrandUpdate(BaseModel):
    name: str | None = None
    wp_url: str | None = None
    markets: list[str] | None = None
    phone: str | None = None
    ga4_property_id: str | None = None
    gsc_site_url: str | None = None
    logo_url: str | None = None

    @field_validator("ga4_property_id", mode="before")
    @classmethod
    def normalize_ga4(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        return normalize_ga4_property_id(value)

    @field_validator("gsc_site_url", "phone", "logo_url", mode="before")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None or not isinstance(value, str):
            return value
        cleaned = value.strip()
        return cleaned or None


def brand_to_dict(b) -> dict:
    return {
        "id": b.id,
        "name": b.name,
        "wp_url": b.wp_url,
        "markets": b.markets,
        "is_corporate": b.is_corporate,
        "phone": b.phone,
        "ga4_property_id": b.ga4_property_id,
        "gsc_site_url": b.gsc_site_url,
        "logo_url": b.logo_url,
    }
