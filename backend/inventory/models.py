from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q, Value
from django.db.models.functions import Concat, Lower
from django.utils import timezone


class Staff(AbstractUser):
    full_name = models.CharField(max_length=80)
    role = models.CharField(
        choices=[
            ("sales", "Sales"), ("manager", "Manager"), ("admin", "Admin"),
            ("tech_support", "Tech Support"),
            ("supplier", "Supplier"),
        ],
        max_length=16,
        default="sales",
    )
    shop = models.ForeignKey("Customer", null=True, blank=True, on_delete=models.PROTECT)
    recovery_email = models.EmailField(null=True, blank=True, verbose_name="verified recovery email")
    supplier = models.ForeignKey("Supplier", null=True, blank=True, on_delete=models.PROTECT)
    phone = models.CharField(max_length=25, blank=True)
    job_title = models.CharField(max_length=80, blank=True)
    avatar = models.TextField(blank=True)

    @property
    def store_id(self):
        return self.shop_id if self.role == "sales" else None

    class Meta:
        db_table = "staff"
        constraints = [
            models.CheckConstraint(
                condition=Q(role__in=["sales", "manager", "admin", "tech_support", "supplier"]), name="valid_role"
            ),
            models.CheckConstraint(
                condition=Q(role="supplier", supplier__isnull=False, shop__isnull=True, is_staff=False, is_superuser=False)
                | (~Q(role="supplier") & Q(supplier__isnull=True)),
                name="staff_supplier_role_binding",
            ),
            models.UniqueConstraint(Lower("recovery_email"), name="unique_staff_recovery_email"),
        ]


class Customer(models.Model):
    shop_name = models.CharField(max_length=80, unique=True, db_collation="nocase")
    contact_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=25)

    class Meta:
        db_table = "customer"


class Product(models.Model):
    sku = models.CharField(max_length=24, primary_key=True)
    barcode = models.GeneratedField(
        expression=Concat(Value("SR-"), "sku"),
        output_field=models.CharField(max_length=27),
        db_persist=True,
        unique=True,
    )
    product_name = models.CharField(max_length=100)
    brand = models.CharField(max_length=40)
    category = models.CharField(max_length=20)
    price_kzt = models.PositiveIntegerField()
    qty_in_stock = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=5)
    location = models.CharField(max_length=30)

    class Meta:
        db_table = "product"
        constraints = [
            models.CheckConstraint(condition=Q(price_kzt__gt=0), name="positive_price")
        ]


class Order(models.Model):
    order_id = models.CharField(max_length=40, primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT)
    channel = models.CharField(
        max_length=20, choices=[("website", "Website"), ("sales_manager", "Phone")]
    )
    status = models.CharField(max_length=10, default="confirmed")
    confirmed_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        db_table = "orders"
        indexes = [models.Index(fields=["status", "confirmed_at"], name="orders_status_date_idx")]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["confirmed", "packed", "shipped", "cancelled"]),
                name="valid_order_status",
            ),
            models.CheckConstraint(
                condition=Q(channel__in=["website", "sales_manager"]),
                name="valid_channel",
            ),
        ]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, db_column="sku", related_name="order_items"
    )
    qty_reserved = models.PositiveIntegerField()
    unit_price_kzt = models.PositiveIntegerField()

    class Meta:
        db_table = "order_item"
        constraints = [
            models.UniqueConstraint(
                fields=["order", "product"], name="unique_order_product"
            ),
            models.CheckConstraint(
                condition=Q(qty_reserved__gt=0), name="positive_order_quantity"
            ),
        ]


class StockMovement(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, db_column="sku")
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, null=True, blank=True)
    movement_type = models.CharField(max_length=20)
    physical_delta = models.IntegerField(default=0)
    reserved_delta = models.IntegerField(default=0)
    moved_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=10, default="system")
    note = models.CharField(max_length=300)

    class Meta:
        db_table = "stock_movement"
        constraints = [
            models.CheckConstraint(
                condition=~Q(physical_delta=0) | ~Q(reserved_delta=0),
                name="nonzero_movement",
            )
        ]


class Draft(models.Model):
    id = models.UUIDField(primary_key=True)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    data = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)
    order = models.OneToOneField(Order, null=True, on_delete=models.PROTECT)
    is_cart = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["staff"], condition=Q(is_cart=True, order__isnull=True),
                name="one_open_cart_per_staff",
            )
        ]


class StockReturn(models.Model):
    request_id = models.UUIDField(unique=True)
    line = models.ForeignKey(OrderItem, on_delete=models.PROTECT)
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT)
    good = models.PositiveIntegerField()
    defective = models.PositiveIntegerField()
    reason = models.CharField(max_length=100)
    comment = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=12, default="pending")
    reviewed_by = models.ForeignKey(
        Staff, null=True, blank=True, on_delete=models.PROTECT, related_name="reviewed_returns"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["pending", "received", "rejected"]), name="valid_return_status"
            ),
            models.CheckConstraint(
                condition=Q(good__gt=0) | Q(defective__gt=0), name="positive_return_quantity"
            ),
        ]


