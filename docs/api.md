# API Reference — notification-services

**Servicio:** `notification-services`
**Versión:** 1.0.0
**Última actualización:** 2026-05-16

---

## URLs base

| Ambiente | URL directa | Vía Gateway |
|---|---|---|
| DEV | `https://notification-services-ridyy4wz4q-uc.a.run.app` | `https://travelhub-gateway-1yvtqj7r.uc.gateway.dev` |
| PROD | `https://notification-services-<hash>-uc.a.run.app` | `https://apitravelhub.site` |
| Local | `http://localhost:8004` | — |

Las rutas públicas se exponen como `/api/v1/notifications/*` en el gateway.
Los endpoints internos (`/api/v1/notifications/internal`, `/api/v1/notifications/internal/welcome`, `/api/v1/notifications/events`) y de QA (`/api/v1/notifications/admin/test-event`) **no están en el gateway** — solo son alcanzables desde `subnet-services` y autenticados con `X-Internal-Token`.

---

## Autenticación

### Endpoints públicos
Todos requieren `Authorization: Bearer <JWT>` (RS256, emitido por `user-services`).
El API Gateway valida firma + `iss` + `aud` + `exp` antes de rutear la petición.
Este servicio solo hace decode sin re-verificar la firma (claim extraction para RBAC).

```bash
# Obtener JWT
TOKEN=$(curl -s -X POST https://user-services-ridyy4wz4q-uc.a.run.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"tu@email.com","password":"tupassword"}' | jq -r '.access_token')
```

### Endpoints internos (server-to-server)
Requieren header `X-Internal-Token` con el valor del secret `{prefix}-internal-notify-token`. No requieren JWT y NO están expuestos por el API Gateway: los callers (otros Cloud Run del monorepo) los invocan directo a la URL de Cloud Run del servicio. Incluye `/internal` (pms-sync-worker), `/internal/welcome` (user-services), `/events` (booking/payment/user workers), `/admin/test-event` (QA, feature-flagged).

---

## Códigos de error comunes

| Código | Causa |
|---|---|
| `400 Bad Request` | Payload inválido o campos requeridos ausentes |
| `401 Unauthorized` | JWT ausente, expirado, o token interno inválido |
| `403 Forbidden` | Rol insuficiente (RBAC) |
| `404 Not Found` | Notificación no encontrada o no pertenece al usuario |
| `422 Unprocessable Entity` | Error de validación Pydantic |
| `429 Too Many Requests` | Rate limit excedido (60 req/min por usuario/IP) |
| `500 Internal Server Error` | Fallo de proveedor (SendGrid/FCM) o BD |

Todos los errores retornan `{"detail": "Mensaje descriptivo en español"}`.

---

## Endpoints públicos

### GET /api/v1/notifications

Lista las notificaciones del usuario autenticado, ordenadas por fecha descendente.

**Roles permitidos:** `traveler`, `hotel_admin`

**Query parameters:**

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `limit` | int (1-100) | 20 | Notificaciones por página |
| `offset` | int (≥ 0) | 0 | Desplazamiento para paginación |
| `unread_only` | bool | false | Si `true`, solo retorna notificaciones no leídas |

**Response 200:**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440010",
      "event_type": "booking.confirmed",
      "title": "Tu reserva está confirmada",
      "body": "Tu reserva en Hotel Bogotá Plaza está confirmada. Check-in: 15 de junio de 2026.",
      "metadata": {
        "booking_id": "660e8400-e29b-41d4-a716-446655440001",
        "hotel_name": "Hotel Bogotá Plaza",
        "check_in": "2026-06-15T14:00:00Z",
        "check_out": "2026-06-18T11:00:00Z",
        "total": 450000,
        "currency": "COP"
      },
      "read_at": null,
      "created_at": "2026-05-01T10:30:00Z"
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

