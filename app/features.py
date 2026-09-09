from pydantic import BaseModel


class UserFeatures(BaseModel):
    """Online features served from Redis for low-latency model inference.

    Derived from durable PostgreSQL `user_events`, not the source of truth.
    """

    user_id: int
    click_count: int = 0
    purchase_count: int = 0
    last_item_id: int | None = None


class UserEventRecord(BaseModel):
    """One durable row from PostgreSQL user_events."""

    id: int
    user_id: int
    item_id: int
    event_type: str
    created_at: str
