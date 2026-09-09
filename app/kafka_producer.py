from aiokafka import AIOKafkaProducer

from .config import get_settings
from .events import UserInteractionEvent
from .logging_config import get_logger
from .resilience import retry_async
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

logger = get_logger("kafka_producer")


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


async def _send_once(
    *,
    topic: str,
    payload: bytes,
    key: bytes,
) -> object:
    settings = get_settings()
    producer = _producer
    if producer is None:
        ephemeral = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            request_timeout_ms=5000,
        )
        await ephemeral.start()
        try:
            return await ephemeral.send_and_wait(topic, value=payload, key=key)
        finally:
            await ephemeral.stop()
    return await producer.send_and_wait(topic, value=payload, key=key)


async def publish_user_interaction(event: UserInteractionEvent) -> None:
    """Publish a user interaction as Confluent Avro (keyed by user_id)."""
    settings = get_settings()
    _, writer_schema, schema_id = _ensure_schema_registered()
    payload = encode_avro_message(
        schema_id,
        writer_schema,
        event_to_avro_record(event),
    )
    key = str(event.user_id).encode("utf-8")

    metadata = await retry_async(
        lambda: _send_once(
            topic=settings.kafka_topic,
            payload=payload,
            key=key,
        ),
        attempts=settings.kafka_publish_attempts,
        base_delay=settings.retry_base_delay_seconds,
        operation="kafka_publish",
    )
    print(
        f"Published Avro event: user={event.user_id} item={event.item_id} "
        f"type={event.event_type} device_type={event.device_type} "
        f"schema_id={schema_id} partition={metadata.partition} "
        f"offset={metadata.offset}"
    )


async def publish_to_dlq(
    event: UserInteractionEvent,
    *,
    error: str,
    instance_id: str = "api",
) -> None:
    """
    Best-effort dead-letter publish after durable-write retries are exhausted.

    Payload stays Avro (same schema) so operators can replay later.
    """
    settings = get_settings()
    try:
        _, writer_schema, schema_id = _ensure_schema_registered()
        payload = encode_avro_message(
            schema_id,
            writer_schema,
            event_to_avro_record(event),
        )
        key = str(event.user_id).encode("utf-8")
        await _send_once(
            topic=settings.kafka_dlq_topic,
            payload=payload,
            key=key,
        )
        logger.warning(
            "dlq_published",
            topic=settings.kafka_dlq_topic,
            user_id=event.user_id,
            item_id=event.item_id,
            error=error,
            instance_id=instance_id,
        )
    except Exception as exc:  # noqa: BLE001 — DLQ must not crash the consumer loop
        logger.warning(
            "dlq_publish_failed",
            user_id=event.user_id,
            error=str(exc),
            original_error=error,
            instance_id=instance_id,
        )
