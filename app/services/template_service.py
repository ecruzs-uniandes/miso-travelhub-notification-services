import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
)


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
