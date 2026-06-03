import asyncio
from datetime import date
from sqlalchemy import select

from app.database import AsyncSessionLocal, init_db
from app.models.brand import Brand
from app.models.content import ContentQueue
from app.utils.seed_data import BRANDS, CONTENT_QUEUE_SEED


async def seed_brands_and_queue():
    await init_db()
    async with AsyncSessionLocal() as session:
        for brand_data in BRANDS:
            existing = await session.get(Brand, brand_data["id"])
            if existing:
                continue
            session.add(Brand(**brand_data))

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
