# CLAUDE.md — notification-services (TravelHub Grupo 9)

> Instrucciones para Claude Code CLI. Ejecutar en orden. No omitir pasos.
> Proyecto: TravelHub — Grupo 9 | Curso: MISW4501 — Uniandes
> Repo: `ecruzs-uniandes/miso-travelhub-notification-services`

---

## 0. Reglas de trabajo

- No ejecutar acciones hasta que el usuario confirme explícitamente cada paso mayor.
- Avanzar fase por fase. No saltar adelante.
- Código Python: FastAPI + SQLAlchemy 2.0 async + pytest-asyncio.
- Mantener consistencia con el resto del monorepo (`user-services`, `pms-integration-services`, `pms-sync-worker`).
- Cobertura mínima de tests: **≥ 70%**.
- Lint obligatorio: `flake8` + `ruff`.
- **No tocar** los demás repos del monorepo. Este servicio es independiente.
- Usar `set -euo pipefail` en todos los scripts bash.

---

## 1. Resumen del Servicio

`notification-services` es el microservicio responsable del envío de notificaciones transaccionales a usuarios de TravelHub a través de múltiples canales: **Email**, **Push**, **SMS** y **WhatsApp**. En el MVP solo Email y Push están implementados; SMS y WhatsApp quedan como Strategy stub.

### Responsabilidades

1. **Consumir** eventos desde 3 topics Kafka publicados por otros servicios (`booking-events`, `payment-events`, `user-events`).
2. **Recibir** llamadas HTTP internas desde `pms-sync-worker` (NO consume `pms-events` por Kafka — `pms-sync-worker` notifica vía HTTP).
3. **Renderizar** plantillas Jinja2 según tipo de evento.
4. **Enviar** la notificación por los canales habilitados según preferencias del usuario (Strategy pattern).
5. **Persistir** un registro en BD (`notification` + `notification_log`) para que el usuario pueda consultar su histórico in-app.
6. **Exponer** endpoints públicos (vía API Gateway) para que el usuario gestione sus preferencias y consulte su histórico.

### ASRs que aplica

- **AH005** — Procesamiento de pago en ≤ 3s: notification-services recibe el evento `payment.completed` de forma asíncrona, no bloquea el flujo del usuario.
- **AH015** — Disponibilidad / observabilidad: el servicio publica métricas y consume eventos sin acoplarse al productor.

### Patrones de diseño aplicados

| Patrón | Aplicación |
|---|---|
| **Strategy (GoF)** | Selección de canal de envío (Email / Push / SMS / WhatsApp) |
| **Template Method (GoF)** | Plantillas Jinja2 parametrizables |
| **Observer (GoF) / EDD** | Consumer Kafka suscrito a múltiples topics |
| **Command (GoF)** | Cada notificación encapsulada como comando con idempotencia (`event_id`) |
| **Circuit Breaker** | Protección ante caídas de SendGrid / FCM |

---

## 2. Stack Tecnológico

| Componente | Tecnología | Versión |
|---|---|---|
| Lenguaje | Python | 3.11 |
| Framework HTTP | FastAPI | 0.111.0 |
| Server ASGI | uvicorn[standard] | 0.30.1 |
| ORM | SQLAlchemy (async) | 2.0.30 |
| Driver PostgreSQL | asyncpg | **≥ 0.30.0** (bug SSL en versiones anteriores) |
| Migraciones | Alembic | 1.13.1 |
| Validación | Pydantic | 2.7.1 |
| Settings | pydantic-settings | 2.3.1 |
| Kafka | confluent-kafka | 2.4.0 |
| Templates | Jinja2 | 3.1.4 |
| HTTP Client | httpx | 0.27.0 |
| JWT | python-jose[cryptography] | 3.3.0 |
| Email Provider | sendgrid | 6.11.0 |
| Push Provider | firebase-admin | 6.5.0 |
| Tests | pytest + pytest-asyncio | 8.2.0 / 0.23.7 |
| Lint | ruff + flake8 | latest |
| Container | Docker → Cloud Run | — |
| Puerto local | **8004** | (8001=pms-int, 8002=pms-sync, 8003=user) |

---

## 3. Decisiones técnicas validadas (NO cambiar sin acuerdo del equipo)

