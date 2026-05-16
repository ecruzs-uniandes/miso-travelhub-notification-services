# ADR-001: Schema de eventos Kafka (Envelope estándar)

**Estado:** Aceptado (vigente) · El envelope se reusa en HTTP — ver "Adenda 2026-05-16" abajo.
**Fecha:** 2026-04-20
**Autores:** Edwin Cruz Silva (Grupo 9)
**Revisado por:** Grupo 9 — MISW4501/4502 Uniandes

---

## Adenda 2026-05-16: el envelope ahora viaja por HTTP, no Kafka

Durante el sprint los compañeros de booking, payment y user-services construyeron sus propios workers Kafka por dominio y nos pidieron exponer un endpoint HTTP que recibiera **el mismo envelope** que iban a publicar al broker. Para no duplicar la lógica de procesamiento (renderizado, idempotencia, plantillas), se agregó `POST /api/v1/notifications/events` que recibe `{event_type, user_id, payload}` y delega al mismo `NotificationService.process_event()` (vía el dispatcher de `app/kafka/dispatcher.py`) que invocaba el consumer Kafka.

Cambios respecto al envelope original:
- **`event_id` y `occurred_at` se generan server-side** (`event_id = http_<event_type>_<uuid4>`, `occurred_at = now()` UTC). Antes los publicaba el productor para garantizar idempotencia cross-redelivery; ahora la idempotencia es responsabilidad del worker emisor — cada POST envía un correo.
- **Campos requeridos en el body**: `event_type`, `user_id`, `payload`. Los payloads por `event_type` siguen iguales a los Pydantic schemas declarados en este ADR (ver § Schemas Pydantic abajo y `docs/api.md` para curls).
- **Auth**: `X-Internal-Token` en lugar de identidad Kafka. El endpoint no está en API Gateway; se llama directo al Cloud Run del servicio.

El consumer Kafka sigue intacto en `app/kafka/consumer.py` y reusa el mismo dispatcher; si en el futuro se prefiere volver al transporte por broker, sólo se cambia `KAFKA_CONSUMER_ENABLED` y los productores publican al topic correspondiente.

Detalle completo del contrato HTTP, curls por `event_type`, opt-out y reglas operativas: `docs/api.md` § *POST /api/v1/notifications/events*.

---

## Contexto

`notification-services` necesita consumir eventos de múltiples productores independientes (`booking-services`, `payments-services`, `user-services`) que viven en repositorios separados y evolucionan de forma autónoma.

Sin un contrato común, cada productor podría usar:
- Campos con nombres distintos para el mismo concepto (ej: `userId` vs `user_id` vs `uid`)
- Formatos de fecha distintos (Unix timestamp vs ISO 8601 vs epoch ms)
- Estructuras de mensaje distintas (plano vs anidado)

Esto forzaría al consumer a mantener lógica de parsing específica por productor, aumentando la deuda técnica y el riesgo de bugs al onboardear nuevos productores.

---

## Decisión

Se adopta un **envelope JSON estándar** para todos los eventos publicados en Kafka dentro del ecosistema TravelHub:

```json
{
  "event_id":    "evt_<id único>",
  "event_type":  "dominio.accion",
  "occurred_at": "2026-05-01T15:30:00Z",
  "user_id":     "550e8400-e29b-41d4-a716-446655440000",
  "payload":     { }
}
```

### Campos del envelope

| Campo | Tipo | Invariante |
|---|---|---|
| `event_id` | string | Único globalmente. Puede ser `evt_<uuid>` o `<uuid>` directo. Nunca reutilizar. |
| `event_type` | string | Notación `dominio.accion` en snake_case. Ejemplos: `booking.confirmed`, `payment.failed`. |
| `occurred_at` | string ISO 8601 UTC | Timestamp del momento en que el evento ocurrió en el dominio de origen. |
| `user_id` | string UUID | ID del usuario al que refiere la notificación. |
| `payload` | object | Datos específicos del evento. Sin schema fijo — cada tipo define el suyo. |

