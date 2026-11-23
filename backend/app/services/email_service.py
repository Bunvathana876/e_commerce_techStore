from email.message import EmailMessage
import html
import logging
import smtplib
import ssl

from fastapi import HTTPException, status
import httpx

from app.core.config import Settings, settings

logger = logging.getLogger("uvicorn.error")


class EmailDeliveryError(Exception):
    """Raised when an upstream SMTP or SendGrid email delivery fails."""


class EmailService:
    """Transactional email dispatcher supporting SMTP and SendGrid."""

    @staticmethod
    def resolve_provider(cfg: Settings | None = None) -> str:
        c = cfg or settings
        explicit = (c.EMAIL_PROVIDER or "auto").strip().lower()
        if explicit in {"smtp", "sendgrid", "console"}:
            return explicit
        if c.SENDGRID_API_KEY and c.SENDGRID_API_KEY.strip():
            return "sendgrid"
        if c.SMTP_HOST and c.SMTP_HOST.strip():
            return "smtp"
        return "console"

    @staticmethod
    def ensure_configured(cfg: Settings | None = None) -> str:
        c = cfg or settings
        provider = EmailService.resolve_provider(c)
        if provider == "sendgrid":
            if not (c.SENDGRID_API_KEY and c.SENDGRID_API_KEY.strip()):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="SendGrid email provider is selected but SENDGRID_API_KEY is not configured.",
                )
            return provider
        if provider == "smtp":
            if not (c.SMTP_HOST and c.SMTP_HOST.strip()):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="SMTP email provider is selected but SMTP_HOST is not configured.",
                )
            return provider
        if c.is_production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Password reset email service is not configured. Configure SMTP or SendGrid.",
            )
        return provider

    @staticmethod
    def build_reset_url(raw_token: str, client: str = "storefront", cfg: Settings | None = None) -> str:
        c = cfg or settings
        normalized_client = (client or "storefront").strip().lower()
        base = c.MANAGEMENT_BASE_URL if normalized_client == "management" else c.STOREFRONT_BASE_URL
        return f"{base.rstrip('/')}/reset-password?token={raw_token}"

    @staticmethod
    def send_email(
        *,
        to_email: str,
        subject: str,
        plain_body: str,
        html_body: str,
        cfg: Settings | None = None,
    ) -> str:
        c = cfg or settings
        provider = EmailService.ensure_configured(c)
        if provider == "sendgrid":
            EmailService._send_via_sendgrid(
                to_email=to_email,
                subject=subject,
                plain_body=plain_body,
                html_body=html_body,
                cfg=c,
            )
        elif provider == "smtp":
            EmailService._send_via_smtp(
                to_email=to_email,
                subject=subject,
                plain_body=plain_body,
                html_body=html_body,
                cfg=c,
            )
        else:
            EmailService._send_via_console(to_email=to_email, subject=subject)
        return provider

    @staticmethod
    def _send_via_smtp(
        *,
        to_email: str,
        subject: str,
        plain_body: str,
        html_body: str,
        cfg: Settings,
    ) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{cfg.EMAIL_FROM_NAME} <{cfg.EMAIL_FROM_ADDRESS}>"
        msg["To"] = to_email
        msg.set_content(plain_body)
        msg.add_alternative(html_body, subtype="html")

        host = (cfg.SMTP_HOST or "").strip()
        port = cfg.SMTP_PORT
        timeout = cfg.SMTP_TIMEOUT_SECONDS
        context = ssl.create_default_context()

        try:
            if cfg.SMTP_USE_SSL or port == 465:
                with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as server:
                    if cfg.SMTP_USERNAME and cfg.SMTP_PASSWORD:
                        server.login(cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=timeout) as server:
                    server.ehlo()
                    if cfg.SMTP_USE_TLS:
                        server.starttls(context=context)
                        server.ehlo()
                    if cfg.SMTP_USERNAME and cfg.SMTP_PASSWORD:
                        server.login(cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD)
                    server.send_message(msg)
        except Exception as exc:
            logger.error("SMTP delivery error: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to dispatch recovery email via SMTP right now.",
            ) from exc

    @staticmethod
    def _send_via_sendgrid(
        *,
        to_email: str,
        subject: str,
        plain_body: str,
        html_body: str,
        cfg: Settings,
    ) -> None:
        api_key = (cfg.SENDGRID_API_KEY or "").strip()
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {
                "email": cfg.EMAIL_FROM_ADDRESS,
                "name": cfg.EMAIL_FROM_NAME,
            },
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": plain_body},
                {"type": "text/html", "value": html_body},
            ],
        }
        try:
            response = httpx.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=10.0,
            )
            if response.status_code >= 300:
                logger.error("SendGrid API returned status %s", response.status_code)
                raise EmailDeliveryError(f"SendGrid error status {response.status_code}")
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("SendGrid delivery error: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to dispatch recovery email via SendGrid right now.",
            ) from exc

    @staticmethod
    def _send_via_console(*, to_email: str, subject: str) -> None:
        local, _, domain = to_email.partition("@")
        masked = f"{local[:2]}***@{domain}" if domain else "***"
        logger.info("[DEV EMAIL CONSOLE] Dispatched '%s' to %s", subject, masked)

    @staticmethod
    def send_password_reset_email(
        *,
        to_email: str,
        user_name: str,
        raw_token: str,
        client: str = "storefront",
        expire_minutes: int | None = None,
        cfg: Settings | None = None,
    ) -> str:
        c = cfg or settings
        ttl = expire_minutes or c.PASSWORD_RESET_EXPIRE_MINUTES
        reset_url = EmailService.build_reset_url(raw_token, client=client, cfg=c)
        safe_name = html.escape(user_name or "Customer")
        safe_url = html.escape(reset_url, quote=True)
        safe_token = html.escape(raw_token)

        subject = "Reset Your Blue Panda Password"
        plain_body = (
            f"Hello {user_name or 'Customer'},\n\n"
            "We received a request to reset your Blue Panda account password.\n"
            f"Reset link (expires in {ttl} minutes):\n{reset_url}\n\n"
            f"If you are using the mobile app, paste this recovery token:\n{raw_token}\n\n"
            "If you did not request a password reset, you can safely ignore this email.\n"
        )
        html_body = (
            "<div style=\"font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#0f172a;\">"
            "<h2 style=\"color:#1d4ed8;\">Blue Panda Account Recovery</h2>"
            f"<p>Hello {safe_name},</p>"
            "<p>We received a request to reset your Blue Panda account password. "
            f"This link expires in <strong>{ttl} minutes</strong>.</p>"
            f"<p style=\"margin:24px 0;\"><a href=\"{safe_url}\" "
            "style=\"background:#1d4ed8;color:#ffffff;padding:12px 20px;border-radius:8px;"
            "text-decoration:none;font-weight:bold;display:inline-block;\">Reset Password</a></p>"
            f"<p style=\"font-size:13px;color:#475569;\">Mobile app reset token: <code>{safe_token}</code></p>"
            "<p style=\"font-size:12px;color:#64748b;\">If you did not request this change, "
            "no further action is needed.</p>"
            "</div>"
        )

        return EmailService.send_email(
            to_email=to_email,
            subject=subject,
            plain_body=plain_body,
            html_body=html_body,
            cfg=c,
        )
