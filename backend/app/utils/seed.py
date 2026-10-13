import asyncio
import re
from datetime import date
from sqlalchemy import select

from app.database import AsyncSessionLocal, init_db
from app.models.brand import Brand
from app.models.content import ContentQueue
from app.utils.seed_data import BRANDS, CONTENT_QUEUE_SEED


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")[-10:]


def phone_update(current: str | None, seed_phone: str | None, retired: list[str]) -> str | None:
    """The phone the seed should write, or None to leave the brand's alone.

    Brand Settings owns the phone. The seed fills it only when it is empty,
    or when it is one of the CallRail pool numbers an earlier seed wrote by
    mistake. It used to overwrite the phone on every startup, so each deploy
    or restart reverted every Brand Settings change.
    """
    if not seed_phone:
        return None
    have = _digits(current)
    if not have or have in {_digits(p) for p in retired}:
        return seed_phone if have != _digits(seed_phone) else None
    return None


async def seed_brands_and_queue():
    await init_db()
    async with AsyncSessionLocal() as session:
        for brand_data in BRANDS:
            fields = {k: v for k, v in brand_data.items() if k != "retired_phones"}
            existing = await session.get(Brand, fields["id"])
            if existing:
                # Existing brands: fill gaps only, never overwrite an edit.
                if fields.get("author_name") and not existing.author_name:
                    existing.author_name = fields["author_name"]
                new_phone = phone_update(
                    existing.phone, fields.get("phone"), brand_data.get("retired_phones", [])
                )
                if new_phone:
                    existing.phone = new_phone
                continue
            session.add(Brand(**fields))

        existing_queue = await session.execute(select(ContentQueue).limit(1))
        if existing_queue.scalar_one_or_none() is None:
            for item in CONTENT_QUEUE_SEED:
                scheduled = item.get("scheduled_for")
                if isinstance(scheduled, str):
                    scheduled = date.fromisoformat(scheduled)
                session.add(
                    ContentQueue(
                        brand_id=item["brand_id"],
                        content_type=item["content_type"],
                        title=item["title"],
                        target_query=item["target_query"],
                        priority=item["priority"],
                        scheduled_for=scheduled,
                        status="pending",
                    )
                )
        await session.commit()
    print("Seed complete: brands and content queue populated.")


if __name__ == "__main__":
    asyncio.run(seed_brands_and_queue())
