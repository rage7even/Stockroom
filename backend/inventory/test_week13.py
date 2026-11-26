import re
from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Customer, Order, OrderScan, PasswordResetChallenge, Product, PurchaseMessage, PurchaseOrder, Staff, Supplier


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class Week13VerificationTests(TestCase):
    def setUp(self):
        self.manager = Staff.objects.create(username="manager@example.com", full_name="Manager", role="manager")
        self.sales = Staff.objects.create(username="sales@example.com")
        self.customer = Customer.objects.create(shop_name="Test shop")
        for sku in ("CHARGER", "CABLE", "WRONG"):
            Product.objects.create(
                sku=sku, product_name=sku.title(), brand="Example", category="Test",
                price_kzt=500, qty_in_stock=10, location="B-02",
            )
        self.client.force_login(self.manager)
        self.api = APIClient()
        self.api.force_authenticate(self.manager)
        order = self.api.post("/api/orders", {
            "customer_id": self.customer.pk, "channel": "website",
            "lines": [{"sku": "CHARGER", "qty": 2}, {"sku": "CABLE", "qty": 1}],
        }, format="json").json()
        self.oid = order["order_id"]
        self.path = f"/api/orders/{self.oid}"

    def scan(self, sku, token=None, source="camera"):
        return self.api.post(self.path + "/verification", {
            "barcode": "SR-" + sku, "source": source, "request_id": str(token or uuid4()),
        }, format="json")

    def test_quantity_verification_and_exactly_one_stock_deduction(self):
        self.assertEqual(self.api.post(self.path + "/ship").status_code, 409)
        self.assertEqual(self.api.post(self.path + "/pack").status_code, 409)
        self.assertEqual(self.scan("UNKNOWN").status_code, 404)
        self.assertEqual(self.scan("WRONG").status_code, 409)
        request_id = uuid4()
        recorded = self.scan("CHARGER", request_id)
        self.assertEqual(recorded.status_code, 201)
        self.assertEqual(self.scan("CHARGER", request_id).status_code, 200)
        self.assertEqual(self.scan("CABLE", request_id).status_code, 409)
        saved = self.api.get(self.path + "/verification").json()
        self.assertEqual((saved["lines"][0]["verified"], saved["history"][0]["staff"]), (1, "Manager"))
        self.assertEqual(saved["lines"][0]["location"], "B-02")
        self.assertEqual(self.scan("CHARGER").status_code, 201)
        self.assertEqual(self.scan("CHARGER").status_code, 409)
        self.assertTrue(self.scan("CABLE", source="manual").json()["complete"])
        self.assertEqual(self.api.post(self.path + "/ship").status_code, 409)
        self.assertEqual(self.api.post(self.path + "/pack").status_code, 200)
        self.assertEqual(Product.objects.get(pk="CHARGER").qty_in_stock, 10)
        self.assertEqual(self.api.post(self.path + "/ship").status_code, 200)
        self.assertEqual(self.api.post(self.path + "/ship").status_code, 409)
        self.assertEqual(self.scan("CABLE").status_code, 409)
        self.assertEqual(Product.objects.get(pk="CHARGER").qty_in_stock, 8)
        self.assertEqual(Product.objects.get(pk="CABLE").qty_in_stock, 9)
        self.assertEqual(OrderScan.objects.count(), 3)

    def test_undo_is_audited_and_reopens_packed_order(self):
        earlier_id = "ffffffff-ffff-4fff-8fff-ffffffffffff"
        later_id = "00000000-0000-4000-8000-000000000001"
        now = timezone.now()
        with patch("inventory.scans.timezone.now", return_value=now):
            self.scan("CHARGER", earlier_id)
            self.scan("CHARGER")
            latest = self.scan("CABLE", later_id).json()["latest_active_id"]
        self.assertEqual(latest, later_id)
        earlier = earlier_id
        self.assertEqual(self.api.post(self.path + "/pack").status_code, 200)
        self.assertEqual(self.api.post(f"{self.path}/verification/{earlier}/undo").status_code, 409)
        undo = f"{self.path}/verification/{latest}/undo"
        response = self.api.post(undo)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "confirmed")
        self.assertEqual(self.api.post(undo).status_code, 200)
        self.assertFalse(response.json()["complete"])
        self.assertEqual(OrderScan.objects.get(pk=latest).voided_by, self.manager)
        self.assertEqual(self.api.post(self.path + "/ship").status_code, 409)

    def test_legacy_packed_order_still_requires_verification(self):
        Order.objects.filter(pk=self.oid).update(status="packed")
        self.assertEqual(self.api.post(self.path + "/ship").status_code, 409)
        self.scan("CHARGER")
        self.scan("CHARGER")
        self.scan("CABLE")
        self.assertEqual(self.api.post(self.path + "/ship").status_code, 200)

    def test_sales_cannot_view_or_change_verification(self):
        self.api.force_authenticate(self.sales)
        self.assertEqual(self.api.get(self.path + "/verification").status_code, 403)
        self.assertEqual(self.scan("CHARGER").status_code, 403)
        self.assertEqual(self.api.post(self.path + "/pack").status_code, 403)


