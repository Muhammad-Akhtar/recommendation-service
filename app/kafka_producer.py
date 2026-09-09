from aiokafka import AIOKafkaProducer

from .config import get_settings
from .events import UserInteractionEvent
from .schema_registry import (
    SchemaRegistryClient,
    encode_avro_message,
    event_to_avro_record,
    load_avro_schema,
)

_producer: AIOKafkaProducer | None = None
_registry: SchemaRegistryClient | None = None
_writer_schema: dict | None = None
_schema_id: int | None = None


def _ensure_schema_registered() -> tuple[SchemaRegistryClient, dict, int]:
    """Register current Avro schema (V2) with Schema Registry and cache the id."""
    global _registry, _writer_schema, _schema_id

    settings = get_settings()
    if _registry is None:
        _registry = SchemaRegistryClient(settings.schema_registry_url)

    if _writer_schema is None:
        _writer_schema = load_avro_schema("user_interaction.avsc")

    if _schema_id is None:
        _schema_id = _registry.register_schema(
            settings.kafka_value_subject,
            _writer_schema,
        )
        # Prefer FULL so old and new readers can interoperate with optional fields.
        _registry.set_compatibility(settings.kafka_value_subject, "FULL")
        print(
            f"Registered Avro schema subject={settings.kafka_value_subject} "
            f"id={_schema_id}"
        )

    return _registry, _writer_schema, _schema_id


async def start_producer() -> None:
    global _producer
    settings = get_settings()
    _ensure_schema_registered()
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        request_timeout_ms=5000,
    )
    await _producer.start()


async def stop_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None


async def check_kafka() -> bool:
    """Return True if Kafka bootstrap succeeds (used by /ready)."""
    settings = get_settings()
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        request_timeout_ms=2000,
    )
    try:
        await producer.start()
        return True
    except Exception:
        return False
    finally:
        try:
            await producer.stop()
        except Exception:
            pass


def check_schema_registry() -> bool:
    """Return True if Schema Registry HTTP API responds."""
    settings = get_settings()
    return SchemaRegistryClient(settings.schema_registry_url).ping()


async def publish_user_interaction(event: UserInteractionEvent) -> None:
    """Publish a user interaction as Confluent Avro (keyed by user_id)."""
    settings = get_settings()
    producer = _producer
    _, writer_schema, schema_id = _ensure_schema_registered()
    payload = encode_avro_message(
        schema_id,
        writer_schema,
        event_to_avro_record(event),
    )
    key = str(event.user_id).encode("utf-8")

    if producer is None:
        producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            request_timeout_ms=5000,
        )
        await producer.start()
        try:
            await producer.send_and_wait(
                settings.kafka_topic,
                value=payload,
                key=key,
            )
        finally:
            await producer.stop()
        return

    metadata = await producer.send_and_wait(
        settings.kafka_topic,
        value=payload,
        key=key,
    )
    print(
        f"Published Avro event: user={event.user_id} item={event.item_id} "
        f"type={event.event_type} device_type={event.device_type} "
        f"schema_id={schema_id} partition={metadata.partition} "
        f"offset={metadata.offset}"
    )