**Ejemplo curl:**
```bash
curl -s "https://notification-services-ridyy4wz4q-uc.a.run.app/api/v1/notifications?limit=10&unread_only=true" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

---

### POST /api/v1/notifications/{id}/read

Marca una notificación específica como leída. Idempotente: si ya estaba leída, retorna el mismo objeto.

**Roles permitidos:** `traveler`, `hotel_admin`

**Path parameter:** `id` — UUID de la notificación

**Response 200:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440010",
  "event_type": "booking.confirmed",
  "title": "Tu reserva está confirmada",
  "body": "...",
  "metadata": {},
  "read_at": "2026-05-01T11:00:00Z",
  "created_at": "2026-05-01T10:30:00Z"
}
```

**Errores:**
- `404` — Notificación no encontrada o no pertenece al usuario autenticado.

**Ejemplo curl:**
```bash
curl -s -X POST \
  "https://notification-services-ridyy4wz4q-uc.a.run.app/api/v1/notifications/550e8400-e29b-41d4-a716-446655440010/read" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

---

### POST /api/v1/notifications/read-all

Marca todas las notificaciones no leídas del usuario como leídas.

**Roles permitidos:** `traveler`, `hotel_admin`

**Response 200:**
```json
{
  "updated": 5
}
```

**Ejemplo curl:**
```bash
curl -s -X POST \
  "https://notification-services-ridyy4wz4q-uc.a.run.app/api/v1/notifications/read-all" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

---

### GET /api/v1/notifications/preferences

Retorna las preferencias de notificación del usuario autenticado. Si el usuario no tiene preferencias registradas, las crea con valores por defecto (`email_enabled=true`, `push_enabled=true`).

**Roles permitidos:** `traveler`, `hotel_admin`

**Response 200:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email_enabled": true,
  "push_enabled": true,
  "sms_enabled": false,
  "whatsapp_enabled": false,
  "email_address": "usuario@ejemplo.com",
  "phone_number": null,
  "fcm_token": null,
  "locale": "es",
  "updated_at": "2026-05-01T10:00:00Z"
}
```

**Ejemplo curl:**
```bash
curl -s "https://notification-services-ridyy4wz4q-uc.a.run.app/api/v1/notifications/preferences" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

---

### PUT /api/v1/notifications/preferences

Actualiza las preferencias del usuario autenticado. Solo se actualizan los campos enviados (PATCH semantics aunque el método sea PUT).

**Roles permitidos:** `traveler`, `hotel_admin`

**Body (todos los campos son opcionales):**
```json
{
  "email_enabled": true,
  "push_enabled": false,
  "sms_enabled": false,
  "whatsapp_enabled": false,
  "email_address": "nuevo@email.com",
  "phone_number": "+573001234567",
  "fcm_token": "fJpXdMlK..."
}
```

**Response 200:** objeto preferences actualizado (mismo formato que GET).

**Errores:**
- `400` — `email_address` tiene formato inválido, o `phone_number` no tiene prefijo `+`.

**Ejemplo curl:**
```bash
curl -s -X PUT \
  "https://notification-services-ridyy4wz4q-uc.a.run.app/api/v1/notifications/preferences" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email_enabled": true, "email_address": "tu@email.com"}' | jq .
```

---

## Endpoint interno

### POST /api/v1/notifications/internal

Dispara una notificación sincrónica desde servicios internos. Solo alcanzable desde `subnet-services` en la VPC (firewall bloquea tráfico externo).

**No está en el API Gateway. No requiere JWT. Requiere `X-Internal-Token`.**

**Caller:** `pms-sync-worker`

**Header requerido:**
```
X-Internal-Token: <valor de secret dev-travelhub-internal-notify-token>
```

**Body:**

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `type` | string | ✅ | Tipo de notificación PMS |
| `user_id` | UUID | ✅ | ID del hotel admin a notificar |
| `hotel_id` | UUID | ✅ | ID del hotel relacionado |
| `details` | object | ✅ | Detalles del evento (libre) |
| `recipients` | array[string] | ✅ | Roles a notificar (actualmente solo `["hotel_admin"]`) |

**Tipos de notificación válidos (`type`):**

| Valor | Plantilla usada | Descripción |
|---|---|---|
| `pms_sync_conflict` | `pms_sync_conflict.email.*` | Conflicto de disponibilidad al sincronizar PMS |
| `pms_sync_error` | `pms_sync_error.email.*` | Error técnico en la sincronización |
| `pms_sync_complete` | — (solo in-app) | Sincronización completada exitosamente |