1. **Topics Kafka que consume:** `booking-events`, `payment-events`, `user-events`. NO consume `pms-events` — `pms-sync-worker` notifica vía HTTP interno.
2. **DLQ propio:** `notification-dlq` (1 partición). Crear en VM Kafka.
3. **Endpoint interno HTTP:** `POST /api/v1/notifications/internal` — invocado por `pms-sync-worker`. NO público (gateway no lo rutea).
4. **Email provider:** SendGrid. API key en Secret Manager.
5. **Push provider:** Firebase Cloud Messaging (FCM). Service Account JSON en Secret Manager.
6. **SMS / WhatsApp:** Strategy stub. La interfaz existe pero la implementación devuelve `NotImplementedError` con log estructurado.
7. **Idioma:** solo español. Estructura preparada para i18n futuro (campo `locale` en plantilla).
8. **Plantillas:** Jinja2 hardcoded en `app/templates/`. NO en BD.
9. **Idempotencia:** UNIQUE constraint sobre `notification_log.event_id`.
10. **Reintentos:** 3 intentos con backoff exponencial. Tras fallar, mensaje va a `notification-dlq`.
11. **Persistencia in-app:** sí, los usuarios pueden consultar su histórico en la app.
12. **Schema de eventos Kafka:** JSON estándar `{event_id, event_type, occurred_at, user_id, payload}`.
13. **Networking GCP:** Direct VPC egress (NO VPC connector). Flag: `--network=travelhub-vpc --subnet=subnet-services --vpc-egress=private-ranges-only`.
14. **PROD sin Kafka todavía:** desplegar con feature flag `KAFKA_CONSUMER_ENABLED=false`. Cuando Kafka PROD exista, se cambia el flag y se redespliega (sin recompilar).
15. **DB local:** `travelhub_notifications` (puerto 5432). DB DEV/PROD: tablas `notification_*` en BD compartida `travelhub`.
16. **Tablas con prefijo `notification_*`** para no chocar con tablas de otros servicios en la BD compartida de DEV.
17. **JWT validation:** mismo patrón que `pms-integration-services` — decode no-verify (el gateway ya validó firma + iss + aud + exp). El backend valida claims de negocio (RBAC, MFA donde aplique).

---

## 4. Estructura del repositorio

```
miso-travelhub-notification-services/
├── README.md
├── CLAUDE.md                              # este archivo
├── pyproject.toml                         # ruff config
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── docker-compose.yml                     # local-only (postgres + servicio)
├── .env.example
├── .gitignore
├── .dockerignore
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
├── app/
│   ├── __init__.py
│   ├── main.py                            # FastAPI app + startup tasks
│   ├── config.py                          # pydantic-settings
│   ├── database.py                        # async engine + session
│   ├── models/
│   │   ├── __init__.py
│   │   ├── notification.py                # Notification, NotificationLog
│   │   └── preference.py                  # NotificationPreference
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── events.py                      # Kafka event schemas (Pydantic)
│   │   ├── notification.py
│   │   ├── preference.py
│   │   └── internal.py                    # InternalNotificationRequest
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                        # JWT decode, get_current_user
│   │   ├── public.py                      # /notifications, /preferences (gateway)
│   │   ├── internal.py                    # /internal (solo VPC interna)
│   │   └── health.py                      # /health, /ready
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── chain.py                       # Chain of Responsibility wrapper
│   │   ├── rate_limit.py
│   │   ├── rbac.py
│   │   └── jwt_decode.py
│   ├── kafka/
│   │   ├── __init__.py
│   │   ├── consumer.py                    # multi-topic consumer (asyncio)
│   │   ├── dispatcher.py                  # event_type -> handler
│   │   └── handlers/
│   │       ├── __init__.py
│   │       ├── booking.py
│   │       ├── payment.py
│   │       └── user.py
│   ├── senders/
│   │   ├── __init__.py
│   │   ├── base.py                        # NotificationSender ABC
│   │   ├── factory.py                     # SenderFactory (Strategy)
│   │   ├── email_sendgrid.py
│   │   ├── push_fcm.py
│   │   ├── sms_stub.py
│   │   └── whatsapp_stub.py
│   ├── templates/                         # Jinja2 templates
│   │   ├── booking_confirmed.email.html
│   │   ├── booking_confirmed.email.txt
│   │   ├── booking_confirmed.push.json
│   │   ├── booking_cancelled.email.html
│   │   ├── booking_cancelled.email.txt
│   │   ├── booking_cancelled.push.json
│   │   ├── booking_reminder.email.html
│   │   ├── booking_reminder.email.txt
│   │   ├── payment_completed.email.html
│   │   ├── payment_completed.email.txt
│   │   ├── payment_failed.email.html
│   │   ├── payment_failed.email.txt
│   │   ├── user_welcome.email.html
│   │   ├── user_welcome.email.txt
│   │   ├── user_password_reset.email.html
│   │   ├── user_password_reset.email.txt
│   │   ├── pms_sync_conflict.email.html
│   │   ├── pms_sync_conflict.email.txt
│   │   └── pms_sync_error.email.html
│   ├── services/
│   │   ├── __init__.py
│   │   ├── notification_service.py        # orquestador (template + sender)
│   │   ├── preference_service.py
│   │   └── template_service.py            # carga y render Jinja2
│   ├── resilience/
│   │   ├── __init__.py
│   │   └── circuit_breaker.py
│   └── utils/
│       ├── __init__.py
│       ├── logger.py                      # structured logging
│       └── tracing.py                     # correlation IDs
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_senders.py
│   │   ├── test_dispatcher.py
│   │   ├── test_template_service.py
│   │   ├── test_preference_service.py
│   │   ├── test_circuit_breaker.py
│   │   └── test_middleware.py
│   ├── integration/
│   │   ├── test_public_api.py
│   │   ├── test_internal_api.py
│   │   ├── test_kafka_handlers.py
│   │   └── test_db_models.py
│   └── fixtures/
│       └── sample_events.py
├── scripts/
│   ├── create-topics.sh                   # idempotente: crea topics + DLQ
│   ├── run-migrations.sh
│   └── seed-dev.sh
├── deploy/
│   ├── deploy-dev.sh                      # gcloud CLI con direct VPC egress
│   ├── deploy-prod.sh                     # idem (apunta a proyecto PROD)
│   └── cloudbuild.yaml                    # migrations vía Cloud Run Job
├── .github/
│   └── workflows/
│       ├── ci.yml                         # tests + lint en PR
│       ├── deploy-dev.yml                 # push develop / feature/*
│       └── deploy-prod.yml                # push main → Cloud Deploy canary
└── docs/
    ├── ADR-001-event-schema.md
    ├── ADR-002-internal-http-pms.md
    ├── api.md
    └── kafka-topics.md
```

