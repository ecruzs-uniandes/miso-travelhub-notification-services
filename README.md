# miso-travelhub-notification-services

Microservicio de notificaciones transaccionales para TravelHub (Grupo 9 — MISW4501/4502, Uniandes).

## Stack

Python 3.11 · FastAPI · SQLAlchemy async · Kafka (confluent-kafka) · SendGrid · FCM · Jinja2 · PostgreSQL

## Inicio rápido

```bash
# Copiar variables de entorno
cp .env.example .env

# Levantar con Docker Compose (postgres + servicio)
docker compose up --build

# Health check
curl http://localhost:8004/health
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest --cov=app --cov-report=term-missing --cov-fail-under=70
```

## Lint

```bash
ruff check app/ tests/
flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203
```

## Migraciones

```bash
alembic upgrade head
```

## Documentación

- [API Reference](docs/api.md)
- [Kafka Topics](docs/kafka-topics.md)
- [ADR-001 Event Schema](docs/ADR-001-event-schema.md)
- [ADR-002 Internal HTTP](docs/ADR-002-internal-http-pms.md)
- [CLAUDE.md](CLAUDE.md) — instrucciones completas de arquitectura e implementación
