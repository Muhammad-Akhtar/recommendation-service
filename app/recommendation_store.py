import json

import asyncpg

POPULAR_RECOMMENDATIONS = [10, 20, 30, 40, 50]


async def get_recommendations(
    user_id: int,
    connection: asyncpg.Connection,
) -> list[int]:
    row = await connection.fetchrow(
        "SELECT recommendations FROM recommendations WHERE user_id = $1",
        user_id,
    )

    if row is None:
        raise KeyError(f"No recommendations found for user {user_id}")

    data = row["recommendations"]
    if isinstance(data, str):
        return json.loads(data)
    return list(data)


async def save_recommendations(
    user_id: int,
    recommendations: list[int],
    connection: asyncpg.Connection,
) -> None:
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