**Body ejemplo:**
```json
{
  "type": "pms_sync_conflict",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "hotel_id": "660e8400-e29b-41d4-a716-446655440001",
  "details": {
    "conflict_type": "availability",
    "description": "La habitación 101 está marcada como disponible en el PMS pero tiene reserva activa en TravelHub.",
    "room_type": "Doble Estándar",
    "check_in": "2026-06-15"
  },
  "recipients": ["hotel_admin"]
}
```

**Response 202 Accepted:**
```json
{
  "notification_id": "770e8400-e29b-41d4-a716-446655440002",
  "channels_sent": ["email"]
}
```

Si el usuario no tiene email configurado, `channels_sent` estará vacío pero la respuesta sigue siendo 202 (la notificación in-app se creó igual).

**Errores:**
- `401` — `X-Internal-Token` ausente o incorrecto.
- `400` — `type` desconocido, `user_id` o `hotel_id` no son UUIDs válidos.
- `500` — Fallo al enviar (el log tendrá el detalle; la notificación in-app se crea igual).

**Ejemplo curl (DEV):**
```bash
# Leer el token desde Secret Manager
INTERNAL_TOKEN=$(gcloud secrets versions access latest \
  --secret=dev-travelhub-internal-notify-token \
  --project=gen-lang-client-0930444414)

curl -s -X POST \
  "https://notification-services-ridyy4wz4q-uc.a.run.app/api/v1/notifications/internal" \
  -H "X-Internal-Token: $INTERNAL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "pms_sync_conflict",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "hotel_id": "660e8400-e29b-41d4-a716-446655440001",
    "details": {"conflict_type": "availability", "description": "Smoke test"},
    "recipients": ["hotel_admin"]
  }' | jq .
```

---

### POST /api/v1/notifications/events

Ingesta HTTP genérica de eventos de notificación. **Sustituye** el consumo Kafka que originalmente este servicio iba a hacer de los topics `booking-events`, `payment-events`, `user-events`: ahora los workers de cada dominio (booking, payment, user) llaman a este endpoint con el mismo envelope que iban a publicar al broker.

Internamente delega al mismo `process_event()` que usa el consumer Kafka y `/admin/test-event`, así que renderización de plantillas, idempotencia por `event_id`, selección de canales y reintentos siguen idénticos.

**No está en el API Gateway. No requiere JWT. Requiere `X-Internal-Token`.**

**Callers esperados:** `booking-service`, `payments-service`, `user-services` (cuando emita welcome/password-reset/email-verification) — todos vía Cloud Run-to-Cloud Run dentro de la VPC.

**Header requerido:**
```
X-Internal-Token: <valor de secret {prefix}-internal-notify-token>
```

**Body (envelope estándar TravelHub):**

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `event_id` | string | ✅ | ID único del evento. Idempotencia: mismo `event_id+channel` no reenvía. |
| `event_type` | string | ✅ | Tipo de evento. Lista cerrada — ver tabla abajo. |
| `occurred_at` | datetime ISO-8601 | ✅ | Cuándo ocurrió el evento de dominio (UTC). |
| `user_id` | UUID | ✅ | Destinatario. Debe existir en `notification_preference` (o se autoupserts en `user.welcome`). |
| `payload` | object | ✅ | Campos específicos del `event_type` — ver schemas Pydantic. |

**`event_type` soportados:**

| event_type | Payload mínimo | Plantilla |
|---|---|---|
| `booking.confirmed` | `{booking_id, hotel_name, check_in, check_out, total, currency}` | `booking_confirmed.email.*` |
| `booking.cancelled` | `{booking_id, hotel_name, check_in, check_out, reason?}` | `booking_cancelled.email.*` |
| `booking.reminder` | `{booking_id, hotel_name, check_in, check_out, days_until}` | `booking_reminder.email.*` |
| `payment.completed` | `{payment_id, booking_id, amount, currency, provider}` | `payment_completed.email.*` |
| `payment.failed` | `{payment_id, booking_id, amount, currency, reason?}` | `payment_failed.email.*` |
| `user.welcome` | `{email, full_name}` | `user_welcome.email.*` |
| `user.password_reset` | `{email, full_name, reset_token, reset_url}` | `user_password_reset.email.*` |

