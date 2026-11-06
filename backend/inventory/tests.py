import csv
from pathlib import Path
from unittest.mock import patch
from django.core.management import call_command
from django.db import IntegrityError, transaction, connections
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import Product, Order, OrderItem, StockMovement, Staff, Customer
from . import services


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class StockroomTests(TestCase):
    def setUp(self):
        call_command("seed", verbosity=0, stdout=__import__("io").StringIO())
        self.client = APIClient()
        self.client.login(username="manager@stockroom.local", password="Stockroom2026!")
        self.manager = Staff.objects.get(role="manager")

    def order(self, qty=1, sku="BAS-C65W-WHT", **kw):
        return self.client.post(
            "/api/orders",
            {
                "customer_id": Customer.objects.first().pk,
                "channel": "sales_manager",
                "lines": [{"sku": sku, "qty": qty}],
                **kw,
            },
            format="json",
        )

    def available(self):
        return services.available(Product.objects.get(pk="BAS-C65W-WHT"))

    def test_01_acceptance(self):
        self.assertEqual(self.available(), 4)
        self.assertEqual(self.order(5).status_code, 409)
        self.assertEqual(self.available(), 4)

    def test_02_exact_stock(self):
        self.assertEqual(self.order(4).status_code, 201)
        self.assertEqual(self.available(), 0)

    def test_03_reserve_without_shelf_change(self):
        self.order(2)
        self.assertEqual(self.available(), 2)
        self.assertEqual(Product.objects.get(pk="BAS-C65W-WHT").qty_in_stock, 10)

    def test_04_cancel_once(self):
        oid = self.order(2).data["order_id"]
        self.assertEqual(self.client.post(f"/api/orders/{oid}/cancel").status_code, 200)
        self.assertEqual(self.available(), 4)
        self.assertEqual(self.client.post(f"/api/orders/{oid}/cancel").status_code, 409)

    def test_05_pack_and_ship(self):
        oid = self.order(2).data["order_id"]
        self.client.post(f"/api/orders/{oid}/pack")
        self.assertEqual(self.available(), 2)
        self.client.post(f"/api/orders/{oid}/ship")
        self.assertEqual(self.available(), 2)
        self.assertEqual(Product.objects.get(pk="BAS-C65W-WHT").qty_in_stock, 8)
        self.assertEqual(self.client.post(f"/api/orders/{oid}/ship").status_code, 409)

    def test_06_atomic_multiline(self):
        r = self.order(
            lines=[{"sku": "ANK-C20W-WHT", "qty": 2}, {"sku": "BAS-C65W-WHT", "qty": 5}]
        )
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Order.objects.count(), 3)
        self.assertEqual(services.available(Product.objects.get(pk="ANK-C20W-WHT")), 5)

    def test_07_audit_failure_rolls_back(self):
        data = {
            "customer": Customer.objects.first(),
            "channel": "website",
            "note": "",
            "lines": [{"sku": "BAS-C65W-WHT", "qty": 2}],
        }
        with patch(
            "inventory.services.record",
            side_effect=RuntimeError("Injected audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                services.confirm(data, self.manager)
        self.assertEqual(self.available(), 4)
        self.assertEqual(Order.objects.count(), 3)

    def test_08_permissions(self):
        self.client.login(username="sales@stockroom.local", password="Stockroom2026!")
        self.assertEqual(self.order().status_code, 201)
        self.assertEqual(self.client.get("/api/movements").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/stock/receive",
                {
                    "sku": "HOC-U72-BLK",
                    "quantity": 1,
                    "source": "manual",
                    "note": "test",
                },
                format="json",
            ).status_code,
            403,
        )

    def test_09_registration_and_csrf(self):
        c = APIClient(enforce_csrf_checks=True)
        body = {
            "login": "new@example.com",
            "password": "LongPassword123",
            "full_name": "Test Person",
            "role": "admin",
        }
        self.assertEqual(
            c.post("/api/auth/register", body, format="json").status_code, 403
        )
        c.get("/api/auth/csrf")
        token = c.cookies["csrftoken"].value
        r = c.post("/api/auth/register", body, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["role"], "sales")
        self.assertEqual(c.get("/api/auth/me").status_code, 200)
        user = Staff.objects.get(username="new@example.com")
        self.assertNotEqual(user.password, body["password"])

    def test_10_receiving_and_audit(self):
        r = self.client.post(
            "/api/stock/receive",
            {
                "sku": "HOC-U72-BLK",
                "quantity": 5,
                "source": "manual",
                "note": "Delivery 001",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Product.objects.get(pk="HOC-U72-BLK").qty_in_stock, 9)
        self.assertTrue(
            StockMovement.objects.filter(
                product_id="HOC-U72-BLK",
                source="manual",
                staff=self.manager,
                note="Delivery 001",
            ).exists()
        )

    def test_11_reserved_protected(self):
        r = self.client.post(
            "/api/stock/adjust",
            {
                "sku": "BAS-C65W-WHT",
                "quantity": -5,
                "source": "manual",
                "note": "Recount",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.available(), 4)

    def test_12_data_rules(self):
        line = OrderItem.objects.first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(
                order=line.order,
                product=line.product,
                qty_reserved=1,
                unit_price_kzt=100,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            StockMovement.objects.filter(pk=StockMovement.objects.first().pk).update(
                note="tampered"
            )

    def test_13_history_and_low_unreserved(self):
        p = next(
            p
            for p in self.client.get("/api/products").data
            if p["sku"] == "HOC-U72-BLK"
        )
        self.assertEqual((p["available"], p["reserved"]), (4, 0))
        self.assertEqual(
            len([o for o in self.client.get("/api/orders").data if o["stale"]]), 1
        )

    def test_14_historical_price(self):
        oid = self.order().data["order_id"]
        Product.objects.filter(pk="BAS-C65W-WHT").update(price_kzt=1)
        o = next(o for o in self.client.get("/api/orders").data if o["order_id"] == oid)
        self.assertEqual(o["total_kzt"], 17990)

    def test_15_twenty_data_records(self):
        cases = (
            [(i, 201) for i in range(1, 11)]
            + [(v, 400) for v in [0, -1, 1.5, True, "2", None, {}, [], 100001]]
            + [(21, 409)]
        )
        results = []
        for i, (qty, expected) in enumerate(cases, 1):
            r = self.order(qty, sku="ANK-C30W-BLK")
            self.assertEqual(r.status_code, expected, (i, r.data))
            results.append([i, str(qty), expected, r.status_code, "PASS"])
            if r.status_code == 201:
                self.client.post("/api/orders/" + r.data["order_id"] + "/cancel")
        with (Path(__file__).resolve().parents[2] / "qa/data_results.csv").open(
            "w", newline=""
        ) as f:
            w = csv.writer(f)
            w.writerow(["Record", "Quantity", "Expected", "Actual", "Result"])
            w.writerows(results)
