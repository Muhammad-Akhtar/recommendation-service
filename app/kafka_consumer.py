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
from app.redis_client import redis_client
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


async def process_event(event: UserInteractionEvent, instance_id: str) -> None:
    """
    Task 18 upgraded pipeline for one event:

      1) PostgreSQL user_events  → durable history (source of truth)
      2) Redis features:user:*   → online features for inference
    """
    # 1. Durable write first
    pool = get_pool()
    async with pool.acquire() as connection:
        event_id = await save_user_event(event, connection)
    log(
        f"[{instance_id}] Saved user_events id={event_id} "
        f"user={event.user_id} item={event.item_id} type={event.event_type}"
    )

    # 2. Materialize online features (derived state)
    features = await apply_interaction_event(event, redis_client)
    log(
        f"[{instance_id}] Materialized Redis features user={features.user_id} "
        f"clicks={features.click_count} "
        f"purchases={features.purchase_count} "
        f"last_item={features.last_item_id}"
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
                    f"group={settings.kafka_consumer_group})"
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

                    try:
                        await process_event(event, instance_id)
                    except Exception as e:
                        log(
                            f"[{instance_id}] event pipeline failed "
                            f"user={event.user_id}: {e}"
                        )
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
