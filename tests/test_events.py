from app.events import UserInteractionEvent
from app.schema_registry import (
    encode_avro_message,
    event_to_avro_record,
    load_avro_schema,
)


def test_user_interaction_event_defaults_timestamp():
    event = UserInteractionEvent(
        user_id=123,
        item_id=42,
        event_type="view",
    )

    assert event.user_id == 123
    assert event.item_id == 42
    assert event.event_type == "view"
    assert event.timestamp.endswith("Z")
    assert event.device_type is None


def test_user_interaction_event_optional_device_type():
    event = UserInteractionEvent(
        user_id=123,
        item_id=42,
        event_type="view",
        device_type="mobile",
    )
    assert event.device_type == "mobile"


def test_user_interaction_event_json_roundtrip():
    event = UserInteractionEvent(
        user_id=123,
        item_id=42,
        event_type="view",
        timestamp="2026-09-08T12:00:00Z",
        device_type="web",
    )

    parsed = UserInteractionEvent.model_validate_json(event.model_dump_json())
    assert parsed == event


def test_avro_v2_schema_has_optional_device_type():
    schema = load_avro_schema("user_interaction.avsc")
    field_names = [f["name"] for f in schema["fields"]]
    assert "device_type" in field_names
    device = next(f for f in schema["fields"] if f["name"] == "device_type")
    assert device["type"] == ["null", "string"]
    assert device["default"] is None


def test_avro_encode_roundtrip_local():
    """Encode/decode without Schema Registry (local schema id stub)."""
    schema = load_avro_schema("user_interaction.avsc")
    event = UserInteractionEvent(
        user_id=123,
        item_id=42,
        event_type="view",
        timestamp="2026-09-08T12:00:00Z",
        device_type=None,
    )
    payload = encode_avro_message(1, schema, event_to_avro_record(event))
    assert payload[0] == 0
    assert len(payload) > 5
