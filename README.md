# notification-services

Microservicio de notificaciones transaccionales de TravelHub. Envía emails y push notifications a usuarios cuando ocurren eventos de reserva, pago o cuenta.

**Curso:** MISW4501/4502 — Uniandes · **Grupo:** 9

---

## Índice

- [Arquitectura](#arquitectura)
- [Inicio rápido (local)](#inicio-rápido-local)
- [Variables de entorno](#variables-de-entorno)
- [Tests](#tests)
- [Migraciones](#migraciones)
- [Deploy a GCP](#deploy-a-gcp)
- [Smoke test en DEV](#smoke-test-en-dev)
- [Documentación adicional](#documentación-adicional)

---

## Arquitectura

```
API Gateway ──► /api/v1/notifications/*    (público, JWT — preferences, histórico in-app)
                  │
                  ▼
           notification-services
                  ▲
                  │ HTTP server-to-server (X-Internal-Token, NO via gateway)
                  │
   ┌──────────────┼──────────────────────────────────────────────┐
   │              │                                              │
   POST /internal           POST /internal/welcome      POST /events ← NUEVO 2026-05-16
   pms-sync-worker          user-services               workers booking/payment/user
   (conflict, error, sync)  (welcome post-register)     (envelope estándar TravelHub)
                  │
                  ▼
    NotificationService.process_event(envelope)
    ├── TemplateService   (Jinja2 — booking_*, payment_*, user_*)
    ├── PreferenceService (PostgreSQL — toggles por canal)
    └── SenderFactory     (Strategy)
        ├── SendGridSender   (email — operativo)
        ├── FCMSender        (push — placeholder, FCM credentials pendientes)
        ├── SMSStubSender    (no implementado)
        └── WhatsAppStubSender (no implementado)
```

> **Cambio arquitectónico 2026-05-16 (A):** este servicio ya NO consume `booking-events` / `payment-events` / `user-events` de Kafka. Los workers de cada dominio (booking, payment, user) llaman vía HTTP al nuevo endpoint `POST /api/v1/notifications/events` con un envelope simplificado (`event_type`, `user_id`, `payload`). Internamente se reutiliza el mismo `process_event()` que usaba el consumer Kafka, así que renderizado y plantillas no cambian. Detalle: [docs/api.md](docs/api.md) § *POST /api/v1/notifications/events*.
>
> **Cambio arquitectónico 2026-05-16 (B):** **opt-out por defecto + fallback a `users.email`**. Antes, un viajero sin fila en `notification_preference` recibía `channel_skipped` y nada llegaba — obligaba a disparar `user.welcome` antes de cualquier `booking/payment`. Ahora `NotificationService` resuelve el destinatario así: si `pref.email_address` está seteado se usa; si no, query `SELECT email, nombre FROM users WHERE id=:uid AND activo=true` (misma BD `travelhub` que user-services). Los defaults del modelo (`email_enabled=true`, `push_enabled=true`) ya hacían el resto. El viajero apaga canales con `PUT /api/v1/notifications/preferences` — eso sí se respeta. Trade-off: notification queda acoplado al schema de `users.email` / `users.nombre` / `users.activo`.

### Patrones aplicados

| Patrón | Dónde |
|---|---|
| Strategy | `app/senders/` — selección de canal por preferencias |
| Chain of Responsibility | `app/middleware/` — JWT → RateLimit → RBAC (exempt: `/health`, `/internal*`, `/events`, `/admin/test-event`) |
| Circuit Breaker | `app/resilience/circuit_breaker.py` — protege SendGrid / FCM |
| Dispatcher / Command | `app/kafka/dispatcher.py` — `event_type` → handler. Reusado tanto por el consumer Kafka como por `/events` y `/admin/test-event` (cero duplicación de lógica de envío). |
| Idempotencia | `notification_log.event_id + channel` UNIQUE |

### Stack

| Componente | Versión |
|---|---|
| Python | 3.11 |
| FastAPI | 0.111.0 |
| SQLAlchemy async | 2.0.30 |
| asyncpg | ≥ 0.30.0 |
| confluent-kafka | 2.4.0 |
| SendGrid | 6.11.0 |
| Firebase Admin (FCM) | 6.5.0 |
| Jinja2 | 3.1.4 |

---

## Inicio rápido (local)

### Prerequisitos

- Docker Desktop corriendo
- Python 3.11 + pip

### Con Docker Compose (recomendado)

```bash
# 1. Variables de entorno
cp .env.example .env
# Editar .env si necesitas cambiar puertos o credenciales

# 2. Levantar postgres + servicio
docker compose up --build

# 3. Verificar
curl http://localhost:8004/health
# → {"status": "ok", "service": "notification-services", "env": "local"}

curl http://localhost:8004/ready
# → {"status": "ok", "checks": {"database": "ok", "kafka": "disabled"}}
```

### Sin Docker (venv)

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# Requiere PostgreSQL local corriendo
export DATABASE_URL="postgresql+asyncpg://travelhub_app:localpass@localhost:5432/travelhub_notifications?ssl=disable"
export KAFKA_CONSUMER_ENABLED=false
export INTERNAL_NOTIFY_TOKEN=local-token
export SENDGRID_API_KEY=SG.test
export SENDGRID_SANDBOX=true
export FCM_CREDENTIALS_JSON=""
export FCM_PROJECT_ID=local
export APP_URL=http://localhost:3000
export SUPPORT_EMAIL=soporte@travelhub.app

alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8004 --reload
```

---

## Variables de entorno

| Variable | Requerida | Descripción | Ejemplo |
|---|---|---|---|
| `DATABASE_URL` | ✅ | Conexión PostgreSQL async | `postgresql+asyncpg://user:pass@host/db?ssl=disable` |
| `KAFKA_CONSUMER_ENABLED` | — | Activa el consumer Kafka. **`false` por defecto desde 2026-05-16** — los eventos de booking/payment/user llegan ahora por HTTP a `/events`. | `false` |
| `KAFKA_BOOTSTRAP_SERVERS` | si Kafka activo | Brokers (solo si decides reactivar el consumer) | `10.10.3.3:9092` |
| `INTERNAL_NOTIFY_TOKEN` | ✅ | Token para todos los endpoints internos (`/internal`, `/internal/welcome`, `/events`, `/admin/test-event`) | desde Secret Manager |
| `SENDGRID_API_KEY` | ✅ | Clave API de SendGrid | `SG.xxx` |
| `SENDGRID_SANDBOX` | — | `true` simula envío sin email real | `true` en DEV |
| `FCM_CREDENTIALS_JSON` | — | Path o JSON del SA de Firebase | `/secrets/fcm-sa.json` |
| `JWT_ISSUER` | ✅ | Issuer esperado en tokens JWT | `https://auth.travelhub.app` |
| `JWT_AUDIENCE` | ✅ | Audience esperado | `travelhub-api` |
| `APP_URL` | ✅ | URL base de la app (para links en emails) | `https://app.travelhub.app` |

Ver `.env.example` para la lista completa.

---

## Tests

```bash
source venv/bin/activate

# Ejecutar con cobertura
pytest --cov=app --cov-report=term-missing --cov-fail-under=70

# Solo tests unitarios
pytest tests/unit/ -v

# Solo tests de integración
pytest tests/integration/ -v

# Un test específico
pytest tests/unit/test_circuit_breaker.py -v
```

**Cobertura actual:** 79% (mínimo requerido: 70%)

### Lint

```bash
ruff check app/ tests/
flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203
```

---

## Migraciones

```bash
# Aplicar todas las migraciones
alembic upgrade head

# Ver estado actual
alembic current

# Crear nueva migración (tras cambiar modelos)
alembic revision --autogenerate -m "descripcion del cambio"

# Revertir una migración
alembic downgrade -1
```

La migración inicial (`001`) crea las tablas:
- `notification_preference` — preferencias de canal por usuario
- `notification` — historial in-app consultable por el usuario
- `notification_log` — auditoría técnica de envíos (idempotencia)

---

## Deploy a GCP

### DEV — Cloud Run directo

```bash
# Requiere gcloud autenticado con cuenta con permisos en gen-lang-client-0930444414
bash deploy/deploy-dev.sh

# Smoke test post-deploy
curl https://notification-services-ridyy4wz4q-uc.a.run.app/health
```

### PROD — Cloud Deploy canary

El deploy a PROD se gatilla automáticamente al hacer push a `main` vía GitHub Actions.
El pipeline `notification-services-pipeline` aplica canary: **10% → 50% → 100%** con aprobación manual.

```bash
# Ver estado del pipeline (requiere acceso a travelhub-prod-492116)
gcloud deploy delivery-pipelines describe notification-services-pipeline \
  --region=us-central1 \
  --project=travelhub-prod-492116
```

### CI/CD — GitHub Actions

| Trigger | Job |
|---|---|
| PR a `main` o `develop` | Tests + lint + docker build |
| Push a `develop` o `feature/**` | Tests + lint + deploy DEV |
| Push a `main` | Tests + lint + deploy PROD (canary) |

---

## Smoke test en DEV

### 1. Health check

```bash
curl https://notification-services-ridyy4wz4q-uc.a.run.app/health
```

### 2. Disparar notificación vía HTTP (recomendado — sin Kafka, sin JWT)

Este es el flujo que usan los workers de booking, payment y user-services. Sirve también como smoke E2E.

```bash
# Token y URL (DEV)
export INTERNAL_TOKEN=$(gcloud secrets versions access latest \
  --secret=dev-travelhub-internal-notify-token --project=gen-lang-client-0930444414)
export NOTIF_URL="https://notification-services-ridyy4wz4q-uc.a.run.app/api/v1/notifications/events"

# user_id real existente en user-services. Si no tiene preferencia configurada,
# el primer user.welcome la crea automáticamente con el email del payload.
export USER_ID="ba2d8b89-aa6d-48c7-b048-54eab2f25d7a"

# 2.1 — Opcional: bootstrap del welcome (no es estrictamente necesario desde el cambio
#       opt-out — si el user_id existe en `users` el booking ya le llega).
#       Sirve si quieres además guardar el `email_address` en notification_preference o
#       enviar el correo de bienvenida.
curl -sS -X POST "$NOTIF_URL" \
  -H "X-Internal-Token: $INTERNAL_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"event_type\": \"user.welcome\",
    \"user_id\": \"$USER_ID\",
    \"payload\": { \"email\": \"viajero@ejemplo.com\", \"full_name\": \"María Pérez\" }
  }"

# 2.2 — Reserva confirmada (funciona aunque NO hayas corrido 2.1 — fallback a users.email)
curl -sS -X POST "$NOTIF_URL" \
  -H "X-Internal-Token: $INTERNAL_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"event_type\": \"booking.confirmed\",
    \"user_id\": \"$USER_ID\",
    \"payload\": {
      \"booking_id\": \"660e8400-e29b-41d4-a716-446655440001\",
      \"hotel_name\": \"Hotel Bogotá Plaza\",
      \"check_in\": \"2026-06-15T14:00:00Z\",
      \"check_out\": \"2026-06-18T11:00:00Z\",
      \"total\": 450000,
      \"currency\": \"COP\"
    }
  }"

# Cada llamada → HTTP 202 + email entregado vía SendGrid.
# Ver curls completos por cada event_type (welcome, password_reset, booking.confirmed/cancelled/reminder,
# payment.completed/failed) en docs/api.md § "POST /api/v1/notifications/events".
```

Para PROD usar:
- URL: `https://notification-services-qhweqfkejq-uc.a.run.app/api/v1/notifications/events`
- Secret: `--secret=prod-travelhub-internal-notify-token --project=travelhub-prod-492116`

### 3. Validar que el email salió

```bash
# Buscar los logs recientes en Cloud Logging. El event_id se genera server-side
# con formato http_<event_type>_<uuid4> — se devuelve en la respuesta HTTP de /events.
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=notification-services AND textPayload:"events_ingest_received"' \
  --project=gen-lang-client-0930444414 --limit=10 --freshness=5m --order=desc \
  --format='value(timestamp,textPayload)'

# Resultado esperado (2 líneas por evento):
# ... events_ingest_received event_type=booking.confirmed event_id=http_booking_confirmed_<uuid>
# ... email_sent
```

> En DEV `SENDGRID_SANDBOX=false` y `SENDGRID_FROM_EMAIL=noreply@apitravelhub.site` desde 2026-05-16 — los emails llegan al buzón real. Si los recibes en spam, marca como "no es spam" para entrenar al filtro.

### 4. Endpoints públicos (con JWT, vía gateway)

Las rutas de **preferencias** e **histórico in-app** sí pasan por API Gateway con JWT del usuario. Detalle completo en [docs/api.md](docs/api.md) § *Endpoints públicos*.

```bash
TOKEN=$(curl -s -X POST https://apitravelhubdev.site/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"tu@email.com","password":"tupassword"}' | jq -r '.access_token')

# Ver mis preferencias
curl -H "Authorization: Bearer $TOKEN" \
  https://apitravelhubdev.site/api/v1/notifications/preferences

# Listar mis notificaciones (las creadas por el smoke aparecen aquí)
curl -H "Authorization: Bearer $TOKEN" \
  "https://apitravelhubdev.site/api/v1/notifications?limit=10"
```

---

## Documentación adicional

| Documento | Contenido |
|---|---|
| [docs/api.md](docs/api.md) | Contratos completos de todos los endpoints |
| [docs/kafka-topics.md](docs/kafka-topics.md) | Topics, payloads y guía de prueba local |
| [docs/ADR-001-event-schema.md](docs/ADR-001-event-schema.md) | Decisión: envelope estándar de eventos Kafka |
| [docs/ADR-002-internal-http-pms.md](docs/ADR-002-internal-http-pms.md) | Decisión: HTTP interno vs Kafka para pms-sync-worker |
| [CLAUDE.md](CLAUDE.md) | Instrucciones completas de arquitectura para Claude Code |
