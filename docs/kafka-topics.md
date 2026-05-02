# Kafka Topics — notification-services

## Topics consumidos

| Topic | Particiones | Event types |
|---|---|---|
| `booking-events` | 3 | `booking.confirmed`, `booking.cancelled`, `booking.reminder` |
| `payment-events` | 3 | `payment.completed`, `payment.failed` |
| `user-events` | 3 | `user.welcome`, `user.password_reset`, `user.email_verification` |

## Topics producidos

| Topic | Particiones | Uso |
|---|---|---|
| `notification-dlq` | 1 | Mensajes que fallaron deserialización o procesamiento tras 3 reintentos |

## Consumer Group

`notification-services-group`

## Envelope estándar

```json
{
  "event_id": "evt_01HZX9...",
  "event_type": "booking.confirmed",
  "occurred_at": "2026-05-01T15:30:00Z",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": { ... }
}
```

## Feature flag

`KAFKA_CONSUMER_ENABLED=false` desactiva el consumer sin detener el servicio HTTP.
Usar en PROD hasta que la VM Kafka esté disponible.
