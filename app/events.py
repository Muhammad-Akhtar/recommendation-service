from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class UserInteractionEvent(BaseModel):
    user_id: int
    item_id: int
    event_type: str
    timestamp: str = Field(default_factory=_utc_now)
    # Schema V2 (Task 17): optional, backward/forward friendly with Avro default null
    device_type: str | None = None
