"""Secure, provider-independent SMTP delivery for completed briefings."""

from dataclasses import dataclass
from datetime import datetime, timezone
from email.errors import HeaderParseError
from email.message import EmailMessage
from email.headerregistry import Address
from email.utils import formataddr
import json
import os
from pathlib import Path
import re
import smtplib
import ssl

DEFAULT_BRIEFING = Path("data/output/llm_briefing.html")
DEFAULT_METADATA = Path("data/output/email_delivery.json")
DEFAULT_FROM_NAME = "48-Hour Market Intelligence"


class EmailConfigurationError(ValueError):
    """Raised when SMTP settings are absent or invalid."""


class RecipientValidationError(EmailConfigurationError):
    """Raised when a recipient override or default contains an invalid address."""


def parse_recipients(value: str) -> tuple[str, ...]:
    """Parse, conservatively validate, and de-duplicate a comma-separated list."""
    parts = value.split(",")
    recipients: list[str] = []
    for raw_address in parts:
        address = raw_address.strip()
        if not address:
            raise RecipientValidationError("Invalid recipient: empty entry")
        try:
            parsed = Address(addr_spec=address)
        except (TypeError, ValueError, HeaderParseError) as exc:
            raise RecipientValidationError(f"Invalid recipient: {address}") from exc
        # Address accepts local-only mailboxes; delivery configuration deliberately
        # requires the more familiar local@domain form and forbids display names.
        if (parsed.addr_spec != address or not parsed.username or not parsed.domain
                or any(character.isspace() for character in address)):
            raise RecipientValidationError(f"Invalid recipient: {address}")
        if address not in recipients:
            recipients.append(address)
    return tuple(recipients)


@dataclass(frozen=True)
class SMTPConfig:
    host: str
    port: int
    username: str
    password: str
    sender: str
    recipients: tuple[str, ...]
    sender_name: str = DEFAULT_FROM_NAME
    starttls: bool = True
    use_ssl: bool = False
    timeout: float = 30.0

    @classmethod
    def from_env(cls, recipient_override: str | None = None) -> "SMTPConfig":
        """Load SMTP credentials, preferring a non-blank per-run recipient override."""
        override = recipient_override.strip() if recipient_override is not None else ""
        required = ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "EMAIL_FROM")
        missing = [name for name in required if not os.environ.get(name, "").strip()]
        recipient_value = override or os.environ.get("EMAIL_TO", "").strip()
        if not recipient_value:
            missing.append("EMAIL_TO (or --email-to override)")
        if missing:
            raise EmailConfigurationError("Missing required email configuration: " + ", ".join(missing))
        try:
            port = int(os.environ.get("SMTP_PORT") or "587")
            timeout = float(os.environ.get("SMTP_TIMEOUT") or "30")
        except ValueError as exc:
            raise EmailConfigurationError("SMTP_PORT and SMTP_TIMEOUT must be numeric") from exc
        recipients = parse_recipients(recipient_value)
        truthy = {"1", "true", "yes", "on"}
        use_ssl = os.environ.get("SMTP_USE_SSL", "false").lower() in truthy
        starttls = os.environ.get("SMTP_USE_STARTTLS", "true").lower() in truthy
        if use_ssl and starttls:
            raise EmailConfigurationError("SMTP_USE_SSL and SMTP_USE_STARTTLS cannot both be enabled")
        return cls(os.environ["SMTP_HOST"].strip(), port, os.environ["SMTP_USERNAME"].strip(),
                   os.environ["SMTP_PASSWORD"], os.environ["EMAIL_FROM"].strip(), recipients,
                   os.environ.get("EMAIL_FROM_NAME", DEFAULT_FROM_NAME).strip() or DEFAULT_FROM_NAME,
                   starttls, use_ssl, timeout)


def briefing_date(html: str) -> str:
    match = re.search(r"LLM editorial edition\s*[·&middot;]+\s*(\d{4}-\d{2}-\d{2})", html)
    if not match:
        raise ValueError("Briefing generation date was not found in the HTML")
    return match.group(1)


def build_message(html: str, config: SMTPConfig) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"48-Hour Market Intelligence Briefing — {briefing_date(html)}"
    message["From"] = formataddr((config.sender_name, config.sender))
    message["To"] = ", ".join(config.recipients)
    message.set_content("Your 48-Hour Market Intelligence Briefing is available in the HTML version of this email.")
    message.add_alternative(html, subtype="html")
    return message


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, (EmailConfigurationError, ValueError)):
        return str(exc)
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "SMTP authentication failed"
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "SMTP rejected one or more recipients"
    if isinstance(exc, (TimeoutError, smtplib.SMTPServerDisconnected)):
        return "SMTP connection timed out or was disconnected"
    if isinstance(exc, (smtplib.SMTPException, OSError)):
        return "SMTP delivery failed"
    return "Email delivery failed"


def _write_metadata(path: Path, *, success: bool, recipient_count: int,
                    subject: str | None, briefing_path: Path, error: str | None) -> None:
    payload = {"attempted": True, "success": success,
               "timestamp_utc": datetime.now(timezone.utc).isoformat(),
               "recipient_count": recipient_count, "subject": subject,
               "briefing_file": briefing_path.as_posix(), "error": error}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def send_briefing(briefing_path: Path = DEFAULT_BRIEFING,
                  metadata_path: Path = DEFAULT_METADATA,
                  recipient_override: str | None = None) -> bool:
    """Send one existing briefing and always record a sanitized attempt result."""
    config = None
    subject = None
    try:
        if not briefing_path.is_file() or briefing_path.stat().st_size == 0:
            raise ValueError("Briefing file does not exist or is empty")
        html = briefing_path.read_text(encoding="utf-8")
        config = SMTPConfig.from_env(recipient_override)
        message = build_message(html, config)
        subject = str(message["Subject"])
        smtp_class = smtplib.SMTP_SSL if config.use_ssl else smtplib.SMTP
        with smtp_class(config.host, config.port, timeout=config.timeout) as smtp:
            smtp.ehlo()
            if config.starttls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            smtp.login(config.username, config.password)
            smtp.send_message(message, from_addr=config.sender, to_addrs=list(config.recipients))
        _write_metadata(metadata_path, success=True, recipient_count=len(config.recipients),
                        subject=subject, briefing_path=briefing_path, error=None)
        print(f"Email delivered successfully to {len(config.recipients)} recipient(s).")
        return True
    except Exception as exc:
        error = "Invalid recipient address" if isinstance(exc, RecipientValidationError) else _safe_error(exc)
        _write_metadata(metadata_path, success=False,
                        recipient_count=len(config.recipients) if config else 0,
                        subject=subject, briefing_path=briefing_path, error=error)
        console_error = str(exc) if isinstance(exc, RecipientValidationError) else error
        print(f"Email delivery failed: {console_error}")
        return False


def deliver_briefing_locally(html_path: Path) -> str:
    return f"Briefing saved locally to {html_path} (email not requested)"
