from io import BytesIO, StringIO
from uuid import uuid4

from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import Customer, Order, Product, Staff, StockReturn


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class Week11Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed", stdout=StringIO())

    def setUp(self):
        self.manager = Staff.objects.get(role="manager")
        self.sales = Staff.objects.get(role="sales")
        self.admin = Staff.objects.get(role="admin")
        self.api = APIClient()
        self.api.force_authenticate(self.manager)

    def test_drafts_persist_and_confirm_once(self):
        path = f"/api/drafts/{uuid4()}"
        other = f"/api/drafts/{uuid4()}"
        order_data = {
            "customer_id": Customer.objects.first().pk,
            "channel": "sales_manager",
            "note": "Draft A",
            "lines": [{"sku": "BAS-C65W-WHT", "qty": 2}],
        }
        self.assertEqual(self.api.put(path, order_data, format="json").status_code, 200)
        self.assertEqual(self.api.put(other, {**order_data, "note": "Draft B"}, format="json").status_code, 200)
        self.api.force_authenticate(self.sales)
        self.assertEqual(self.api.get("/api/drafts").data, [])
        self.assertEqual(self.api.put(path, order_data, format="json").status_code, 404)
        self.api.force_authenticate(self.manager)
        self.assertEqual(len(self.api.get("/api/drafts").data), 2)
        self.assertEqual(Order.objects.count(), 3)
        failure = {**order_data, "lines": [{"sku": "BAS-C65W-WHT", "qty": 5}]}
        self.assertEqual(self.api.post(path + "/confirm", failure, format="json").status_code, 409)
        first = self.api.post(path + "/confirm", order_data, format="json")
        second = self.api.post(path + "/confirm", order_data, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data, second.data)
        self.assertEqual(Order.objects.count(), 4)
        self.assertEqual([row["note"] for row in self.api.get("/api/drafts").data], ["Draft B"])

    def test_return_splits_stock_and_enforces_limit(self):
        call_command("seed_week11", stdout=StringIO())
        call_command("seed_week11", stdout=StringIO())
        order = Order.objects.get(note="Week 11 return demo")
        path = f"/api/returns/{order.pk}"
        product = Product.objects.get(pk="DEM-C35W-WHT")
        self.assertEqual(product.qty_in_stock, 7)
        data = {
            "sku": product.pk, "good": 3, "defective": 2, "reason": "Damaged packaging",
            "comment": "Two chargers failed inspection", "request_id": str(uuid4()),
        }
        self.assertEqual(self.api.post(path, data, format="json").status_code, 403)
        shop = Staff.objects.get(username="shop@stockroom.local")
        self.api.force_authenticate(shop)
        self.assertEqual(self.api.get("/api/returns").status_code, 403)
        self.assertEqual(self.api.get("/api/returns/ORD-2026-0001").status_code, 404)
        self.assertEqual(self.api.post(path, data, format="json").status_code, 201)
        self.assertEqual(self.api.post(path, data, format="json").status_code, 200)
        excess = {**data, "good": 0, "defective": 1, "request_id": str(uuid4())}
        self.assertEqual(self.api.post(path, excess, format="json").status_code, 409)
        product.refresh_from_db()
        self.assertEqual(product.qty_in_stock, 7)
        item = StockReturn.objects.get()
        review = f"{path}/{item.pk}/review"
        self.assertEqual(self.api.post(review, {"status": "received"}, format="json").status_code, 403)
        self.api.force_authenticate(self.manager)
        pending = self.api.get("/api/returns").data[0]
        self.assertEqual((pending["order_id"], pending["product_name"], pending["status"]),
                         (order.pk, product.product_name, "pending"))
        self.assertEqual(self.api.post(review, {"status": "received"}, format="json").status_code, 200)
        self.assertEqual(self.api.post(review, {"status": "received"}, format="json").status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.qty_in_stock, 10)
        self.assertEqual(StockReturn.objects.get().defective, 2)
        self.assertEqual(self.api.get("/api/returns").data[0]["status"], "received")
        catalogue = self.api.get("/api/products").data
        row = next(item for item in catalogue if item["sku"] == product.pk)
        self.assertEqual((row["available"], row["defective"]), (10, 2))
        self.api.force_authenticate(self.sales)
        self.assertEqual(self.api.get(path).status_code, 403)

    def test_issue_visibility_and_profile(self):
        self.api.force_authenticate(self.sales)
        issue = self.api.post("/api/issues", {"title": "Example", "description": "Steps"}, format="json")
        path = f"/api/issues/{issue.data['id']}"
        self.api.force_authenticate(self.manager)
        self.assertEqual(self.api.get("/api/issues").data["items"], [])
        self.assertEqual(self.api.patch(path, {"status": "resolved"}, format="json").status_code, 403)
        call_command("seed_week11", stdout=StringIO())
        self.api.force_authenticate(Staff.objects.get(role="tech_support"))
        self.assertEqual(self.api.get("/api/issues").data["items"][0]["id"], issue.data["id"])
        self.assertEqual(self.api.get("/api/orders").status_code, 403)
        self.assertEqual(self.api.patch(path, {"status": "resolved"}, format="json").status_code, 200)
        self.api.force_authenticate(self.sales)
        self.assertEqual(self.api.get("/api/issues").data["items"][0]["status"], "resolved")
        self.assertEqual(self.api.patch("/api/auth/me", {"full_name": "Demo Name", "role": "admin"}, format="json").status_code, 200)
        self.sales.refresh_from_db()
        self.assertEqual((self.sales.full_name, self.sales.role), ("Demo Name", "sales"))

    def test_issue_attachment_is_available_to_author_and_support(self):
        from PIL import Image

        call_command("seed_week11", stdout=StringIO())
        self.api.force_authenticate(self.sales)
        data = {"title": "Example", "description": "Steps"}
        bad = SimpleUploadedFile("bad.png", b"not an image", "image/png")
        self.assertEqual(self.api.post(
            "/api/issues", {**data, "attachment": bad}, format="multipart"
        ).status_code, 400)
        with BytesIO() as output:
            Image.new("RGB", (8, 8), "white").save(output, "PNG")
            image = SimpleUploadedFile("shot.png", output.getvalue(), "image/png")
        created = self.api.post("/api/issues", {**data, "attachment": image}, format="multipart")
        self.assertEqual(created.status_code, 201)
        url = created.data["attachment_url"]
        self.assertEqual(self.api.get("/api/issues").data["items"][0]["attachment_url"], url)
        self.assertEqual(self.api.get(url)["Content-Type"], "image/png")
        self.api.force_authenticate(self.manager)
        self.assertEqual(self.api.get(url).status_code, 404)
        self.api.force_authenticate(Staff.objects.get(role="tech_support"))
        self.assertEqual(self.api.get(url).status_code, 200)
        updated = self.api.patch(
            f"/api/issues/{created.data['id']}", {"status": "resolved"}, format="json"
        )
        self.assertEqual(updated.data["attachment_url"], url)

    def test_csv_import_is_atomic_and_export_contains_data(self):
        header = "sku,product_name,brand,category,price_kzt,reorder_level,location\n"
        first = "CSV-C30W-WHT,USB-C зарядка,Demo,Chargers,5990,4,CSV-A\n"
        invalid = "CSV-CBL1-BLK,Cable,Demo,Cables,wrong,5,CSV-B\n"

        def upload(content):
            file = SimpleUploadedFile("catalog.csv", content.encode("utf-8"), "text/csv")
            return self.api.post("/api/catalog-csv", {"file": file}, format="multipart")

        self.assertEqual(upload(header + first + invalid).status_code, 400)
        self.assertFalse(Product.objects.filter(pk="CSV-C30W-WHT").exists())
        self.assertEqual(upload(header + first).status_code, 201)
        self.assertEqual(upload(header + first).status_code, 400)
        result = self.api.get("/api/catalog-csv")
        self.assertIn("USB-C зарядка", result.content.decode("utf-8-sig"))

    def test_cart_is_private_and_checkout_reserves_once_at_current_price(self):
        sku = "BAS-C65W-WHT"
        endpoint = "/api/cart"
        first = self.api.post(endpoint, {"sku": sku}, format="json").data
        added = self.api.post(endpoint, {"sku": sku}, format="json").data
        self.assertEqual(added["lines"], [{"sku": sku, "qty": 2}])
        self.assertEqual(self.api.get("/api/drafts").data, [])
        self.assertEqual(Order.objects.count(), 3)

        self.api.force_authenticate(self.sales)
        self.assertEqual(self.api.get(endpoint).data["lines"], [])
        checkout = endpoint + f"/{added['id']}/checkout"
        self.assertEqual(self.api.post(checkout, {}, format="json").status_code, 404)

        self.api.force_authenticate(self.manager)
        self.assertEqual(self.api.get(endpoint).data, added)
        customer = Customer.objects.first()
        details = {
            "customer_id": customer.pk, "channel": "website", "note": "Cart order",
            "lines": [{"sku": sku, "qty": 5}], "version": first["version"],
        }
        self.assertEqual(self.api.put(endpoint, details, format="json").status_code, 409)
        details["version"] = added["version"]
        cart = self.api.put(endpoint, details, format="json").data
        self.assertEqual(self.api.post(checkout, {"version": cart["version"]}, format="json").status_code, 409)
        self.assertEqual(self.api.get(endpoint).data, cart)
        self.assertEqual(Order.objects.count(), 3)

        details.update(version=cart["version"], lines=[{"sku": sku, "qty": 2}])
        saved = self.api.put(endpoint, details, format="json").data
        Product.objects.filter(pk=sku).update(price_kzt=12345)
        version = {"version": saved["version"]}
        completed = self.api.post(checkout, version, format="json")
        self.assertEqual(completed.status_code, 201)
        self.assertEqual(self.api.post(checkout, version, format="json").data, completed.data)
        self.assertEqual(self.api.get(endpoint).data["lines"], [])
        self.assertEqual(Order.objects.count(), 4)
        item = Order.objects.get(pk=completed.data["order_id"]).lines.get()
        self.assertEqual((item.qty_reserved, item.unit_price_kzt), (2, 12345))

    def test_csv_preview_updates_catalogue_without_changing_stock_and_reports_rows(self):
        header = "sku,product_name,brand,category,price_kzt,reorder_level,location\n"
        update = "BAS-C65W-WHT,=Warehouse charger,Baseus,Chargers,13500,5,A-01\n"
        new = "CSV-CBL1-BLK,New cable,Demo,Cables,1000,2,CSV-B\n"
        invalid = "CSV-TEST-BLK,Bad cable,Demo,Cables,bad,5,CSV-C\n"
        sku = "BAS-C65W-WHT"
        before = Product.objects.get(pk=sku)

        def upload(operation, content):
            file = SimpleUploadedFile("catalog.csv", content.encode(), "text/csv")
            return self.api.post("/api/catalog-csv", {"file": file, "operation": operation}, format="multipart")

        preview = upload("preview", header + update + new)
        self.assertEqual((preview.data["created"], preview.data["updated"], preview.data["applied"]), (1, 1, False))
        self.assertEqual(Product.objects.get(pk=sku).price_kzt, before.price_kzt)
        rejected = upload("apply", header + update + new + invalid + new)
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual([error["row"] for error in rejected.data["errors"]], [4, 5])
        self.assertFalse(Product.objects.filter(pk="CSV-CBL1-BLK").exists())
        self.assertEqual(Product.objects.get(pk=sku).price_kzt, before.price_kzt)

        applied = upload("apply", header + update + new)
        self.assertTrue(applied.data["applied"])
        after = Product.objects.get(pk=sku)
        self.assertEqual((after.price_kzt, after.qty_in_stock), (13500, before.qty_in_stock))
        self.assertEqual(Product.objects.get(pk="CSV-CBL1-BLK").qty_in_stock, 0)
        export = self.api.get("/api/catalog-csv").content.decode("utf-8-sig")
        self.assertIn(",'=Warehouse charger,", export)
        self.assertEqual(upload("preview", export).data["updated"], 0)