### Reglas de naming para `event_type`

- Formato: `<dominio>.<verbo_pasado>` (ej: `booking.confirmed`, no `booking.confirm` ni `confirmBooking`)
- El dominio coincide con el nombre del servicio sin sufijo `-services`.
- Los verbos van en inglés, en participio pasado.

---

## Alternativas consideradas

### A. Schema Registry con Avro/Protobuf

Usar Confluent Schema Registry con serialización Avro o Protobuf.

**Pros:**
- Validación automática de schema en el productor antes de publicar
- Evolución de schema con compatibilidad garantizada (BACKWARD/FORWARD)
- Payload binario más compacto

**Contras:**
- Requiere desplegar y operar Confluent Schema Registry (otro componente)
- Curva de aprendizaje adicional para el equipo
- Complejidad innecesaria para un MVP académico con ~5 event types

**Rechazado:** overhead operacional no justificado para el scope del proyecto.

### B. Schema ad-hoc por productor (sin contrato común)

Cada servicio publica en el formato que le resulte conveniente y `notification-services` adapta.

**Pros:** ningún proceso de coordinación entre equipos

**Contras:**
- Código de parsing duplicado y frágil en el consumer
- Bugs silenciosos si un productor cambia un campo sin avisar
- No escala: cada nuevo event_type requiere nuevo código de adaptación

**Rechazado:** viola el principio de bajo acoplamiento a largo plazo.

### C. CloudEvents (CNCF)

Usar el spec CloudEvents como envelope, con extensión para `user_id`.

**Pros:** estándar de industria reconocido

**Contras:**
- Overhead de adoptar el spec completo (required attributes: `specversion`, `source`, `id`, `type`)
- Los campos tienen nombres que no coinciden con los convenios del proyecto (`id` vs `event_id`, `type` vs `event_type`)
- Migración posterior más costosa si se quiere mapear de vuelta al dominio

**Rechazado:** beneficios insuficientes para el scope actual.

---

## Consecuencias

### Positivas
- **Parsing unificado:** `notification-services` tiene un solo `EventEnvelope` Pydantic que valida todos los mensajes entrantes.
- **Idempotencia automática:** `event_id` como clave en `UNIQUE(event_id, channel)` en `notification_log` garantiza exactly-once a nivel de BD sin lógica adicional.
- **Extensibilidad:** añadir un nuevo event_type solo requiere registrar un handler en el dispatcher y opcionalmente una plantilla. El envelope no cambia.
- **Desacoplamiento de productores:** notification-services no sabe nada de la implementación interna de booking-services.

### Negativas / compromisos
- **Coordinación requerida:** todos los productores deben adoptar el envelope. Si un productor publica en formato distinto, el mensaje va al DLQ.
- **`payload` no tipado:** la validación del payload por event_type es responsabilidad del handler, no del envelope. Un campo faltante en `payload` causará un error en tiempo de ejecución, no en deserialización.
- **`user_id` siempre requerido:** eventos que no pertenecen a un usuario específico (ej: eventos de sistema) no encajan en este envelope. Para el scope actual todos los eventos tienen `user_id`.

---

## Implementación de referencia

```python
# app/schemas/events.py
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class EventEnvelope(BaseModel):
    event_id: str
    event_type: str
    occurred_at: datetime
    user_id: UUID
    payload: dict
```

```python
# app/kafka/dispatcher.py — registro de handlers por event_type
_handlers: dict[str, Callable] = {}

def register(event_type: str):
    def decorator(fn: Callable) -> Callable:
        _handlers[event_type] = fn
        return fn
    return decorator

def get_handler(event_type: str) -> Callable | None:
    handler = _handlers.get(event_type)
    if not handler:
        logger.warning("unknown_event_type", extra={"event_type": event_type})
    return handler
```

---

## Revisión futura

Si el proyecto escala a producción real y el número de event_types supera ~20, reconsiderar Schema Registry con Avro. La migración desde JSON a Avro es transparente para el consumer si se mantiene el mismo campo `event_type` como discriminador.
