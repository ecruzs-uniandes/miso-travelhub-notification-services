import asyncio
import json
import logging

from confluent_kafka import Consumer, KafkaError, Producer

from app.config import settings
from app.database import AsyncSessionLocal
from app.kafka.dispatcher import get_handler
from app.schemas.events import EventEnvelope
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

TOPICS = ["booking-events", "payment-events", "user-events"]

KAFKA_CONFIG = {
    "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
    "group.id": settings.KAFKA_CONSUMER_GROUP,
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,
    "max.poll.interval.ms": 300000,
}


def _get_producer() -> Producer:
    return Producer({"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS})


async def _publish_to_dlq(producer: Producer, raw_message: bytes, error_reason: str) -> None:
    try:
        payload = json.dumps(
            {"raw": raw_message.decode("utf-8", errors="replace"), "error": error_reason}
        ).encode()
        producer.produce(settings.KAFKA_DLQ_TOPIC, value=payload)
        producer.flush(timeout=5)
    except Exception as exc:
        logger.error("dlq_publish_failed", extra={"error": str(exc)})


async def _process_message(msg_value: bytes) -> None:
    try:
        data = json.loads(msg_value)
        envelope = EventEnvelope(**data)
    except Exception as exc:
        raise ValueError(f"Deserialización fallida: {exc}") from exc

    handler = get_handler(envelope.event_type)
    if not handler:
        return

    async with AsyncSessionLocal() as session:
        try:
            svc = NotificationService(session)
            await handler(envelope, svc)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def consumer_loop() -> None:
    consumer = Consumer(KAFKA_CONFIG)
    producer = _get_producer()
    consumer.subscribe(TOPICS)
    logger.info("kafka_consumer_subscribed", extra={"topics": TOPICS})

    try:
        while True:
            msg = await asyncio.get_event_loop().run_in_executor(
                None, lambda: consumer.poll(timeout=1.0)
            )

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("kafka_consumer_error", extra={"error": str(msg.error())})
                continue

            raw = msg.value()
            try:
                await _process_message(raw)
            except ValueError as exc:
                logger.error("kafka_message_invalid", extra={"error": str(exc)})
                await _publish_to_dlq(producer, raw, str(exc))
            except Exception as exc:
                logger.error("kafka_handler_failed", extra={"error": str(exc)})
                await _publish_to_dlq(producer, raw, str(exc))
            finally:
                consumer.commit(message=msg)

    except asyncio.CancelledError:
        logger.info("kafka_consumer_cancelled")
    finally:
        consumer.close()
