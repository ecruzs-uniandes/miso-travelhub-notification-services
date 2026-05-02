# ADR-001: Schema de eventos Kafka

## Contexto
notification-services necesita consumir eventos de múltiples servicios (booking, payment, user).

## Decisión
Usar un envelope JSON estándar `{event_id, event_type, occurred_at, user_id, payload}` para todos los eventos.

## Consecuencias
- Todos los productores deben usar este envelope.
- El `event_id` garantiza idempotencia via UNIQUE constraint en `notification_log`.
- El campo `payload` es flexible (dict) para acomodar distintos tipos de evento.