class Issue(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT)
    title = models.CharField(max_length=120)
    description = models.TextField()
    status = models.CharField(max_length=16, default="open")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["open", "in_progress", "resolved"]), name="valid_issue_status"
            ),
        ]


class IssueAttachment(models.Model):
    issue = models.OneToOneField(Issue, related_name="attachment", on_delete=models.CASCADE)
    content = models.BinaryField()
    content_type = models.CharField(max_length=10)


class Supplier(models.Model):
    name = models.CharField(max_length=100, unique=True)
    location = models.CharField(max_length=150)
    agreement = models.CharField(max_length=300, blank=True)
    agreement_active = models.BooleanField(default=False)
    lead_days = models.PositiveSmallIntegerField()


class SupplierOffer(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="offers")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    unit_cost = models.PositiveIntegerField()
    available_qty = models.PositiveIntegerField(null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["supplier", "product"], name="one_offer_per_supplier_product"),
            models.CheckConstraint(condition=Q(unit_cost__gt=0), name="positive_supplier_cost"),
        ]


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        ORDERED = "ordered", "Ordered"
        IN_TRANSIT = "in_transit", "In transit"
        PARTIAL = "partial", "Partially received"
        RECEIVED = "received", "Received"

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=Status, default=Status.ORDERED)
    created_at = models.DateTimeField(auto_now_add=True)
    expected_on = models.DateField()


class PurchaseLine(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    ordered_qty = models.PositiveIntegerField()
    unit_cost = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="one_line_per_purchase_product"),
            models.CheckConstraint(
                condition=Q(ordered_qty__gt=0, unit_cost__gt=0),
                name="positive_purchase_quantity_and_cost",
            ),
        ]


class PurchaseReceipt(models.Model):
    id = models.UUIDField(primary_key=True)
    order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="receipts")
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class PurchaseReceiptLine(models.Model):
    receipt = models.ForeignKey(PurchaseReceipt, on_delete=models.PROTECT, related_name="lines")
    purchase_line = models.ForeignKey(PurchaseLine, on_delete=models.PROTECT, related_name="receipts")
    qty = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["receipt", "purchase_line"], name="one_line_per_receipt_product"),
            models.CheckConstraint(condition=Q(qty__gt=0), name="positive_receipt_quantity"),
        ]


class Notification(models.Model):
    recipient = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=250)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True)


class OrderScan(models.Model):
    id = models.UUIDField(primary_key=True)
    line = models.ForeignKey(OrderItem, on_delete=models.PROTECT, related_name="scans")
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT)
    barcode = models.CharField(max_length=27)
    source = models.CharField(max_length=6, choices=[("camera", "Camera"), ("manual", "Manual"), ("demo", "Demo")])
    created_at = models.DateTimeField(default=timezone.now)
    voided_at = models.DateTimeField(null=True)
    voided_by = models.ForeignKey(Staff, null=True, on_delete=models.PROTECT, related_name="voided_scans")

    class Meta:
        indexes = [
            models.Index(fields=["line", "voided_at", "created_at"], name="order_scan_line_active_idx"),
        ]


class PurchaseConversation(models.Model):
    purchase = models.OneToOneField(PurchaseOrder, primary_key=True, on_delete=models.PROTECT, related_name="conversation")
    created_at = models.DateTimeField(auto_now_add=True)


class PurchaseMessage(models.Model):
    request_id = models.UUIDField(unique=True)
    conversation = models.ForeignKey(PurchaseConversation, on_delete=models.PROTECT, related_name="messages")
    sender = models.ForeignKey(Staff, on_delete=models.PROTECT)
    body = models.CharField(max_length=1500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["conversation", "id"], name="purchase_message_thread_idx")]


class PasswordResetChallenge(models.Model):
    staff = models.OneToOneField(Staff, primary_key=True, on_delete=models.CASCADE)
    token = models.UUIDField(unique=True)
    digest = models.CharField(max_length=64)
    issued_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True)


class ProfileSecurityChallenge(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    action = models.CharField(max_length=14)
    token = models.UUIDField(unique=True)
    email = models.EmailField()
    digest = models.CharField(max_length=64)
    old_digest = models.CharField(max_length=64, blank=True)
    issued_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["staff", "action"], name="unique_profile_security_action"),
        ]


class DirectConversation(models.Model):
    first = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name="direct_conversations_first")
    second = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name="direct_conversations_second")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(first_id__lt=models.F("second_id")), name="direct_members_sorted"),
            models.UniqueConstraint(fields=["first", "second"], name="direct_members_unique"),
        ]


class DirectMessage(models.Model):
    request_id = models.UUIDField(unique=True)
    conversation = models.ForeignKey(DirectConversation, on_delete=models.PROTECT, related_name="messages")
    sender = models.ForeignKey(Staff, on_delete=models.PROTECT)
    body = models.CharField(max_length=1500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["conversation", "id"], name="direct_message_thread_idx")]
