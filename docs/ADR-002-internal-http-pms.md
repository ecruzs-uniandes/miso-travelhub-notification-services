# ADR-002: Endpoint HTTP interno para pms-sync-worker

## Contexto
`pms-sync-worker` necesita notificar a hotel admins sobre eventos de sincronización PMS.

## Decisión
En lugar de publicar a Kafka, `pms-sync-worker` llama directamente a `POST /api/v1/notifications/internal` via HTTP interno en la VPC.

## Consecuencias
- Acoplamiento temporal reducido vs Kafka.
- Seguridad via `X-Internal-Token` + firewall de subnet.
- La URL del endpoint debe configurarse en el deploy de `pms-sync-worker`.
- Este endpoint NO está en el OpenAPI del gateway (no es público).
