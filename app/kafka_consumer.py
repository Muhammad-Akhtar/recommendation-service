import asyncio
import os
import socket
import sys

from aiokafka import AIOKafkaConsumer, ConsumerRebalanceListener
from aiokafka.structs import TopicPartition

from app.config import get_settings
from app.database import close_db, get_pool, init_db
from app.event_store import save_user_event
from app.events import UserInteractionEvent
from app.feature_store import apply_interaction_event
from app.kafka_producer import publish_to_dlq
from app.metrics import DLQ_MESSAGES_TOTAL
from app.redis_client import redis_client
from app.resilience import retry_async
from app.schema_registry import (
    SchemaRegistryClient,
    decode_avro_message,
    load_avro_schema,
)


def log(message: str) -> None:
    print(message, flush=True)


class PartitionRebalanceListener(ConsumerRebalanceListener):
    """Log partition assignment so Task 16 rebalancing is visible."""

    def __init__(self, instance_id: str) -> None:
        self.instance_id = instance_id

    async def on_partitions_revoked(self, revoked: set[TopicPartition]) -> None:
        parts = sorted(f"{tp.topic}:{tp.partition}" for tp in revoked)
        log(f"[{self.instance_id}] partitions revoked: {parts or 'none'}")

    async def on_partitions_assigned(self, assigned: set[TopicPartition]) -> None:
        parts = sorted(f"{tp.topic}:{tp.partition}" for tp in assigned)
        log(f"[{self.instance_id}] partitions assigned: {parts or 'none'}")


async def _save_event_durable(event: UserInteractionEvent) -> int:
    pool = get_pool()
    async with pool.acquire() as connection:
        return await save_user_event(event, connection)


async def process_event(event: UserInteractionEvent, instance_id: str) -> None:
    """
    Task 18 pipeline + resilience:

      1) PostgreSQL user_events with retry → on exhaustion: DLQ and stop
      2) Redis features:user:* (best-effort after durable success)
    """
    settings = get_settings()

    # 1. Durable write with limited retries — then DLQ (do not block the partition forever)
    try:
        event_id = await retry_async(
            lambda: _save_event_durable(event),
            attempts=settings.consumer_pg_attempts,
            base_delay=settings.retry_base_delay_seconds,
            operation="consumer_pg_save",
        )
    except Exception as e:
        log(
            f"[{instance_id}] durable write failed after retries "
            f"user={event.user_id}: {e} → DLQ"
        )
        await publish_to_dlq(event, error=str(e), instance_id=instance_id)
        DLQ_MESSAGES_TOTAL.inc()
        return

    log(
        f"[{instance_id}] Saved user_events id={event_id} "
        f"user={event.user_id} item={event.item_id} type={event.event_type}"
    )

    # 2. Materialize online features (derived). History already durable — soft-fail Redis.
    try:
        features = await apply_interaction_event(event, redis_client)
        log(
            f"[{instance_id}] Materialized Redis features user={features.user_id} "
            f"clicks={features.click_count} "
            f"purchases={features.purchase_count} "
            f"last_item={features.last_item_id}"
        )
    except Exception as e:
        log(
            f"[{instance_id}] Redis feature materialization failed "
            f"user={event.user_id} (history kept): {e}"
        )


async def run_consumer() -> None:
    settings = get_settings()
    instance_id = os.getenv("CONSUMER_INSTANCE_ID") or socket.gethostname()
    listener = PartitionRebalanceListener(instance_id)
    registry = SchemaRegistryClient(settings.schema_registry_url)
    reader_schema = load_avro_schema("user_interaction.avsc")  # V2 reader

    await init_db()
    log(f"[{instance_id}] PostgreSQL pool ready (user_events + recommendations)")

    try:
        while True:
            consumer = AIOKafkaConsumer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id=settings.kafka_consumer_group,
                client_id=f"recommendation-consumer-{instance_id}",
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                request_timeout_ms=10000,
            )

            try:
                log(
                    f"[{instance_id}] Connecting to Kafka at "
                    f"{settings.kafka_bootstrap_servers} "
                    f"(schema-registry={settings.schema_registry_url})..."
                )
                while not registry.ping():
                    log(f"[{instance_id}] waiting for Schema Registry...")
                    await asyncio.sleep(2)

                consumer.subscribe(
                    topics=[settings.kafka_topic],
                    listener=listener,
                )
                await consumer.start()
                log(
                    f"[{instance_id}] Kafka consumer started "
                    f"(topic={settings.kafka_topic}, "
                    f"group={settings.kafka_consumer_group}, "
                    f"dlq={settings.kafka_dlq_topic})"
                )

                async for message in consumer:
                    key = message.key.decode("utf-8") if message.key else None
                    try:
                        record = decode_avro_message(
                            message.value,
                            registry,
                            reader_schema=reader_schema,
                        )
                        event = UserInteractionEvent.model_validate(record)
                    except Exception as e:
                        # Poison / non-Avro: skip (auto-commit advances). Not infinite retry.
                        log(
                            f"[{instance_id}] skip non-Avro/invalid message "
                            f"partition={message.partition} "
                            f"offset={message.offset}: {e}"
                        )
                        continue

                    log(
                        f"[{instance_id}] Received Avro event: "
                        f"partition={message.partition} offset={message.offset} "
                        f"key={key} user={event.user_id} item={event.item_id} "
                        f"type={event.event_type} device_type={event.device_type} "
                        f"timestamp={event.timestamp}"
                    )

                    await process_event(event, instance_id)
            except Exception as e:
                log(f"[{instance_id}] Kafka consumer waiting for broker: {e}")
                await asyncio.sleep(5)
            finally:
                try:
                    await consumer.stop()
                except Exception:
                    pass
    finally:
        await close_db()


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    asyncio.run(run_consumer())
