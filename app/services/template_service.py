import logging
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

_MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _filter_currency(value, currency: str = "COP") -> str:
    """750000 -> '$ 750.000 COP'. Acepta int, float, Decimal o str numérica."""
    if value is None or value == "":
        return ""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return str(value)
    formatted = f"{amount:,.0f}".replace(",", ".")
    return f"$ {formatted} {currency}".strip()


def _filter_date_es(value) -> str:
    """ISO 2026-06-15 o datetime -> '15 de junio de 2026'."""
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                value = date.fromisoformat(value)
            except ValueError:
                return value
    if isinstance(value, (datetime, date)):
        return f"{value.day} de {_MONTHS_ES[value.month - 1]} de {value.year}"
    return str(value)


def _filter_datetime_es(value) -> str:
    """ISO 2026-05-13T02:38:04Z -> '13 de mayo de 2026, 9:38 PM' (America/Bogota, UTC-5)."""
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if isinstance(value, datetime):
        # Conversión naive a Bogotá (UTC-5). No usamos zoneinfo para evitar dependencia adicional.
        from datetime import timedelta, timezone as tz
        if value.tzinfo is None:
            value = value.replace(tzinfo=tz.utc)
        bog = value.astimezone(tz(timedelta(hours=-5)))
        hour_12 = bog.hour % 12 or 12
        ampm = "AM" if bog.hour < 12 else "PM"
        return f"{bog.day} de {_MONTHS_ES[bog.month - 1]} de {bog.year}, {hour_12}:{bog.minute:02d} {ampm}"
    return str(value)


def _filter_default_or(value, fallback: str = "") -> str:
    """Devuelve fallback si value es None o string vacío/whitespace."""
    if value is None:
        return fallback
    if isinstance(value, str) and not value.strip():
        return fallback
    return value


_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["currency"] = _filter_currency
_env.filters["date_es"] = _filter_date_es
_env.filters["datetime_es"] = _filter_datetime_es
_env.filters["default_or"] = _filter_default_or


class TemplateService:
    def render(self, template_code: str, context: dict) -> str:
        try:
            template = _env.get_template(template_code)
            return template.render(**context)
        except TemplateNotFound:
            raise ValueError(f"Plantilla no encontrada: {template_code}")
        except Exception as exc:
            logger.error("template_render_failed", extra={"template": template_code, "error": str(exc)})
            raise ValueError(f"Error al renderizar plantilla '{template_code}': {exc}") from exc

    def template_exists(self, template_code: str) -> bool:
        try:
            _env.get_template(template_code)
            return True
        except TemplateNotFound:
            return False
