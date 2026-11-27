import re
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import PasswordResetChallenge, ProfileSecurityChallenge, Staff


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class ProfileSecurityTests(TestCase):
    base = "/api/auth/profile-security"
    current_password = "LocalPassword-183"
    new_password = "Warehouse-Verified-926!"
    first_email = "stockroom.test@gmail.com"
    next_email = "stockroom.next@gmail.com"

    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.staff = Staff.objects.create_user(
            username="employee@stockroom.local", role="manager", password=self.current_password,
        )
        self.api = APIClient(enforce_csrf_checks=True)
        self.assertTrue(self.api.login(username=self.staff.username, password=self.current_password))

    def post(self, path, data, client=None):
        client = client or self.api
        csrf = client.get("/api/auth/csrf").json()["csrfToken"]
        return client.post(path, data, format="json", HTTP_X_CSRFTOKEN=csrf)

    def request(self, action, **kwargs):
        def send_now(email, code, purpose="reset"):
            from .recovery import deliver_code, mail_slots
            self.assertTrue(mail_slots.acquire(blocking=False))
            deliver_code(email, code, purpose)

        with patch("inventory.profile_security.queue_code", side_effect=send_now), \
                patch("inventory.recovery.queue_code", side_effect=send_now), \
                self.captureOnCommitCallbacks(execute=True):
            return self.post(self.base + "/request", {
                "action": action, "current_password": self.current_password, **kwargs,
            })

    def confirm(self, action, code, **kwargs):
        return self.post(self.base + "/confirm", {"action": action, "code": code, **kwargs})

    @staticmethod
    def code_from(message):
        return re.search(r"\b[0-9]{8}\b", message.body).group()

    def test_code_links_email_then_works_with_forgot_password(self):
        denied = self.request("recovery_email", email=self.first_email, current_password="wrong-password")
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)
        sent = self.request("recovery_email", email=self.first_email.upper())
        self.assertEqual(sent.status_code, 202)
        self.assertEqual(sent.json(), {"requires_old_code": False})
        self.assertEqual(mail.outbox[0].to, [self.first_email])
        self.staff.refresh_from_db()
        self.assertIsNone(self.staff.recovery_email)
        code = self.code_from(mail.outbox[0])
        saved = self.confirm("recovery_email", code)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["recovery_email"], "s***@gmail.com")
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.recovery_email, self.first_email)
        self.assertEqual(self.confirm("recovery_email", code).status_code, 400)

        with patch("inventory.recovery.queue_code") as deliver, self.captureOnCommitCallbacks(execute=True):
            result = self.post("/api/auth/password-reset/request", {"email": self.first_email}, APIClient())
            self.assertEqual(result.status_code, 202)
        deliver.assert_called_once()
        self.assertEqual(deliver.call_args.args[0], self.first_email)

    def test_change_password_requires_own_code_and_keeps_current_session(self):
        self.assertEqual(self.request("password").status_code, 400)
        self.staff.recovery_email = self.first_email
        self.staff.save(update_fields=["recovery_email"])
        other = APIClient()
        other.login(username=self.staff.username, password=self.current_password)

        self.assertEqual(self.request("password").status_code, 202)
        mail_code = self.code_from(mail.outbox[0])
        incorrect = "00000000" if mail_code != "00000000" else "11111111"
        self.assertEqual(mail.outbox[0].to, [self.first_email])
        failed = self.confirm("password", incorrect, password=self.new_password)
        self.assertEqual(failed.status_code, 400)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password(self.current_password))
        self.assertEqual(self.confirm("password", mail_code, password=self.new_password).status_code, 200)
        self.assertEqual(self.api.get("/api/auth/me").status_code, 200)
        self.assertEqual(other.get("/api/auth/me").status_code, 403)
        self.assertFalse(other.login(username=self.staff.username, password=self.current_password))
        self.assertTrue(other.login(username=self.staff.username, password=self.new_password))
        self.assertEqual(self.confirm("password", mail_code, password=self.current_password).status_code, 400)

    def test_replace_email_needs_both_codes(self):
        self.staff.recovery_email = self.first_email
        self.staff.save(update_fields=["recovery_email"])
        with patch("inventory.recovery.queue_code"), self.captureOnCommitCallbacks(execute=True):
            self.post("/api/auth/password-reset/request", {"email": self.first_email}, APIClient())
        self.assertTrue(PasswordResetChallenge.objects.filter(staff=self.staff).exists())
        sent = self.request("recovery_email", email=self.next_email)
        self.assertEqual(sent.json(), {"requires_old_code": True})
        self.assertEqual([m.to for m in mail.outbox], [[self.next_email], [self.first_email]])
        new_code, old_code = map(self.code_from, mail.outbox)
        self.assertNotEqual(new_code, old_code)
        self.assertEqual(self.confirm("recovery_email", new_code).status_code, 400)
        self.assertEqual(self.confirm("recovery_email", new_code, old_code=old_code).status_code, 200)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.recovery_email, self.next_email)
        self.assertFalse(PasswordResetChallenge.objects.filter(staff=self.staff).exists())

    def test_anonymous_duplicate_address_and_challenge_rate_limit(self):
        self.assertEqual(APIClient().get(self.base).status_code, 403)
        Staff.objects.create_user(username="owner@stockroom.local", recovery_email=self.first_email)
        self.assertEqual(self.request("recovery_email", email=self.first_email).status_code, 202)
        self.assertEqual(self.request("recovery_email", email=self.next_email).status_code, 400)
        code = self.code_from(mail.outbox[0])
        self.assertEqual(self.confirm("recovery_email", code).status_code, 400)
        self.staff.refresh_from_db()
        self.assertIsNone(self.staff.recovery_email)

    @override_settings(DEBUG=False)
    def test_shared_demo_initial_binding_is_blocked_without_setup_key(self):
        self.staff.username = "manager@stockroom.local"
        self.staff.save(update_fields=["username"])
        self.assertFalse(self.api.get(self.base).json()["can_link_email"])
        self.assertEqual(self.request("recovery_email", email=self.first_email).status_code, 403)
        self.assertFalse(ProfileSecurityChallenge.objects.exists())

    @override_settings(DEBUG=False, STOCKROOM_DEMO_SETUP_KEY="example-test-key")
    def test_shared_demo_can_link_with_setup_key_and_email_code(self):
        self.staff.username = "admin@stockroom.local"
        self.staff.save(update_fields=["username"])
        state = self.api.get(self.base).json()
        self.assertTrue(state["can_link_email"])
        self.assertTrue(state["requires_setup_key"])
        self.assertNotIn("example-test-key", str(state))
        invalid = self.request("recovery_email", email=self.first_email, setup_key="wrong")
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(mail.outbox)
        sent = self.request("recovery_email", email=self.first_email, setup_key="example-test-key")
        self.assertEqual(sent.status_code, 202)
        code = self.code_from(mail.outbox[0])
        with self.settings(STOCKROOM_DEMO_SETUP_KEY="rotated-test-key"):
            self.assertEqual(self.confirm("recovery_email", code).status_code, 400)
        verified = self.confirm("recovery_email", code)
        self.assertEqual(verified.status_code, 200)
        self.assertFalse(verified.json()["requires_setup_key"])
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.recovery_email, self.first_email)
