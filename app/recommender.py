import asyncpg

from .recommendation_store import get_recommendations as get_recommendations_for_user


async def get_recommendations(
    user_id: int,
    connection: asyncpg.Connection,
) -> list[int]:
    print("Running recommendation logic...")
    return await get_recommendations_for_user(user_id, connection)
