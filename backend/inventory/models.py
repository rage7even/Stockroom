from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class Staff(AbstractUser):
    full_name = models.CharField(max_length=80)
    role = models.CharField(
        max_length=10,
        choices=[("sales", "Sales"), ("manager", "Manager"), ("admin", "Admin")],
        default="sales",
    )

    class Meta:
        db_table = "staff"
        constraints = [
            models.CheckConstraint(
                condition=Q(role__in=["sales", "manager", "admin"]), name="valid_role"
            )
        ]


class Customer(models.Model):
    shop_name = models.CharField(max_length=80, unique=True, db_collation="nocase")
    contact_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=25)

    class Meta:
        db_table = "customer"


class Product(models.Model):
    sku = models.CharField(max_length=24, primary_key=True)
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
