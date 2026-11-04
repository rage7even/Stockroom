from django.db import models
from django.db.models import F, Q, Sum, Subquery, OuterRef, Value
from django.db.models.functions import Coalesce
from django.utils import timezone


class Staff(models.Model):
    staff_id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=80)
    login = models.CharField(max_length=150, unique=True, db_collation='nocase')
    password_hash = models.TextField()
    role = models.CharField(max_length=10, choices=[(v, v) for v in ('sales', 'manager', 'admin')])
    is_active = models.IntegerField(default=1)

    class Meta:
        db_table = 'staff'
        constraints = [
            models.CheckConstraint(condition=Q(role__in=['sales', 'manager', 'admin']), name='staff_role_valid'),
            models.CheckConstraint(condition=Q(is_active__in=[0, 1]), name='staff_active_valid'),
        ]


class Session(models.Model):
    token_hash = models.CharField(max_length=64, primary_key=True)
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name='sessions')
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'session'


class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True)
    shop_name = models.CharField(max_length=80, unique=True, db_collation='nocase')
    contact_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=25)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'customer'


class ProductQuerySet(models.QuerySet):
    def inventory(self):
        reserved = OrderItem.objects.filter(
            sku_id=OuterRef('pk'), order__status__in=['confirmed', 'packed'],
        ).values('sku_id').annotate(total=Sum('qty_reserved')).values('total')
        return self.annotate(
            reserved=Coalesce(Subquery(reserved), Value(0)),
        ).annotate(available=F('qty_in_stock') - F('reserved'))


class Product(models.Model):
    sku = models.CharField(max_length=20, primary_key=True)
    product_name = models.CharField(max_length=100)
    brand = models.CharField(max_length=40)
    category = models.CharField(max_length=20)
    price_kzt = models.IntegerField()
    qty_in_stock = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=5)
    location = models.CharField(max_length=30)
    is_active = models.IntegerField(default=1)
    objects = ProductQuerySet.as_manager()

    class Meta:
        db_table = 'product'
        constraints = [
            models.CheckConstraint(condition=Q(price_kzt__gt=0), name='product_positive_price'),
            models.CheckConstraint(condition=Q(qty_in_stock__gte=0), name='product_nonnegative_stock'),
            models.CheckConstraint(condition=Q(reorder_level__gte=0), name='product_nonnegative_reorder'),
            models.CheckConstraint(condition=Q(is_active__in=[0, 1]), name='product_active_valid'),
        ]


class Order(models.Model):
    order_id = models.CharField(max_length=40, primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='orders')
    channel = models.CharField(max_length=20)
    status = models.CharField(max_length=10)
    confirmed_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name='orders')
    note = models.TextField(default='', blank=True)

    class Meta:
        db_table = 'orders'
        indexes = [models.Index(fields=['status', 'confirmed_at'], name='idx_orders_status')]
        constraints = [
            models.CheckConstraint(condition=Q(channel__in=['website', 'sales_manager']), name='order_channel_valid'),
            models.CheckConstraint(condition=Q(status__in=['confirmed', 'packed', 'shipped', 'cancelled']), name='order_status_valid'),
        ]


class OrderItem(models.Model):
    item_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='lines')
    sku = models.ForeignKey(Product, db_column='sku', on_delete=models.PROTECT, related_name='order_lines')
    qty_reserved = models.IntegerField()
    unit_price_kzt = models.IntegerField()
    confirmed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'order_item'
        indexes = [models.Index(fields=['sku'], name='idx_item_sku')]
        constraints = [
            models.UniqueConstraint(fields=['order', 'sku'], name='order_item_unique_sku'),
            models.CheckConstraint(condition=Q(qty_reserved__gt=0), name='item_positive_quantity'),
            models.CheckConstraint(condition=Q(unit_price_kzt__gt=0), name='item_positive_price'),
        ]


class StockMovement(models.Model):
    movement_id = models.AutoField(primary_key=True)
    sku = models.ForeignKey(Product, db_column='sku', on_delete=models.PROTECT, related_name='movements')
    movement_type = models.CharField(max_length=20)
    physical_delta = models.IntegerField(default=0)
    reserved_delta = models.IntegerField(default=0)
    moved_at = models.DateTimeField(default=timezone.now)
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name='movements')
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.PROTECT, related_name='movements')
    source = models.CharField(max_length=10)
    note = models.TextField()

    class Meta:
        db_table = 'stock_movement'
        indexes = [models.Index(fields=['sku', 'moved_at'], name='idx_movement_sku_time')]
        constraints = [
            models.CheckConstraint(condition=~Q(physical_delta=0) | ~Q(reserved_delta=0), name='movement_nonzero'),
            models.CheckConstraint(condition=Q(movement_type__in=['delivery_in', 'reserve', 'release', 'sale', 'correction', 'write_off']), name='movement_type_valid'),
            models.CheckConstraint(condition=Q(source__in=['manual', 'scanner', 'system']), name='movement_source_valid'),
        ]