---

## 5. DDL — Modelo de datos

Todas las tablas con prefijo `notification_*` para coexistir con tablas de otros servicios en la DB compartida de GCP DEV.

```sql
-- =========================================
-- Tabla: notification_preference
-- Una fila por usuario. Toggles de canales.
-- =========================================
CREATE TABLE notification_preference (
    user_id            UUID PRIMARY KEY,
    email_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    push_enabled       BOOLEAN NOT NULL DEFAULT TRUE,
    sms_enabled        BOOLEAN NOT NULL DEFAULT FALSE,
    whatsapp_enabled   BOOLEAN NOT NULL DEFAULT FALSE,
    email_address      VARCHAR(255),       -- redundante con user-services pero evita join entre dominios
    phone_number       VARCHAR(20),
    fcm_token          VARCHAR(500),       -- token de push del dispositivo
    locale             VARCHAR(10) NOT NULL DEFAULT 'es',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notification_preference_updated ON notification_preference(updated_at);

-- =========================================
-- Tabla: notification
-- Histórico in-app que el usuario consulta.
-- Una fila por notificación lógica (multi-canal cuenta como una sola).
-- =========================================
CREATE TABLE notification (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID NOT NULL,
    event_type         VARCHAR(64) NOT NULL,        -- booking.confirmed, payment.completed, etc.
    title              VARCHAR(200) NOT NULL,
    body               TEXT NOT NULL,
    metadata           JSONB,                       -- IDs de booking, payment, etc.
    read_at            TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notification_user_created ON notification(user_id, created_at DESC);
CREATE INDEX idx_notification_user_unread ON notification(user_id) WHERE read_at IS NULL;

-- =========================================
-- Tabla: notification_log
-- Auditoría técnica de envíos por canal.
-- Permite idempotencia y retry tracking.
-- =========================================
CREATE TABLE notification_log (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id    UUID REFERENCES notification(id) ON DELETE CASCADE,
    event_id           VARCHAR(128) NOT NULL,       -- viene del evento Kafka, garantiza idempotencia
    channel            VARCHAR(20) NOT NULL,        -- email | push | sms | whatsapp
    template_code      VARCHAR(64) NOT NULL,        -- ej: booking_confirmed.email
    status             VARCHAR(20) NOT NULL,        -- pending | sent | failed | skipped
    provider_response  JSONB,                       -- respuesta cruda de SendGrid / FCM
    attempts           INT NOT NULL DEFAULT 0,
    error_message      TEXT,
    sent_at            TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (event_id, channel)                      -- idempotencia: mismo evento + mismo canal = una sola fila
);

CREATE INDEX idx_notification_log_status ON notification_log(status);
CREATE INDEX idx_notification_log_event ON notification_log(event_id);
```

### Notas sobre el modelo

- `notification_preference.email_address`, `phone_number`, `fcm_token` se replican aquí (no se hace join contra `user-services`). Se actualizan vía evento `user.profile_updated`.
- `notification_log.event_id + channel` UNIQUE garantiza idempotencia: si el mismo evento llega dos veces a Kafka, se intenta INSERT y se hace `ON CONFLICT DO NOTHING` → skip.
- `notification.metadata JSONB` guarda contexto del evento original (booking_id, payment_id, hotel_id, etc.) para que el frontend pueda hacer deep-linking.

---

## 6. Schema de eventos Kafka

Todos los eventos siguen este envelope JSON estándar:

```json
{
  "event_id": "evt_01HZX9...",
  "event_type": "booking.confirmed",
  "occurred_at": "2026-05-01T15:30:00Z",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": { ... }
}
```

### Topics que consume

| Topic | event_type esperados | Payload mínimo |
|---|---|---|
| `booking-events` | `booking.confirmed`, `booking.cancelled`, `booking.reminder` | `{booking_id, hotel_name, check_in, check_out, total}` |
| `payment-events` | `payment.completed`, `payment.failed` | `{payment_id, booking_id, amount, currency, provider}` |
| `user-events` | `user.welcome`, `user.password_reset`, `user.email_verification` | `{email, full_name, reset_token?}` |

### Eventos definidos como Pydantic schemas (`app/schemas/events.py`)

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal
from uuid import UUID

class EventEnvelope(BaseModel):
    event_id: str
    event_type: str
    occurred_at: datetime
    user_id: UUID
    payload: dict

class BookingConfirmedPayload(BaseModel):
    booking_id: UUID
    hotel_name: str
    check_in: datetime
    check_out: datetime
    total: float
    currency: str

class PaymentCompletedPayload(BaseModel):
    payment_id: UUID
    booking_id: UUID
    amount: float
    currency: str
    provider: Literal["stripe", "mercadopago", "paypal"]

class UserWelcomePayload(BaseModel):
    email: str
    full_name: str