Un `event_type` no listado responde 202 igualmente, pero el dispatcher loguea `unknown_event_type` y no envía nada (mismo comportamiento que el consumer Kafka — no es error técnico).

**Body ejemplo:**
```json
{
  "event_id": "evt_01HZX9ABC123",
  "event_type": "booking.confirmed",
  "occurred_at": "2026-05-16T18:30:00Z",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "booking_id": "660e8400-e29b-41d4-a716-446655440001",
    "hotel_name": "Hotel Bogotá Plaza",
    "check_in": "2026-06-15T14:00:00Z",
    "check_out": "2026-06-18T11:00:00Z",
    "total": 450000,
    "currency": "COP"
  }
}
```

**Response 202 Accepted:**
```json
{
  "accepted": true,
  "event_id": "evt_01HZX9ABC123",
  "event_type": "booking.confirmed",
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Errores:**
- `401` — `X-Internal-Token` ausente o incorrecto.
- `422` — Envelope inválido (falta campo, tipo equivocado).
- `500` — Falla al renderizar plantilla o enviar (la transacción se rollback-ea; el caller debe reintentar con el mismo `event_id`).

**Ejemplo curl (DEV):**
```bash
INTERNAL_TOKEN=$(gcloud secrets versions access latest \
  --secret=dev-travelhub-internal-notify-token \
  --project=gen-lang-client-0930444414)

curl -s -X POST \
  "https://notification-services-ridyy4wz4q-uc.a.run.app/api/v1/notifications/events" \
  -H "X-Internal-Token: $INTERNAL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_smoke_'$(date +%s)'",
    "event_type": "booking.confirmed",
    "occurred_at": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {
      "booking_id": "660e8400-e29b-41d4-a716-446655440001",
      "hotel_name": "Hotel Bogotá Plaza",
      "check_in": "2026-06-15T14:00:00Z",
      "check_out": "2026-06-18T11:00:00Z",
      "total": 450000,
      "currency": "COP"
    }
  }' | jq .
```

> **Por qué HTTP y no Kafka:** los workers de booking/payment/user del equipo se diseñaron como consumidores Kafka propios por dominio (ej. payment-service publica a `payment-events` y su worker procesa). Como notification-services no es el dueño de esos topics y los workers ya están desplegados, los workers nos llaman directamente vía HTTP en vez de notification consumir Kafka. El envelope es el mismo, así que si en el futuro queremos volver a consumir, solo cambia el transporte.

---

## Health endpoints

### GET /health

Liveness probe. Responde siempre que el proceso esté corriendo.

**Response 200:**
```json
{
  "status": "ok",
  "service": "notification-services",
  "env": "dev"
}
```

---

### GET /ready

Readiness probe. Verifica conectividad a BD y estado del consumer Kafka.

**Response 200 (todo OK):**
```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "kafka": "disabled"
  }
}
```

**Response 503 (BD no disponible):**
```json
{
  "status": "error",
  "checks": {
    "database": "error: connection refused",
    "kafka": "disabled"
  }
}
```

`kafka` aparece como `"disabled"` cuando `KAFKA_CONSUMER_ENABLED=false`.

---

## Notas de implementación

### Idempotencia
Cada envío se registra en `notification_log` con `(event_id, channel)` como clave única. Si el mismo `event_id` llega dos veces (redelivery Kafka), el segundo intento se ignora silenciosamente (`status=skipped`).

### Plantillas
Los cuerpos de los emails se renderizan con Jinja2. El texto plano se usa como `body` en la notificación in-app. El HTML va como cuerpo del email. Ambos están en `app/templates/`.

### Logging PII
Los campos `email_address`, `phone_number` y `fcm_token` nunca se loguean en claro. Los logs usan `***` para enmascararlos.

### Rate limiting
60 peticiones por minuto por `user_id` (extraído del JWT) o por IP si no hay JWT. Al exceder: `429 Too Many Requests` con header `Retry-After: 60`.
