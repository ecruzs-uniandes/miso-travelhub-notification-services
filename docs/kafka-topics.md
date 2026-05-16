# Kafka Topics — notification-services

**Última actualización:** 2026-05-16

---

## ⚠ Cambio arquitectónico (2026-05-16): los topics de dominio se reemplazan por HTTP

Durante el sprint, cada dominio (booking, payment, user) construyó su propio worker Kafka por su lado. Para no duplicar el consumer aquí y evitar drift de envelope, **notification-services ya NO consume `booking-events`, `payment-events` ni `user-events`**: los workers de dominio llaman vía HTTP a `POST /api/v1/notifications/events` con el **mismo envelope** que iban a publicar al broker. Ver `docs/api.md` § "POST /api/v1/notifications/events".

Este documento se mantiene como **contrato del envelope** (sigue siendo la fuente de verdad de qué `event_type` existen, qué `payload` lleva cada uno y cómo se valida en Pydantic), y como referencia histórica de los topics. La tabla de roles abajo aplica solo al `notification-dlq` (que sí seguimos produciendo) y al consumer si en algún momento se reactiva.

---

## Resumen

`notification-services` recibe eventos vía:
- **HTTP** (vigente): workers de dominio (booking, payment, user) llaman `POST /api/v1/notifications/events` con `X-Internal-Token`.
- **Kafka** (deshabilitado por defecto, `KAFKA_CONSUMER_ENABLED=false`): el consumer multi-topic original sigue en `app/kafka/consumer.py` y se puede reactivar sin cambios si el equipo decide volver al transporte por broker.

Y produce solo:

| Rol | Topic | Particiones | Replication |
|---|---|---|---|
| Producer (DLQ) | `notification-dlq` | 1 | 1 (DEV), 2 (PROD) |

**Consumer group (si se reactiva):** `notification-services-group`

---

## Envelope estándar

Todos los eventos siguen este schema JSON:

```json
{
  "event_id":    "evt_01HZX9abc123",
  "event_type":  "booking.confirmed",
  "occurred_at": "2026-05-01T15:30:00Z",
  "user_id":     "550e8400-e29b-41d4-a716-446655440000",
  "payload":     { }
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `event_id` | string | Identificador único del evento. Garantiza idempotencia en `notification_log`. |
| `event_type` | string | Tipo del evento en notación `dominio.accion`. Ver tabla de tipos abajo. |
| `occurred_at` | ISO 8601 datetime (UTC) | Cuándo ocurrió el evento en el dominio de origen. |
| `user_id` | UUID | ID del usuario al que pertenece la notificación. |
| `payload` | object | Datos específicos del tipo de evento. Ver cada sección abajo. |

### Validación de types en Python

```python
# app/schemas/events.py
class EventEnvelope(BaseModel):
    event_id: str
    event_type: str
    occurred_at: datetime
    user_id: UUID
    payload: dict
