from uuid import uuid4

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Customer, DirectConversation, DirectMessage, PurchaseConversation, PurchaseMessage,
    PurchaseOrder, Staff, Supplier,
)


class StaffChatTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        supplier = Supplier.objects.create(name="Demo Supplier", lead_days=2)
        store = Customer.objects.create(shop_name="Demo Shop")
        cls.manager = Staff.objects.create(username="manager@example.com", full_name="Manager", role="manager")
        cls.admin = Staff.objects.create(username="admin@example.com", full_name="Әкімші", role="admin")
        cls.sales = Staff.objects.create(username="sales@example.com", full_name="Sales")
        cls.support = Staff.objects.create(username="support@example.com", full_name="Support", role="tech_support")
        cls.vendor = Staff.objects.create(username="supplier@example.com", role="supplier", supplier=supplier)
        cls.shop = Staff.objects.create(username="shop@example.com", shop=store)
        cls.inactive = Staff.objects.create(username="inactive@example.com", is_active=False)
        cls.po = PurchaseOrder.objects.create(supplier=supplier, staff=cls.manager, expected_on=timezone.localdate())

    def direct(self, peer):
        return f"/api/chat/staff/{peer.pk}/messages"

    def send(self, path, body, request_id=None):
        return self.api.post(path, {"request_id": str(request_id or uuid4()), "body": body}, format="json")

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.manager)

    def test_directory_filters_employees_without_exposing_login(self):
        path = "/api/chat/staff"
        rows = self.api.get(path).json()
        self.assertEqual({row["id"] for row in rows}, {self.admin.pk, self.sales.pk, self.support.pk})
        self.assertTrue(all(set(row) == {"id", "name", "role"} for row in rows))
        self.assertEqual(self.api.get(path, {"name": "ӘКІМ"}).json(), [
            {"id": self.admin.pk, "name": self.admin.full_name, "role": "admin"},
        ])

    def test_members_exchange_messages_and_share_one_conversation(self):
        path = self.direct(self.admin)
        self.assertEqual(self.api.get(path).json()["messages"], [])
        self.assertEqual(DirectConversation.objects.count(), 0)
        token = uuid4()
        first = self.send(path, "Is the order ready?", token)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(self.send(path, "Is the order ready?", token).status_code, 200)
        self.assertEqual(self.send(path, "Changed text", token).status_code, 409)
        self.api.force_authenticate(self.admin)
        path = self.direct(self.manager)
        self.assertEqual(self.api.get(path).json()["messages"], [first.json()])
        self.assertEqual(self.send(path, "Yes, packing is complete.").status_code, 201)
        self.api.force_authenticate(self.manager)
        rows = self.api.get(self.direct(self.admin), {"after": first.json()["id"]}).json()["messages"]
        self.assertEqual([row["body"] for row in rows], ["Yes, packing is complete."])
        self.assertEqual(DirectConversation.objects.count(), 1)
        self.assertEqual(DirectMessage.objects.count(), 2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DirectConversation.objects.create(first=self.manager, second=self.admin)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DirectConversation.objects.create(first=self.admin, second=self.manager)

    def test_other_staff_cannot_read_pair_and_external_roles_are_blocked(self):
        self.assertEqual(self.send(self.direct(self.admin), "Private warehouse message").status_code, 201)
        self.api.force_authenticate(self.sales)
        self.assertEqual(self.api.get(self.direct(self.admin)).json()["messages"], [])
        for peer in (self.sales, self.inactive, self.vendor, self.shop):
            self.assertEqual(self.api.get(self.direct(peer)).status_code, 404)
            self.assertEqual(self.send(self.direct(peer), "This must fail").status_code, 404)
        for user in (self.vendor, self.shop):
            self.api.force_authenticate(user)
            self.assertEqual(self.api.get("/api/chat/staff").status_code, 403)
            self.assertEqual(self.api.get(self.direct(self.manager)).status_code, 403)
            self.assertEqual(self.send(self.direct(self.manager), "This must fail").status_code, 403)
        self.assertEqual(DirectConversation.objects.count(), 1)
        self.assertEqual(DirectMessage.objects.count(), 1)

    def test_profanity_is_rejected_in_both_chats_before_database_write(self):
        paths = (self.direct(self.admin), f"/api/chat/{self.po.pk}/messages")
        for path in paths:
            token = uuid4()
            for text in ("FUCK!", "ну, БЛЯТЬ!", "Боқ!", "ｓｈｉｔ", "s\u200bhit"):
                with self.subTest(path=path, text=text):
                    denied = self.send(path, text, token)
                    self.assertEqual(denied.status_code, 400)
                    self.assertEqual(denied.json(), {"detail": "Please remove profanity before sending the message."})
            self.assertFalse(DirectConversation.objects.exists() if path == paths[0] else PurchaseConversation.objects.exists())
            self.assertEqual(self.send(path, "Dispatch Dickson’s order 10 — Сукафе", token).status_code, 201)
            self.assertEqual(len(self.api.get(path).json()["messages"]), 1)
        self.assertEqual(DirectMessage.objects.count(), 1)
        self.assertEqual(PurchaseMessage.objects.count(), 1)

    def test_many_languages_and_disguised_profanity(self):
        path = self.direct(self.admin)
        for body in (
            "shiiiit", "S.H.I.T!", "s h i t", "sh!t!", "sh1t", "shіt", "f**ck", "f**k", "s**t",
            "Бляяяять!", "Қотааақ!", "¡Mierda!", "Putain !", "Scheiße!", "Vaffanculo!",
            "Caralho!", "SİKTİR!", "Kurwa!", "Їбати!",
        ):
            with self.subTest(body=body):
                self.assertEqual(self.send(path, body).status_code, 400)
        self.assertFalse(DirectMessage.objects.exists())
        for body in ("Shipping is complete.", "Please assist G. Dickson.", "Product label R.U.S.", "PO-01345"):
            self.assertEqual(self.send(path, body).status_code, 201)


    def test_supplier_messages_are_moderated_too(self):
        self.api.force_authenticate(self.vendor)
        path = f"/api/chat/{self.po.pk}/messages"
        self.assertEqual(self.send(path, "SHIT").status_code, 400)
        self.assertFalse(PurchaseMessage.objects.exists())
        self.assertEqual(self.send(path, "Delivery on Friday.").status_code, 201)
