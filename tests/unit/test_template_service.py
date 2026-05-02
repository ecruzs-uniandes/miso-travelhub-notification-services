import pytest


BASE_CONTEXT = {
    "user": {"full_name": "Juan Pérez", "email": "juan@example.com"},
    "event": {"occurred_at_human": "1 de mayo de 2026, 10:00 AM"},
    "payload": {
        "booking_id": "770e8400-e29b-41d4-a716-446655440002",
        "hotel_name": "Hotel Bogotá",
        "check_in": "2026-06-15",
        "check_out": "2026-06-18",
        "total": 450.0,
        "currency": "USD",
    },
    "links": {
        "app_url": "https://app.travelhub.app",
        "support_email": "soporte@travelhub.app",
    },
}


class TestTemplateService:
    def test_render_booking_confirmed_txt(self):
        from app.services.template_service import TemplateService
        svc = TemplateService()
        result = svc.render("booking_confirmed.email.txt", BASE_CONTEXT)
        assert "Juan Pérez" in result
        assert "Hotel Bogotá" in result

    def test_render_booking_confirmed_html(self):
        from app.services.template_service import TemplateService
        svc = TemplateService()
        result = svc.render("booking_confirmed.email.html", BASE_CONTEXT)
        assert "Juan Pérez" in result
        assert "Hotel Bogotá" in result
        assert "<html" in result

    def test_template_not_found_raises_value_error(self):
        from app.services.template_service import TemplateService
        svc = TemplateService()
        with pytest.raises(ValueError, match="no encontrada"):
            svc.render("nonexistent.template.txt", BASE_CONTEXT)

    def test_template_exists_true(self):
        from app.services.template_service import TemplateService
        svc = TemplateService()
        assert svc.template_exists("booking_confirmed.email.txt") is True

    def test_template_exists_false(self):
        from app.services.template_service import TemplateService
        svc = TemplateService()
        assert svc.template_exists("nonexistent.txt") is False

    def test_render_payment_completed(self):
        from app.services.template_service import TemplateService
        context = {**BASE_CONTEXT, "payload": {
            "payment_id": "880e8400",
            "booking_id": "770e8400",
            "amount": 450.0,
            "currency": "USD",
            "provider": "stripe",
        }}
        svc = TemplateService()
        result = svc.render("payment_completed.email.txt", context)
        assert "450.0" in result
        assert "USD" in result

    def test_render_user_welcome(self):
        from app.services.template_service import TemplateService
        svc = TemplateService()
        result = svc.render("user_welcome.email.txt", BASE_CONTEXT)
        assert "Juan Pérez" in result
        assert "TravelHub" in result