# ... resto de payloads
```

Si el `event_type` no está registrado en el dispatcher → log warning, ack del mensaje, no DLQ (no es un error técnico, es un evento que aún no nos interesa).

---

## 7. Endpoints

### 7.1 Endpoints públicos (vía API Gateway, ruta `/api/v1/notifications/*`)

Todos requieren JWT válido (gateway ya validó firma + iss + aud + exp).

| Método | Ruta | Descripción | Roles |
|---|---|---|---|
| GET | `/api/v1/notifications` | Lista mis notificaciones (paginado, ?unread_only=true) | traveler, hotel_admin |
| POST | `/api/v1/notifications/{id}/read` | Marca como leída | traveler, hotel_admin |
| POST | `/api/v1/notifications/read-all` | Marca todas como leídas | traveler, hotel_admin |
| GET | `/api/v1/notifications/preferences` | Lee mis preferencias | traveler, hotel_admin |
| PUT | `/api/v1/notifications/preferences` | Actualiza toggles + email/phone/fcm_token | traveler, hotel_admin |
| GET | `/health` | Liveness | público |
| GET | `/ready` | Readiness (incluye check de BD + Kafka si flag enabled) | público |

#### Contratos detallados

**GET `/api/v1/notifications`**
```
Query: ?limit=20&offset=0&unread_only=false
Response 200:
{
  "items": [
    {
      "id": "uuid",
      "event_type": "booking.confirmed",
      "title": "Tu reserva en Hotel X está confirmada",
      "body": "Check-in 15 de junio...",
      "metadata": { "booking_id": "uuid" },
      "read_at": null,
      "created_at": "2026-05-01T10:00:00Z"
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
Errores: 401 (JWT inválido), 403 (rol no autorizado).
```

**PUT `/api/v1/notifications/preferences`**
```
Body:
{
  "email_enabled": true,
  "push_enabled": true,
  "sms_enabled": false,
  "whatsapp_enabled": false,
  "email_address": "user@example.com",
  "phone_number": "+573001234567",
  "fcm_token": "..."
}
Response 200: objeto preferences actualizado
Errores: 400 (validación), 401, 403.
```

### 7.2 Endpoint interno (NO público, solo VPC interna)

| Método | Ruta | Descripción | Caller |
|---|---|---|---|
| POST | `/api/v1/notifications/internal` | Disparo síncrono de notificación | `pms-sync-worker` |

**POST `/api/v1/notifications/internal`**
```
Body:
{
  "type": "pms_sync_conflict" | "pms_sync_error" | "pms_sync_complete",
  "user_id": "uuid",                  // hotel_admin del hotel
  "hotel_id": "uuid",
  "details": { ... },
  "recipients": ["hotel_admin"]
}
Response 202 Accepted: { "notification_id": "uuid", "channels_sent": ["email"] }
Errores: 400 (payload inválido), 500 (fallo proveedor).
```

**Seguridad del endpoint interno:** este endpoint NO está en el OpenAPI del gateway. Solo es alcanzable desde la subnet `subnet-services` (validado por firewall + IP source check en middleware). Adicionalmente, requiere header `X-Internal-Token` con valor leído desde Secret Manager (`${PREFIX}-internal-notify-token`).

---

## 8. Chain of Responsibility (middleware FastAPI)

Mismo patrón que `pms-integration-services` y `user-services`. Orden:

```
Request
  ↓
[1] JWTDecodeMiddleware  → decode no-verify, extrae claims a request.state
  ↓
[2] RateLimitMiddleware  → 60 req/min por user_id/IP → 429 si excede
  ↓
[3] RBACMiddleware       → valida role vs ruta → 403 si no permitido
  ↓
Handler
```

- Las rutas `/health`, `/ready` y `/internal` quedan exentas de JWT (el internal usa otro mecanismo).
- MFA filter NO aplica aquí (notification-services no maneja datos sensibles que requieran step-up).

---

## 9. Senders (Strategy pattern)

```python
# app/senders/base.py
from abc import ABC, abstractmethod

class NotificationSender(ABC):
    @abstractmethod
    async def send(self, recipient: str, subject: str, body: str, metadata: dict) -> dict:
        """Retorna provider_response como dict. Lanza excepción si falla."""
        ...

# app/senders/factory.py
def get_sender(channel: str) -> NotificationSender:
    return {
        "email": SendGridSender(),
        "push": FCMSender(),
        "sms": SMSStubSender(),
        "whatsapp": WhatsAppStubSender(),
    }[channel]
```

### SendGrid (email)

- API key: variable `SENDGRID_API_KEY` desde Secret Manager.
- From address: `noreply@travelhub.app` (configurable en env).
- Sandbox mode en DEV (`SENDGRID_SANDBOX=true` no hace envío real).

### FCM (push)

- Service account JSON: variable `FCM_CREDENTIALS_JSON` desde Secret Manager.
- Si el `fcm_token` del usuario está vacío → status `skipped`, no es error.

### SMS / WhatsApp (stub)

```python
class SMSStubSender(NotificationSender):
    async def send(self, recipient, subject, body, metadata):
        logger.warning("sms_stub_invoked", extra={"recipient": recipient, "body_len": len(body)})
        raise NotImplementedError("SMS provider not configured for MVP")
```

El dispatcher captura `NotImplementedError` → status `skipped`, no DLQ.

---

## 10. Kafka Consumer

### Configuración

```python
# app/kafka/consumer.py
KAFKA_CONFIG = {
    "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
    "group.id": "notification-services-group",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,  # commit manual tras procesamiento exitoso
    "max.poll.interval.ms": 300000,
}

TOPICS = ["booking-events", "payment-events", "user-events"]
```

### Flujo

1. Poll mensaje.
2. Deserializar a `EventEnvelope`. Si falla → DLQ (`notification-dlq`) + log error + commit.
3. Buscar handler en dispatcher por `event_type`. Si no existe → log warning + commit (no DLQ).
4. Ejecutar handler:
   - Cargar preferencias del usuario.
   - Renderizar plantilla(s) según canales habilitados.
   - Insertar fila en `notification` + `notification_log` (con `ON CONFLICT DO NOTHING` por `event_id + channel`).
   - Si la fila ya existía (conflict) → log + commit (idempotente, ya se procesó).
   - Si es nueva → llamar al sender. Si falla → retry con backoff exponencial (3 intentos: 2s, 4s, 8s).
   - Tras 3 fallos → status `failed`, publicar mensaje a `notification-dlq` con metadata, commit del original.
5. Commit offset.

### Feature flag PROD

```python
if settings.KAFKA_CONSUMER_ENABLED:
    asyncio.create_task(consumer_loop())
else:
    logger.warning("kafka_consumer_disabled", env=settings.ENV)
```

`KAFKA_CONSUMER_ENABLED=false` en PROD hasta que la VM Kafka exista. La app sigue sirviendo endpoints HTTP normalmente.

---

## 11. Plantillas Jinja2

Convención de nombre: `{event_type_with_underscores}.{channel}.{ext}`

Ejemplos:
- `booking_confirmed.email.html`
- `booking_confirmed.email.txt`
- `booking_confirmed.push.json`

### Variables disponibles en todas las plantillas

```
{{ user.full_name }}
{{ user.email }}
{{ event.occurred_at_human }}    # formato: "1 de mayo de 2026, 10:00 AM"
{{ payload.* }}                  # campos del payload del evento
{{ links.app_url }}              # https://app.travelhub.app
{{ links.support_email }}
```

### Ejemplo: `booking_confirmed.email.html`

```html
<!DOCTYPE html>
<html lang="es">
<body>
  <h1>¡Hola {{ user.full_name }}!</h1>
  <p>Tu reserva en <strong>{{ payload.hotel_name }}</strong> está confirmada.</p>
  <ul>
    <li>Check-in: {{ payload.check_in }}</li>
    <li>Check-out: {{ payload.check_out }}</li>
    <li>Total: {{ payload.total }} {{ payload.currency }}</li>
  </ul>
  <p><a href="{{ links.app_url }}/bookings/{{ payload.booking_id }}">Ver detalles</a></p>
</body>
</html>
```

### Ejemplo: `booking_confirmed.push.json`

```json
{
  "title": "Reserva confirmada",
  "body": "Tu reserva en {{ payload.hotel_name }} está lista. Check-in {{ payload.check_in_short }}.",
  "data": {
    "deep_link": "/bookings/{{ payload.booking_id }}"
  }
}
```

---

## 12. Variables de entorno

`.env.example`:

```bash
# === App ===
ENV=local                              # local | dev | prod
LOG_LEVEL=INFO
PORT=8004

# === Database ===
DATABASE_URL=postgresql+asyncpg://travelhub_app:secret@postgres:5432/travelhub_notifications?ssl=disable
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10

# === Kafka ===
KAFKA_CONSUMER_ENABLED=true
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_CONSUMER_GROUP=notification-services-group
KAFKA_DLQ_TOPIC=notification-dlq

# === JWT ===
JWT_ISSUER=https://auth.travelhub.app
JWT_AUDIENCE=travelhub-api
# (solo decode no-verify; el gateway ya validó firma)

# === Internal endpoint ===
INTERNAL_NOTIFY_TOKEN=change-me-in-secret-manager

# === Email (SendGrid) ===
SENDGRID_API_KEY=SG.xxx
SENDGRID_FROM_EMAIL=noreply@travelhub.app
SENDGRID_FROM_NAME=TravelHub
SENDGRID_SANDBOX=true                  # false en prod

# === Push (FCM) ===
FCM_CREDENTIALS_JSON=/secrets/fcm-sa.json
FCM_PROJECT_ID=gen-lang-client-0930444414

# === App links (para plantillas) ===
APP_URL=https://app.travelhub.app
SUPPORT_EMAIL=soporte@travelhub.app

# === Resilience ===
RETRY_MAX_ATTEMPTS=3
RETRY_BACKOFF_BASE=2
CB_FAILURE_THRESHOLD=5
CB_RECOVERY_TIMEOUT=30
```

En GCP, los secretos van a Secret Manager con naming `${PREFIX}-<secret-name>`:
- `dev-travelhub-sendgrid-api-key`
- `dev-travelhub-fcm-credentials`
- `dev-travelhub-internal-notify-token`

---

## 13. Docker

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

EXPOSE 8004

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
```

### docker-compose.yml (LOCAL ONLY — usar solo para desarrollo aislado)

```yaml
# Para desarrollo en el monorepo, usar el compose de travelhub-local/.
# Este compose es para trabajar el servicio aislado.
version: "3.9"
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: travelhub_notifications
      POSTGRES_USER: travelhub_app
      POSTGRES_PASSWORD: localpass
    ports: ["5432:5432"]
    volumes: ["pg_data:/var/lib/postgresql/data"]

  notification-services:
    build: .
    ports: ["8004:8004"]
    environment:
      DATABASE_URL: postgresql+asyncpg://travelhub_app:localpass@postgres:5432/travelhub_notifications?ssl=disable
      KAFKA_CONSUMER_ENABLED: "false"
      ENV: local
    depends_on: [postgres]
    volumes: ["./app:/app/app"]
    command: uvicorn app.main:app --host 0.0.0.0 --port 8004 --reload

volumes:
  pg_data:
```

---

## 14. Tests

### Estructura mínima

- **unit/** — sin BD ni Kafka, mocks puros. ≥ 80% de los tests.
- **integration/** — con `pytest-asyncio` + base de datos en memoria (SQLite async) o testcontainers.

### Casos obligatorios

#### Unit
- `test_senders.py`: SendGrid OK, SendGrid falla → excepción; FCM con token vacío → skipped; SMSStub → NotImplementedError.
- `test_dispatcher.py`: cada `event_type` mapea al handler correcto; event_type desconocido → log warning, no excepción.
- `test_template_service.py`: render con todas las variables; falta variable → error claro.
- `test_circuit_breaker.py`: abre tras N fallos, half-open tras timeout, cierra tras éxito.

#### Integration
- `test_public_api.py`: GET notifications con JWT válido, sin JWT → 401, rol incorrecto → 403, paginación.
- `test_internal_api.py`: header válido → 202, header inválido → 401, payload inválido → 400.
- `test_kafka_handlers.py`: evento booking → fila en `notification` + `notification_log`; mismo `event_id` dos veces → una sola fila (idempotencia).
- `test_db_models.py`: UNIQUE constraint sobre `(event_id, channel)` activo.

### Ejecución

```bash
# Local
pytest --cov=app --cov-report=term-missing --cov-fail-under=70

# CI (GitHub Actions)
ruff check app/ tests/
flake8 app/ tests/
pytest --cov=app --cov-report=xml --cov-fail-under=70
```

---

## 15. Migraciones (Alembic)

`alembic/env.py` debe configurarse en modo async:

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

def run_migrations_online():
    asyncio.run(_run_async())

async def _run_async():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        await conn.run_sync(do_run_migrations)
```

Migración inicial: `alembic/versions/001_initial_schema.py` con las 3 tablas del DDL.

### Ejecución en cada ambiente

| Ambiente | Cómo |
|---|---|
| Local | `alembic upgrade head` directo |
| DEV (GCP) | `scripts/run-migrations.sh` desde laptop con Cloud SQL Proxy |
| PROD (GCP) | Cloud Run Job invocado desde `cloudbuild.yaml` (igual patrón que `user-services`) |

---

## 16. Scripts auxiliares

### `scripts/create-topics.sh`

Idempotente. Crea los 4 topics si no existen.

```bash
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
```

> **Nota:** este script crea los topics en el broker LOCAL (`travelhub-local/`). Para la VM Kafka en GCP, hay que coordinar con quien administra `travelhub-kafka` para agregarlos al `kafka-init` container o crearlos vía IAP tunnel.

---

## 17. Deploy a GCP

### `deploy/deploy-dev.sh`

```bash
#!/bin/bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-gen-lang-client-0930444414}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="notification-services"
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/travelhub/${SERVICE_NAME}:latest"

echo ">>> Building..."
gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}"

echo ">>> Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --network=travelhub-vpc \
  --subnet=subnet-services \
  --vpc-egress=private-ranges-only \
  --clear-vpc-connector \
  --port 8004 \
  --min-instances=1 \
  --max-instances=3 \
  --no-cpu-throttling \
  --set-env-vars "ENV=dev,KAFKA_CONSUMER_ENABLED=true,KAFKA_BOOTSTRAP_SERVERS=10.10.3.3:9092,JWT_ISSUER=https://auth.travelhub.app,JWT_AUDIENCE=travelhub-api,APP_URL=https://app.travelhub.app,SUPPORT_EMAIL=soporte@travelhub.app,SENDGRID_FROM_EMAIL=noreply@travelhub.app,SENDGRID_FROM_NAME=TravelHub,SENDGRID_SANDBOX=true,FCM_PROJECT_ID=${PROJECT_ID}" \
  --set-secrets "DATABASE_URL=dev-travelhub-notification-db-url:latest,SENDGRID_API_KEY=dev-travelhub-sendgrid-api-key:latest,FCM_CREDENTIALS_JSON=dev-travelhub-fcm-credentials:latest,INTERNAL_NOTIFY_TOKEN=dev-travelhub-internal-notify-token:latest" \
  --service-account "github-deploy-notification@${PROJECT_ID}.iam.gserviceaccount.com" \
  --allow-unauthenticated

echo ">>> Done. Recordar actualizar la URL en gateway/openapi-spec.yaml."
```

### `deploy/deploy-prod.sh`

Idéntico pero apuntando a `travelhub-prod-492116` y con `KAFKA_CONSUMER_ENABLED=false` hasta que Kafka PROD exista.

### Notas críticas de deploy

- **Usar Direct VPC egress** (`--network=travelhub-vpc --subnet=subnet-services --vpc-egress=private-ranges-only`), NO `--vpc-connector`. Si el servicio existía antes con connector, agregar `--clear-vpc-connector`.
- **Tag de servicio**: si la firewall rule `fw-allow-services-to-data` requiere tag, agregar `--tags=data-layer` al deploy. Validar con `gcloud compute firewall-rules describe fw-allow-services-to-data` qué espera.
- **Primer deploy en Cloud Deploy**: no hay revisión previa, así que canary se salta y va directo a 100%. Esto es esperado.

---

## 18. CI/CD (GitHub Actions + Workload Identity Federation)

### `.github/workflows/ci.yml` (en cada PR)

```yaml
name: CI
on: [pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: ruff check app/ tests/
      - run: flake8 app/ tests/
      - run: pytest --cov=app --cov-fail-under=70
```

### `.github/workflows/deploy-dev.yml` (push a `develop` o `feature/*`)

Auth vía WIF con SA `github-deploy-notification@gen-lang-client-0930444414.iam.gserviceaccount.com`. Pool `github-pool`, provider `github-provider`. Mismo patrón que los otros 3 servicios.

### `.github/workflows/deploy-prod.yml` (push a `main`)

Cloud Deploy pipeline `notification-services-pipeline` con canary 10→50→100. Migraciones via Cloud Run Job antes del deploy.

### Service Accounts a crear (una vez por proyecto)

```bash
# DEV
gcloud iam service-accounts create github-deploy-notification \
  --project=gen-lang-client-0930444414

# PROD
gcloud iam service-accounts create github-deploy-notification \
  --project=travelhub-prod-492116
```

Roles necesarios: `roles/run.admin`, `roles/iam.serviceAccountUser`, `roles/cloudbuild.builds.editor`, `roles/secretmanager.secretAccessor`, `roles/clouddeploy.releaser` (solo PROD).

WIF binding restringido al repo: `attribute.repository=ecruzs-uniandes/miso-travelhub-notification-services`.

---

## 19. Anti-patterns (NO hacer)

- **NO** crear endpoint público `POST /send`. Las notificaciones SOLO se disparan por:
  - Eventos Kafka (productores: booking, payment, user)
  - HTTP interno desde `pms-sync-worker`
- **NO** hacer joins SQL contra tablas de otros servicios. Si necesitas el email del usuario, viene en `notification_preference` (sincronizado vía evento `user.profile_updated`) o en el payload del evento.
- **NO** validar firma JWT en este servicio (ya lo hizo el gateway). Solo decode no-verify.
- **NO** hardcodear `gen-lang-client-0930444414` ni URLs de DEV en código. Todo via env vars.
- **NO** usar VPC connector para deploy. Direct VPC egress únicamente.
- **NO** usar `asyncpg < 0.30` (bug SSL en Cloud Run + direct VPC).
- **NO** retornar el cuerpo de la plantilla renderizada en respuestas HTTP. Las plantillas son internas.
- **NO** hacer logging de PII en claro (email, phone, FCM token). Usar `***` o hash truncado.
- **NO** consumir `pms-events` por Kafka. `pms-sync-worker` notifica vía HTTP interno; ese es el contrato vigente.
- **NO** publicar a Kafka desde este servicio (excepto al DLQ propio). notification-services es solo consumer + receptor HTTP, no productor de eventos de dominio.

---

## 20. Definición de Done

Una funcionalidad está "Done" cuando:

- [ ] Código en rama `feature/*` con commits convencionales (`feat:`, `fix:`, `chore:`).
- [ ] Tests unitarios + integración pasan localmente.
- [ ] Cobertura ≥ 70% (`pytest --cov-fail-under=70`).
- [ ] `ruff check` y `flake8` sin errores.
- [ ] CI verde en PR.
- [ ] Migraciones Alembic creadas si hubo cambios de schema (revisión cruzada con teammate).
- [ ] Variables de entorno nuevas documentadas en `.env.example` y en este CLAUDE.md.
- [ ] Secretos nuevos creados en Secret Manager (DEV y PROD).
- [ ] Deploy a DEV exitoso, smoke test pasando: `curl https://notification-services-<hash>-uc.a.run.app/health` → 200.
- [ ] Smoke test de envío real: publicar evento dummy a `booking-events`, verificar fila en `notification_log` con status `sent`.
- [ ] Documento `docs/api.md` actualizado si hubo cambios en endpoints.
- [ ] PR aprobado por al menos un teammate.

---

## 21. Fases de implementación (orden estricto)

> **Cada fase termina con un commit. Pedir confirmación al usuario antes de avanzar a la siguiente.**

### Fase 1 — Scaffolding y configuración base
1. Crear estructura de directorios completa (sección 4).
2. `requirements.txt`, `requirements-dev.txt`, `pyproject.toml` con ruff config, `.gitignore`, `.dockerignore`, `.env.example`.
3. `app/config.py` con pydantic-settings.
4. `app/database.py` con engine async + session.
5. `app/main.py` con FastAPI app vacía + endpoint `/health`.
6. `Dockerfile` + `docker-compose.yml` local.
7. Verificar: `docker compose up` levanta el servicio, `curl localhost:8004/health` → 200.

### Fase 2 — Modelos + Migraciones
1. `app/models/notification.py`, `app/models/preference.py`.
2. `alembic/env.py` async-aware.
3. Migración `001_initial_schema.py` con las 3 tablas.
4. `scripts/run-migrations.sh`.
5. Tests `test_db_models.py`.
6. Verificar: `alembic upgrade head` crea las 3 tablas.

### Fase 3 — Middleware y endpoints públicos
1. `app/middleware/jwt_decode.py`, `rate_limit.py`, `rbac.py`, `chain.py`.
2. `app/api/deps.py` — dependency injection del current_user.
3. `app/schemas/preference.py`, `notification.py`.
4. `app/services/preference_service.py`.
5. `app/api/public.py` con los 5 endpoints públicos.
6. Tests integración `test_public_api.py`.

### Fase 4 — Senders + Templates
1. `app/senders/base.py`, `factory.py`.
2. `app/senders/email_sendgrid.py`, `push_fcm.py`, `sms_stub.py`, `whatsapp_stub.py`.
3. Plantillas Jinja2 en `app/templates/` (al menos las 6 críticas: booking_confirmed, booking_cancelled, payment_completed, payment_failed, user_welcome, user_password_reset, en formato email html/txt).
4. `app/services/template_service.py`, `notification_service.py`.
5. `app/resilience/circuit_breaker.py`.
6. Tests unit `test_senders.py`, `test_template_service.py`, `test_circuit_breaker.py`.

### Fase 5 — Kafka consumer
1. `app/schemas/events.py` con todos los Pydantic event schemas.
2. `app/kafka/consumer.py`, `dispatcher.py`.
3. `app/kafka/handlers/booking.py`, `payment.py`, `user.py`.
4. Integración del consumer al startup de FastAPI con feature flag.
5. Tests integración `test_kafka_handlers.py` (con mock de Kafka).
6. `scripts/create-topics.sh`.
7. Verificar end-to-end con `travelhub-local/`: publicar evento manualmente, ver notificación creada.

### Fase 6 — Endpoint interno
1. `app/schemas/internal.py`.
2. `app/api/internal.py` con validación de `X-Internal-Token`.
3. Templates `pms_sync_conflict.email.*` y `pms_sync_error.email.*`.
4. Tests `test_internal_api.py`.

### Fase 7 — CI/CD
1. `.github/workflows/ci.yml`, `deploy-dev.yml`, `deploy-prod.yml`.
2. `deploy/deploy-dev.sh`, `deploy-prod.sh`, `cloudbuild.yaml`.
3. Documentar en `docs/api.md`, `docs/kafka-topics.md`, ADRs.

### Fase 8 — Deploy DEV + smoke test
1. Crear secretos en Secret Manager.
2. Crear SA + bindings WIF.
3. Primer deploy manual con `bash deploy/deploy-dev.sh`.
4. Actualizar URL en `gateway/openapi-spec.yaml` (coordinar con repo de infra).
5. Smoke test E2E: publicar evento, verificar email en SendGrid sandbox + fila en BD.

### Fase 9 — Deploy PROD
1. Solo cuando Kafka PROD exista, o con `KAFKA_CONSUMER_ENABLED=false`.
2. Cloud Deploy canary 10→50→100.
3. Smoke test idéntico a DEV.

---

## 22. Dependencias externas / coordinación con el equipo

Estos puntos requieren coordinación con teammates antes de cerrar el sprint:

1. **`booking-services`** (Andrés/Pablo/Omar): debe publicar a `booking-events` con el envelope estándar. Eventos: `booking.confirmed`, `booking.cancelled`, `booking.reminder`.
2. **`payments-services`** (Andrés/Pablo/Omar): debe publicar a `payment-events`. Eventos: `payment.completed`, `payment.failed`.
3. **`user-services`** (Edwin): hoy NO publica a Kafka. Hay que agregarle producer para `user.welcome`, `user.password_reset`, `user.email_verification`. **Esto está fuera del scope de este servicio pero es prerequisito para que las notificaciones de usuario funcionen.**
4. **VM Kafka (`travelhub-kafka`)**: agregar `booking-events`, `payment-events`, `user-events`, `notification-dlq` al `kafka-init` container o crearlos manualmente vía IAP tunnel.
5. **API Gateway**: agregar las rutas `/api/v1/notifications/*` al `openapi-spec.yaml` y redesplegar.
6. **`pms-sync-worker`**: ya espera el endpoint `POST /api/v1/notifications/internal`. Asegurar que la URL configurada en su deploy apunte a `notification-services`.

---

## 23. Referencias

- `CONTEXT_ROOT.md` — visión global del monorepo.
- `miso-travelhub-user-services/CLAUDE.md` — patrón de auth + JWKS + WIF (referencia).
- `miso-travelhub-pms-sync-worker/CLAUDE.md` — patrón Kafka consumer + circuit breaker.
- `miso-travelhub-pms-intergration-services/CLAUDE.md` — patrón Kafka producer.
- ADRs propios de este servicio (Fase 7) en `docs/`.

---

**Última actualización:** 2026-05-01
**Autor del documento:** Edwin Cruz Silva (Grupo 9)
