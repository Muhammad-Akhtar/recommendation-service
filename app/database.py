import asyncpg

from .config import get_settings

_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    """Create the connection pool and ensure the recommendations table exists."""
    global _pool
    settings = get_settings()

    _pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        min_size=1,
        max_size=5,
    )

    async with _pool.acquire() as connection:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendations (
                user_id BIGINT PRIMARY KEY,
                recommendations JSONB NOT NULL
            )
            """
        )
        # Task 18 upgrade — durable click/purchase history (offline store)
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_events (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                item_id BIGINT NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_events_user_id_created_at
            ON user_events (user_id, created_at DESC)
            """
        )
        # Task 19 — candidate items for model ranking (not Task 14 results)
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendation_items (
                id BIGSERIAL PRIMARY KEY,
                item_id BIGINT NOT NULL UNIQUE,
                score DOUBLE PRECISION NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )


async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    return _pool
