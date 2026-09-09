import pytest

from app.events import UserInteractionEvent
from app.feature_store import (
    apply_interaction_event,
    feature_key,
    get_user_features,
    update_user_features,
)
from app.features import UserFeatures


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.store[key] = value
        return True


@pytest.mark.asyncio
async def test_get_user_features_defaults_when_missing():
    redis = FakeRedis()
    features = await get_user_features(123, redis)
    assert features == UserFeatures(user_id=123)


@pytest.mark.asyncio
async def test_update_user_features_persists():
    redis = FakeRedis()
    updated = await update_user_features(
        123,
        redis,
        click_count=2,
        last_item_id=50,
    )
    assert updated.click_count == 2
    assert updated.last_item_id == 50
    assert feature_key(123) in redis.store

    loaded = await get_user_features(123, redis)
    assert loaded == updated


@pytest.mark.asyncio
async def test_apply_click_and_purchase_events():
    redis = FakeRedis()

    after_click = await apply_interaction_event(
        UserInteractionEvent(user_id=123, item_id=42, event_type="click"),
        redis,
    )
    assert after_click.click_count == 1
    assert after_click.purchase_count == 0
    assert after_click.last_item_id == 42

    after_click_2 = await apply_interaction_event(
        UserInteractionEvent(user_id=123, item_id=50, event_type="click"),
        redis,
    )
    assert after_click_2.click_count == 2
    assert after_click_2.last_item_id == 50

    after_purchase = await apply_interaction_event(
        UserInteractionEvent(user_id=123, item_id=99, event_type="purchase"),
        redis,
    )
    assert after_purchase.click_count == 2
    assert after_purchase.purchase_count == 1
    assert after_purchase.last_item_id == 99
