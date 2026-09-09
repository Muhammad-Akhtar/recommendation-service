import asyncio
import json

import asyncpg

from app.config import get_settings
from app.recommendation_repository import ensure_recommendation_items_table


# Task 14 — persisted per-user recommendation results (fallback store)
RECOMMENDATIONS = {
    123: [10, 25, 42, 81, 99],
    456: [12, 33, 47, 58, 72],
    789: [5, 18, 29, 61, 94],
}

# Task 19 — candidate catalog for the model to rank
RECOMMENDATION_ITEMS = [
    (10, 0.95),
    (20, 0.91),
    (30, 0.88),
    (40, 0.84),
    (50, 0.80),
    (60, 0.76),
    (70, 0.72),
    (80, 0.68),
    (90, 0.65),
    (91, 0.63),
    (92, 0.61),
    (93, 0.59),
    (94, 0.57),
]


async def main() -> None:
    settings = get_settings()
    connection = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )

    try:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendations (
                user_id BIGINT PRIMARY KEY,
                recommendations JSONB NOT NULL
            )
            """
        )
        await ensure_recommendation_items_table(connection)

        for user_id, recommendations in RECOMMENDATIONS.items():
            await connection.execute(
                """
                INSERT INTO recommendations (user_id, recommendations)
                VALUES ($1, $2::jsonb)
                ON CONFLICT (user_id)
                DO UPDATE SET recommendations = EXCLUDED.recommendations
                """,
                user_id,
                json.dumps(recommendations),
            )
            print(f"Seeded recommendations user_id={user_id}")

        for item_id, score in RECOMMENDATION_ITEMS:
            await connection.execute(
                """
                INSERT INTO recommendation_items (item_id, score, is_active)
                VALUES ($1, $2, TRUE)
                ON CONFLICT (item_id)
                DO UPDATE SET score = EXCLUDED.score, is_active = TRUE
                """,
                item_id,
                score,
            )
            print(f"Seeded recommendation_items item_id={item_id} score={score}")
    finally:
        await connection.close()

    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