```

Si la deserialización falla (JSON inválido o campo requerido ausente), el mensaje se envía a `notification-dlq` y se commitea el offset. No se reintenta.

---

## Topic: `booking-events`

**Productor:** `booking-services` (repositorio externo al grupo 9)

### `booking.confirmed`

Se dispara cuando una reserva queda confirmada y el pago fue procesado.

```json
{
  "event_id": "evt_booking_confirmed_001",
  "event_type": "booking.confirmed",
  "occurred_at": "2026-05-01T15:30:00Z",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "booking_id": "660e8400-e29b-41d4-a716-446655440001",
    "hotel_name": "Hotel Bogotá Plaza",
    "hotel_id": "770e8400-e29b-41d4-a716-446655440002",
    "check_in": "2026-06-15T14:00:00Z",
    "check_out": "2026-06-18T11:00:00Z",
    "total": 450000,
    "currency": "COP",
    "room_type": "Doble Estándar",
    "guests": 2
  }
}
```

**Notificación generada:**
- Título: `Tu reserva está confirmada`
- Canal email: plantilla `booking_confirmed.email.html`
- Canal push: plantilla `booking_confirmed.push.json`

---

### `booking.cancelled`

Se dispara cuando una reserva es cancelada (por usuario o por el sistema).

```json
{
  "event_id": "evt_booking_cancelled_001",
  "event_type": "booking.cancelled",
  "occurred_at": "2026-05-02T09:00:00Z",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "booking_id": "660e8400-e29b-41d4-a716-446655440001",
    "hotel_name": "Hotel Bogotá Plaza",
    "check_in": "2026-06-15T14:00:00Z",
    "check_out": "2026-06-18T11:00:00Z",
    "reason": "Cancelación solicitada por el usuario",
    "refund_amount": 450000,
    "currency": "COP"
  }
}
```

**Notificación generada:**
- Título: `Tu reserva ha sido cancelada`
- Canal email: plantilla `booking_cancelled.email.html`
- Canal push: plantilla `booking_cancelled.push.json`

---

### `booking.reminder`

Recordatorio enviado N días antes del check-in (configurable en `booking-services`).

```json
{
  "event_id": "evt_booking_reminder_001",
  "event_type": "booking.reminder",
  "occurred_at": "2026-06-13T08:00:00Z",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "booking_id": "660e8400-e29b-41d4-a716-446655440001",
    "hotel_name": "Hotel Bogotá Plaza",
    "hotel_address": "Cra 13 # 85-80, Bogotá",
    "check_in": "2026-06-15T14:00:00Z",
    "check_out": "2026-06-18T11:00:00Z",
    "days_until_checkin": 2
  }
}
```

**Notificación generada:**
- Título: `Recordatorio de tu reserva`
- Canal email: plantilla `booking_reminder.email.html`
- Canal push: plantilla `booking_reminder.push.json`

---

## Topic: `payment-events`

**Productor:** `payments-services` (repositorio externo al grupo 9)

### `payment.completed`

Se dispara cuando un pago es procesado exitosamente.

```json
{
  "event_id": "evt_payment_completed_001",
  "event_type": "payment.completed",
  "occurred_at": "2026-05-01T15:29:55Z",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "payment_id": "880e8400-e29b-41d4-a716-446655440003",
    "booking_id": "660e8400-e29b-41d4-a716-446655440001",
    "amount": 450000,
    "currency": "COP",
    "provider": "mercadopago",
    "last4": "4242",
    "receipt_url": "https://mercadopago.com/receipt/xyz"
  }
}
```

**Notificación generada:**
- Título: `Pago completado exitosamente`
- Canal email: plantilla `payment_completed.email.html`

---

### `payment.failed`

Se dispara cuando un intento de pago falla.

```json
{
  "event_id": "evt_payment_failed_001",
  "event_type": "payment.failed",
  "occurred_at": "2026-05-01T15:29:55Z",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "payment_id": "880e8400-e29b-41d4-a716-446655440003",
    "booking_id": "660e8400-e29b-41d4-a716-446655440001",
    "amount": 450000,
    "currency": "COP",
    "provider": "mercadopago",
    "error_code": "insufficient_funds",
    "error_message": "Fondos insuficientes"
  }
}
```

**Notificación generada:**
- Título: `Error en el pago`
- Canal email: plantilla `payment_failed.email.html`

---

## Topic: `user-events`

**Productor:** `user-services`

> **Nota:** Al 2026-05-01, `user-services` aún no publica a Kafka. Los handlers de este topic están implementados pero inactivos hasta que se complete la integración. Ver coordinación en CLAUDE.md sección 22.

### `user.welcome`

Se dispara al registrar un nuevo usuario.

```json
{
  "event_id": "evt_user_welcome_001",
  "event_type": "user.welcome",
  "occurred_at": "2026-05-01T12:00:00Z",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "email": "nuevo@usuario.com",
    "full_name": "María García"
  }
}
```

**Notificación generada:**
- Título: `¡Bienvenido a TravelHub!`
- Canal email: plantilla `user_welcome.email.html`

---

### `user.password_reset`

Se dispara cuando el usuario solicita un restablecimiento de contraseña.

```json
{
  "event_id": "evt_password_reset_001",
  "event_type": "user.password_reset",
  "occurred_at": "2026-05-01T14:00:00Z",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "email": "usuario@ejemplo.com",
    "full_name": "María García",
    "reset_token": "tok_abc123",
    "expires_in_minutes": 30
  }
}
```

**Notificación generada:**
- Título: `Restablece tu contraseña`
- Canal email: plantilla `user_password_reset.email.html`

---

### `user.email_verification`

Se dispara al necesitar verificar el email de un usuario recién registrado.

```json
{
  "event_id": "evt_email_verify_001",
  "event_type": "user.email_verification",
  "occurred_at": "2026-05-01T12:01:00Z",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "email": "nuevo@usuario.com",
    "full_name": "María García",
    "verification_token": "tok_verify_xyz",
    "expires_in_minutes": 1440
  }
}
```

**Notificación generada:** igual que `user.welcome` (fusionado en la misma plantilla en MVP).

---

## Topic: `notification-dlq`

**Dead Letter Queue.** notification-services produce aquí cuando:
1. Un mensaje no puede deserializarse (JSON malformado o envelope incompleto).
2. Un mensaje falla procesamiento tras 3 reintentos con backoff exponencial.

### Formato del mensaje en DLQ

```json
{
  "original_topic": "booking-events",
  "original_offset": 42,
  "original_partition": 1,
  "original_payload": "<raw string del mensaje original>",
  "error": "ValidationError: field 'user_id' is required",
  "failed_at": "2026-05-01T15:35:00Z",
  "service": "notification-services",
  "attempt_count": 3
}
```

---

## Configuración del consumer

```python
KAFKA_CONFIG = {
    "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
    "group.id": "notification-services-group",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,   # commit manual tras procesamiento exitoso
    "max.poll.interval.ms": 300000,
    "session.timeout.ms": 10000,
}
```

El commit de offset ocurre **después** de insertar en BD (y publicar a DLQ si aplica). Esto garantiza at-least-once delivery con idempotencia a nivel de BD.

---

## Gestión de topics en GCP (VM Kafka)

Los topics deben existir antes del primer arranque del servicio. Crearlos vía IAP tunnel:

```bash
# Abrir IAP tunnel
gcloud compute ssh travelhub-kafka \
  --zone=us-central1-c \
  --project=gen-lang-client-0930444414 \
  --tunnel-through-iap

