import logging
import smtplib
from email.message import EmailMessage
from functools import lru_cache

from app.config.settings import get_settings

log = logging.getLogger("mail")


class Mailer:
    """SMTP (Mailpit в compose); без MAIL_HOST — только запись в журнал."""

    def send(self, to: str, subject: str, body: str) -> None:
        s = get_settings()
        if not s.mail_host:
            log.info("SMTP не настроен, письмо не отправлено: subject=%s", subject)
            return
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = s.mail_from, to, subject
        msg.set_content(body)
        with smtplib.SMTP(s.mail_host, s.mail_port, timeout=5) as smtp:
            smtp.send_message(msg)


@lru_cache
def get_mailer() -> Mailer:
    return Mailer()
