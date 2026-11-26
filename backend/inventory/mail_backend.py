import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class ResendBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            request = Request(
                "https://api.resend.com/emails",
                data=json.dumps({
                    "from": message.from_email,
                    "to": message.to,
                    "subject": message.subject,
                    "text": message.body,
                }).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                    "User-Agent": "Stockroom/1.0",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=settings.EMAIL_TIMEOUT):
                    sent += 1
            except (URLError, TimeoutError):
                if not self.fail_silently:
                    raise
        return sent
