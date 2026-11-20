from datetime import timedelta
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Notification, Product, PurchaseReceipt, Staff, StockMovement


class Week12Tests(TestCase):
    def setUp(self):
        self.manager = Staff.objects.create(username="warehouse", role="manager")
        self.admin = Staff.objects.create(username="admin", role="admin")
        self.sales = Staff.objects.create(username="sales", role="sales")
        self.product = Product.objects.create(
            sku="DEM-C35W-WHT", product_name="Demo USB-C Charger", brand="Demo",
            category="Chargers", price_kzt=5000, qty_in_stock=5, reorder_level=5,
            location="A-01",
        )
        self.api = APIClient()
        self.api.force_authenticate(self.manager)
        self.supplier = {
            "name": "Test Supplier", "location": "Almaty", "agreement": "Test terms",
            "agreement_active": True, "lead_days": 5,
        }
        self.supplier_id = self.api.post("/api/suppliers", self.supplier, format="json").json()["id"]
        self.offer_path = f"/api/suppliers/{self.supplier_id}/offers/{self.product.sku}"
        self.assertEqual(self.api.put(
            self.offer_path, {"unit_cost": 2100, "available_qty": 15}, format="json"
        ).status_code, 200)

    def order(self, qty=10):
        return self.api.post("/api/purchases", {
            "supplier_id": self.supplier_id, "lines": [{"sku": self.product.sku, "qty": qty}],
        }, format="json")

    def receipt(self, order_id, qty, receipt_id=None, sku=None):
        return self.api.post(f"/api/purchases/{order_id}/receipts", {
            "receipt_id": str(receipt_id or uuid4()),
            "lines": [{"sku": sku or self.product.sku, "qty": qty}],
        }, format="json")

    def test_barcode_survives_edit_and_exists_for_bulk_csv_products(self):
        sku = self.product.sku
        path = "/api/products/barcode"
        code = "SR-" + sku
        self.assertEqual(self.api.get(path, {"code": code}).json()["sku"], sku)
        self.assertEqual(self.api.get(path, {"code": "SR-UNKNOWN"}).status_code, 404)
        Product.objects.filter(pk=sku).update(product_name="New name", price_kzt=6000)
        self.assertEqual(self.api.get(path, {"code": code}).json()["product_name"], "New name")
        csv = SimpleUploadedFile("catalogue.csv", (
            b"sku,product_name,brand,category,price_kzt,reorder_level,location\n"
            b"DEM-NEW-BLK,New cable,Demo,Cables,1500,3,A-02\n"
        ))
        self.assertEqual(self.api.post("/api/catalog-csv", {"file": csv}).status_code, 201)
        self.assertEqual(self.api.get(path, {"code": "SR-DEM-NEW-BLK"}).json()["sku"], "DEM-NEW-BLK")

    def test_purchase_checks_agreements_stock_roles_and_price_snapshot(self):
        self.assertEqual(self.order(16).status_code, 409)
        supplier = {**self.supplier, "agreement_active": False}
        self.api.put(f"/api/suppliers/{self.supplier_id}", supplier, format="json")
        self.assertEqual(self.order().status_code, 409)
        self.api.put(f"/api/suppliers/{self.supplier_id}", self.supplier, format="json")
        created = self.order()
        self.assertEqual(created.status_code, 201)
        order = created.json()
        self.assertEqual(order["expected_on"], (timezone.localdate() + timedelta(days=5)).isoformat())
        self.assertEqual(order["lines"][0]["unit_cost"], 2100)
        self.api.put(self.offer_path, {"unit_cost": 3000, "available_qty": 8}, format="json")
        self.assertEqual(self.api.get(f"/api/purchases/{order['id']}").json()["lines"][0]["unit_cost"], 2100)
        self.api.force_authenticate(self.sales)
        self.assertEqual(self.api.get("/api/purchases").status_code, 403)
        self.assertEqual(self.order().status_code, 403)
        self.assertEqual(self.receipt(order["id"], 1).status_code, 403)

    def test_partial_receipt_remaining_stock_history_and_retries(self):
        order_id = self.order().json()["id"]
        endpoint = f"/api/purchases/{order_id}"
        self.assertEqual(self.api.post(endpoint + "/ship").json()["status"], "in_transit")
        self.assertEqual(self.receipt(order_id, 1, sku="UNKNOWN").status_code, 400)
        token = uuid4()
        first = self.receipt(order_id, 6, token)
        self.assertEqual(first.status_code, 201)
        retry = self.receipt(order_id, 6, token)
        self.assertEqual((retry.status_code, retry.json()), (200, first.json()))
        self.assertEqual(self.receipt(order_id, 5, token).status_code, 409)
        self.assertEqual(self.receipt(order_id, 5).status_code, 409)
        order = self.api.get(endpoint).json()
        self.assertEqual((order["status"], order["lines"][0]["remaining"]), ("partial", 4))
        self.assertEqual(Product.objects.get(pk=self.product.pk).qty_in_stock, 11)
        self.assertEqual(Notification.objects.filter(recipient=self.manager).count(), 1)
        self.assertEqual(self.receipt(order_id, 4).status_code, 201)
        self.assertEqual(self.receipt(order_id, 1).status_code, 409)
        order = self.api.get(endpoint).json()
        self.assertEqual((order["status"], order["lines"][0]["remaining"]), ("received", 0))
        self.assertEqual(PurchaseReceipt.objects.count(), 2)
        self.assertEqual(Product.objects.get(pk=self.product.pk).qty_in_stock, 15)
        self.assertEqual(
            list(StockMovement.objects.order_by("pk").values_list("movement_type", "physical_delta")),
            [("purchase_receipt", 6), ("purchase_receipt", 4)],
        )

    def test_alert_only_on_threshold_crossing_and_read_status_per_recipient(self):
        for quantity in (-2, -1):
            self.assertEqual(self.api.post("/api/stock/adjust", {
                "sku": self.product.sku, "source": "manual", "quantity": quantity,
                "note": "Physical check",
            }, format="json").status_code, 200)
        data = self.api.get("/api/notifications").json()
        self.assertEqual(data["unread"], 1)
        item = data["items"][0]
        self.assertIn("3 available, minimum 5", item["message"])
        path = f"/api/notifications/{item['id']}/read"
        self.api.force_authenticate(self.admin)
        self.assertEqual(self.api.post(path).status_code, 404)
        self.assertEqual(self.api.get("/api/notifications").json()["unread"], 1)
        self.api.force_authenticate(self.manager)
        self.assertEqual(self.api.post(path).status_code, 200)
        self.assertEqual(self.api.get("/api/notifications").json()["unread"], 0)