class Week13ChatTests(TestCase):
    def setUp(self):
        self.manager = Staff.objects.create(username="manager@example.com", role="manager")
        a = Supplier.objects.create(name="Cable Supplier", lead_days=1)
        b = Supplier.objects.create(name="Phone Supplier", lead_days=2)
        self.a = PurchaseOrder.objects.create(supplier=a, staff=self.manager, expected_on=timezone.localdate())
        self.b = PurchaseOrder.objects.create(supplier=b, staff=self.manager, expected_on=timezone.localdate())
        self.supplier = Staff.objects.create(username="supplier@example.com", role="supplier", supplier=a)
        self.sales = Staff.objects.create(username="sales@example.com")
        self.api = APIClient()

    def send(self, purchase_id, body, token=None):
        return self.api.post(f"/api/chat/{purchase_id}/messages", {
            "body": body, "request_id": str(token or uuid4()),
        }, format="json")

    def test_exchange_filters_and_store_roles(self):
        self.api.force_authenticate(self.manager)
        filtered = self.api.get("/api/chat", {"supplier": "cable", "purchase": f"PO-{self.a.pk}"}).json()
        self.assertEqual([row["id"] for row in filtered], [self.a.pk])
        self.assertEqual(self.api.get("/api/chat", {"supplier": "Cable", "purchase": self.b.pk}).json(), [])
        self.assertEqual(self.send(self.a.pk, "When can you deliver?").status_code, 201)
        self.api.force_authenticate(self.supplier)
        self.assertEqual(self.api.get("/api/auth/me").status_code, 200)
        self.assertEqual([row["id"] for row in self.api.get("/api/chat").json()], [self.a.pk])
        self.assertEqual(self.api.get(f"/api/chat/{self.b.pk}/messages").status_code, 404)
        self.assertEqual(self.send(self.b.pk, "Hidden purchase").status_code, 404)
        self.assertEqual(self.api.get("/api/orders").status_code, 403)
        self.assertEqual(self.api.get("/api/purchases").status_code, 403)
        self.assertEqual(self.send(self.a.pk, "  ").status_code, 400)
        token = uuid4()
        reply = self.send(self.a.pk, "Tomorrow morning", token)
        self.assertEqual(reply.status_code, 201)
        self.assertEqual(self.send(self.a.pk, "Tomorrow morning", token).json(), reply.json())
        self.assertEqual(self.send(self.a.pk, "Changed", token).status_code, 409)
        self.assertEqual(PurchaseMessage.objects.count(), 2)
        self.api.force_authenticate(self.manager)
        rows = self.api.get(f"/api/chat/{self.a.pk}/messages").json()["messages"]
        self.assertEqual([row["body"] for row in rows], ["When can you deliver?", "Tomorrow morning"])
        self.api.force_authenticate(self.sales)
        self.assertEqual(self.api.get("/api/chat").status_code, 403)

    def test_message_cursors(self):
        self.api.force_authenticate(self.manager)
        for number in range(52):
            self.assertEqual(self.send(self.a.pk, str(number)).status_code, 201)
        path = f"/api/chat/{self.a.pk}/messages"
        recent = self.api.get(path).json()
        self.assertTrue(recent["more"])
        self.assertEqual(len(recent["messages"]), 50)
        earlier = self.api.get(path, {"before": recent["messages"][0]["id"]}).json()
        self.assertEqual([message["body"] for message in earlier["messages"]], ["0", "1"])
        self.assertFalse(earlier["more"])
        later = self.api.get(path, {"after": recent["messages"][-2]["id"]}).json()
        self.assertEqual([message["body"] for message in later["messages"]], ["51"])


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class Week13RecoveryTests(TestCase):
    email = "warehouse.test@gmail.com"
    password = "Test-Stockroom-Proof+673"
    request_path = "/api/auth/password-reset/request"
    confirm_path = "/api/auth/password-reset/confirm"

    def setUp(self):
        cache.clear()
        self.staff = Staff.objects.create_user(
            username="employee@stockroom.local", password="LocalPassword-183",
            recovery_email=self.email, role="manager",
        )
        self.api = APIClient(enforce_csrf_checks=True)
        self.api.get("/api/auth/csrf")
        self.csrf = self.api.cookies["csrftoken"].value
        mail.outbox = []

    def request_code(self, email):
        # Run the delivered callback inline while retaining the real mail backend call.
        def deliver_inline(address, code):
            from .recovery import deliver_code, mail_slots
            self.assertTrue(mail_slots.acquire(blocking=False))
            deliver_code(address, code)
        with patch("inventory.recovery.queue_code", side_effect=deliver_inline), self.captureOnCommitCallbacks(execute=True):
            return self.api.post(self.request_path, {"email": email}, format="json", HTTP_X_CSRFTOKEN=self.csrf)

    def confirm(self, code, password=None, email=None):
        return self.api.post(self.confirm_path, {
            "code": code, "email": email or self.email, "password": password or self.password,
        }, format="json", HTTP_X_CSRFTOKEN=self.csrf)

    def delivered_code(self):
        return re.search(r"\b\d{8}\b", mail.outbox[-1].body).group()

    def test_confirmed_email_generic_responses_and_one_time_code(self):
        self.assertEqual(self.api.post(self.request_path, {"email": self.email}, format="json").status_code, 403)
        known = self.request_code(self.email.upper())
        unknown = self.request_code("unknown@gmail.com")
        self.assertEqual((known.status_code, known.json()), (unknown.status_code, unknown.json()))
        self.assertEqual(known.status_code, 202)
        self.assertEqual(mail.outbox[0].to, [self.email])
        self.assertEqual(self.request_code(self.email).json(), unknown.json())
        self.assertEqual(len(mail.outbox), 1)
        code = self.delivered_code()
        existing = APIClient()
        self.assertTrue(existing.login(username=self.staff.username, password="LocalPassword-183"))
        self.assertEqual(self.confirm(code, email="unknown@gmail.com").status_code, 400)
        self.assertEqual(self.confirm(code, password="1234567890").status_code, 400)
        self.assertEqual(self.confirm(code).status_code, 200)
        self.assertEqual(self.confirm(code).status_code, 400)
        self.assertEqual(existing.get("/api/auth/me").status_code, 403)
        self.assertFalse(existing.login(username=self.staff.username, password="LocalPassword-183"))
        self.assertTrue(existing.login(username=self.staff.username, password=self.password))

    def test_expired_code_and_attempt_limit(self):
        self.request_code(self.email)
        code = self.delivered_code()
        wrong = "00000000" if code != "00000000" else "11111111"
        for _ in range(5):
            self.assertEqual(self.confirm(wrong).status_code, 400)
        self.assertEqual(self.confirm(code).status_code, 400)
        self.assertEqual(PasswordResetChallenge.objects.get(staff=self.staff).attempts, 5)
        PasswordResetChallenge.objects.filter(staff=self.staff).update(issued_at=timezone.now() - timedelta(minutes=11))
        self.request_code(self.email)
        new_code = self.delivered_code()
        self.assertEqual(len(mail.outbox), 2)
        PasswordResetChallenge.objects.filter(staff=self.staff).update(issued_at=timezone.now() - timedelta(minutes=11))
        self.assertEqual(self.confirm(new_code).status_code, 400)
