from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSMSStubSender:
    @pytest.mark.asyncio
    async def test_raises_not_implemented(self):
        from app.senders.sms_stub import SMSStubSender
        sender = SMSStubSender()
        with pytest.raises(NotImplementedError):
            await sender.send("+573001234567", "Test", "Body", {})


class TestWhatsAppStubSender:
    @pytest.mark.asyncio
    async def test_raises_not_implemented(self):
        from app.senders.whatsapp_stub import WhatsAppStubSender
        sender = WhatsAppStubSender()
        with pytest.raises(NotImplementedError):
            await sender.send("+573001234567", "Test", "Body", {})


class TestFCMSender:
    @pytest.mark.asyncio
    async def test_empty_token_returns_skipped(self):
        from app.senders.push_fcm import FCMSender
        sender = FCMSender()
        result = await sender.send("", "Title", "Body", {})
        assert result["status"] == "skipped"
        assert result["reason"] == "no_fcm_token"

    @pytest.mark.asyncio
    async def test_no_credentials_returns_skipped(self):
        from app.senders.push_fcm import FCMSender
        with patch("app.senders.push_fcm.settings") as mock_settings:
            mock_settings.FCM_CREDENTIALS_JSON = ""
            sender = FCMSender()
            FCMSender._initialized = False
            result = await sender.send("some-token", "Title", "Body", {})
        assert result["status"] == "skipped"


class TestSendGridSender:
    @pytest.mark.asyncio
    async def test_send_success(self):
        from app.senders.email_sendgrid import SendGridSender

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.headers = {}

        with patch("app.senders.email_sendgrid.SendGridAPIClient") as mock_sg:
            mock_client = MagicMock()
            mock_client.send.return_value = mock_response
            mock_sg.return_value = mock_client

            sender = SendGridSender()
            result = await sender.send("test@example.com", "Test Subject", "Body text", {})

        assert result["status_code"] == 202

    @pytest.mark.asyncio
    async def test_send_failure_raises(self):
        from app.senders.email_sendgrid import SendGridSender

        with patch("app.senders.email_sendgrid.SendGridAPIClient") as mock_sg:
            mock_client = MagicMock()
            mock_client.send.side_effect = Exception("SendGrid error")
            mock_sg.return_value = mock_client

            sender = SendGridSender()
            with pytest.raises(Exception, match="SendGrid error"):
                await sender.send("test@example.com", "Subject", "Body", {})
