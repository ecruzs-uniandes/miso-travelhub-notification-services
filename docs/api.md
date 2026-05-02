# API Reference — notification-services

Base URL (DEV): `https://notification-services-<hash>-uc.a.run.app`
Via gateway: `https://travelhub-gateway-1yvtqj7r.uc.gateway.dev/api/v1/notifications`

## Autenticación

Todos los endpoints públicos requieren `Authorization: Bearer <JWT>`.
El JWT es emitido por `user-services` y validado por el API Gateway.
Este servicio solo hace decode sin verificar firma (el gateway ya la validó).

## Endpoints Públicos

### GET /api/v1/notifications
Lista las notificaciones del usuario autenticado.

**Query params:** `limit` (1-100, default 20), `offset` (default 0), `unread_only` (bool, default false)

**Response 200:**
```json
{
  "items": [{"id": "uuid", "event_type": "booking.confirmed", "title": "...", "body": "...", "metadata": {}, "read_at": null, "created_at": "2026-05-01T10:00:00Z"}],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

### POST /api/v1/notifications/{id}/read
Marca una notificación como leída.

### POST /api/v1/notifications/read-all
Marca todas las notificaciones del usuario como leídas.

### GET /api/v1/notifications/preferences
Retorna las preferencias de notificación del usuario.

### PUT /api/v1/notifications/preferences
Actualiza las preferencias del usuario.

**Body:**
```json
{
  "email_enabled": true,
  "push_enabled": true,
  "sms_enabled": false,
  "whatsapp_enabled": false,
  "email_address": "user@example.com",
  "phone_number": "+573001234567",
  "fcm_token": "..."
}
```

## Endpoint Interno (NO público)

### POST /api/v1/notifications/internal
Solo accesible desde `subnet-services`. Requiere header `X-Internal-Token`.

**Body:**
```json
{
  "type": "pms_sync_conflict",
  "user_id": "uuid",
  "hotel_id": "uuid",
  "details": {},
  "recipients": ["hotel_admin"]
}
```

**Response 202:**
```json
{"notification_id": "uuid", "channels_sent": ["email"]}
```

## Health

- `GET /health` → `{"status": "ok"}`
- `GET /ready` → readiness con check de BD