# Dentro de la VM
docker exec kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --create --if-not-exists \
  --topic notification-dlq \
  --partitions 1 \
  --replication-factor 1

# Verificar que los topics de dominio ya existen
docker exec kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --describe --topic booking-events

docker exec kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --list
```

---

## Prueba local con Kafka

Usando el stack local en `travelhub-local/`:

```bash
# Publicar evento de prueba
docker exec travelhub-local-kafka-1 kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic booking-events << 'EOF'
{"event_id":"evt_test_001","event_type":"booking.confirmed","occurred_at":"2026-05-01T10:00:00Z","user_id":"550e8400-e29b-41d4-a716-446655440000","payload":{"booking_id":"660e8400-e29b-41d4-a716-446655440001","hotel_name":"Hotel Test","check_in":"2026-06-15T14:00:00Z","check_out":"2026-06-18T11:00:00Z","total":100000,"currency":"COP"}}
EOF

# Verificar en la BD que se creó la notificación
docker exec travelhub-local-postgres-1 psql \
  -U travelhub_app travelhub_notifications \
  -c "SELECT id, event_type, title, created_at FROM notification ORDER BY created_at DESC LIMIT 5;"

# Verificar log de envío
docker exec travelhub-local-postgres-1 psql \
  -U travelhub_app travelhub_notifications \
  -c "SELECT event_id, channel, status, error_message FROM notification_log ORDER BY created_at DESC LIMIT 5;"
```

---

## Comportamiento ante event_type desconocido

Si llega un evento con `event_type` que no tiene handler registrado (ej: `booking.updated`):

1. Se loguea `WARNING unknown_event_type` con el tipo recibido.
2. Se commitea el offset normalmente.
3. **No se envía al DLQ** — no es un error técnico, es un evento que aún no interesa al servicio.

Esto permite que los productores evolucionen su schema sin bloquear notification-services.

---

## Feature flag

`KAFKA_CONSUMER_ENABLED=false` desactiva el consumer sin detener el servicio HTTP.

```bash
# Verificar estado en DEV
gcloud run services describe notification-services \
  --region=us-central1 \
  --project=gen-lang-client-0930444414 \
  --format="value(spec.template.spec.containers[0].env)"
```

Usar `false` en PROD hasta que la VM Kafka PROD esté disponible.
