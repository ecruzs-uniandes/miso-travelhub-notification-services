#!/bin/bash
set -euo pipefail

KAFKA_CONTAINER="${KAFKA_CONTAINER:-kafka}"

create_topic() {
  local topic="$1"
  local partitions="$2"
  docker exec "$KAFKA_CONTAINER" kafka-topics \
    --bootstrap-server localhost:9092 \
    --create --if-not-exists \
    --topic "$topic" \
    --partitions "$partitions" \
    --replication-factor 1
}

create_topic "booking-events" 3
create_topic "payment-events" 3
create_topic "user-events" 3
create_topic "notification-dlq" 1

echo "Topics OK."
docker exec "$KAFKA_CONTAINER" kafka-topics --bootstrap-server localhost:9092 --list
