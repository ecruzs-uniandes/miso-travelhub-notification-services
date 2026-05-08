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
API Gateway ──► POST /api/v1/notifications/*     (público, JWT requerido)
                  │
                  ▼
           notification-services  ◄── POST /api/v1/notifications/internal  (pms-sync-worker, X-Internal-Token)
                  │
          ┌───────┴────────┐
          ▼                ▼
     Kafka consumer    HTTP handlers
     booking-events    internal/
     payment-events
     user-events
          │
          ▼
    NotificationService
    ├── TemplateService  (Jinja2)
    ├── PreferenceService (PostgreSQL)
    └── SenderFactory
        ├── SendGridSender  (email)
        ├── FCMSender       (push)
        ├── SMSStubSender   (no implementado)
        └── WhatsAppStubSender (no implementado)
```

### Patrones aplicados

| Patrón | Dónde |
|---|---|
| Strategy | `app/senders/` — selección de canal por preferencias |
| Chain of Responsibility | `app/middleware/` — JWT → RateLimit → RBAC |
| Circuit Breaker | `app/resilience/circuit_breaker.py` — protege SendGrid / FCM |
| Observer / EDD | `app/kafka/` — consumer suscrito a 3 topics |
| Command + Idempotencia | `notification_log.event_id + channel` UNIQUE |

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
| `KAFKA_CONSUMER_ENABLED` | ✅ | Activa el consumer Kafka | `true` / `false` |
| `KAFKA_BOOTSTRAP_SERVERS` | si Kafka activo | Brokers | `10.10.3.3:9092` |
| `INTERNAL_NOTIFY_TOKEN` | ✅ | Token para endpoint interno | desde Secret Manager |
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

### 2. Registrar email de prueba

```bash
# Obtener JWT de user-services
TOKEN=$(curl -s -X POST https://user-services-ridyy4wz4q-uc.a.run.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"tu@email.com","password":"tupassword"}' | jq -r '.access_token')

# Registrar email en preferencias
curl -X PUT https://notification-services-ridyy4wz4q-uc.a.run.app/api/v1/notifications/preferences \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email_enabled": true, "email_address": "tu@email.com"}'
```

### 3. Disparar notificación de prueba

```bash
# Obtener user_id del token
USER_ID=$(echo $TOKEN | python3 -c "
import sys, base64, json
t = sys.stdin.read().strip().split('.')[1]
t += '=' * (4 - len(t) % 4)
print(json.loads(base64.b64decode(t))['sub'])
")

# Disparar via endpoint interno
curl -X POST https://notification-services-ridyy4wz4q-uc.a.run.app/api/v1/notifications/internal \
  -H "X-Internal-Token: $(gcloud secrets versions access latest --secret=dev-travelhub-internal-notify-token --project=gen-lang-client-0930444414)" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"pms_sync_conflict\",
    \"user_id\": \"$USER_ID\",
    \"hotel_id\": \"660e8400-e29b-41d4-a716-446655440001\",
    \"details\": {\"conflict_type\": \"availability\", \"description\": \"Smoke test\"},
    \"recipients\": [\"hotel_admin\"]
  }"
```

> **Nota:** En DEV `SENDGRID_SANDBOX=true`, el email no llega al buzón. Para recibir el email real:
> ```bash
> gcloud run services update notification-services --region=us-central1 \
>   --project=gen-lang-client-0930444414 --set-env-vars="SENDGRID_SANDBOX=false"
> ```

---

## Documentación adicional

| Documento | Contenido |
|---|---|
| [docs/api.md](docs/api.md) | Contratos completos de todos los endpoints |
| [docs/kafka-topics.md](docs/kafka-topics.md) | Topics, payloads y guía de prueba local |
| [docs/ADR-001-event-schema.md](docs/ADR-001-event-schema.md) | Decisión: envelope estándar de eventos Kafka |
| [docs/ADR-002-internal-http-pms.md](docs/ADR-002-internal-http-pms.md) | Decisión: HTTP interno vs Kafka para pms-sync-worker |
| [CLAUDE.md](CLAUDE.md) | Instrucciones completas de arquitectura para Claude Code |
