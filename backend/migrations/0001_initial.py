import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


# Frozen legacy schema: adoption does not rebuild tables or modify existing rows.
SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS staff (
 staff_id INTEGER PRIMARY KEY, full_name TEXT NOT NULL CHECK(length(trim(full_name))>=2),
 login TEXT NOT NULL COLLATE NOCASE UNIQUE, password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('sales','manager','admin')), is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1))
);
CREATE TABLE IF NOT EXISTS session (
 token_hash TEXT PRIMARY KEY, staff_id INTEGER NOT NULL REFERENCES staff(staff_id), expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customer (
 customer_id INTEGER PRIMARY KEY, shop_name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(trim(shop_name))>=2),
 contact_name TEXT NOT NULL, phone TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS product (
 sku TEXT PRIMARY KEY, product_name TEXT NOT NULL, brand TEXT NOT NULL, category TEXT NOT NULL,
 price_kzt INTEGER NOT NULL CHECK(price_kzt>0), qty_in_stock INTEGER NOT NULL DEFAULT 0 CHECK(qty_in_stock>=0),
 reorder_level INTEGER NOT NULL DEFAULT 5 CHECK(reorder_level>=0), location TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1))
);
CREATE TABLE IF NOT EXISTS orders (
 order_id TEXT PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customer(customer_id),
 channel TEXT NOT NULL CHECK(channel IN ('website','sales_manager')),
 status TEXT NOT NULL CHECK(status IN ('confirmed','packed','shipped','cancelled')),
 confirmed_at TEXT NOT NULL, updated_at TEXT NOT NULL, staff_id INTEGER NOT NULL REFERENCES staff(staff_id), note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS order_item (
 item_id INTEGER PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(order_id), sku TEXT NOT NULL REFERENCES product(sku),
 qty_reserved INTEGER NOT NULL CHECK(qty_reserved>0), unit_price_kzt INTEGER NOT NULL CHECK(unit_price_kzt>0), confirmed_at TEXT NOT NULL,
 UNIQUE(order_id,sku)
);
CREATE TABLE IF NOT EXISTS stock_movement (
 movement_id INTEGER PRIMARY KEY, sku TEXT NOT NULL REFERENCES product(sku),
 movement_type TEXT NOT NULL CHECK(movement_type IN ('delivery_in','reserve','release','sale','correction','write_off')),
 physical_delta INTEGER NOT NULL DEFAULT 0, reserved_delta INTEGER NOT NULL DEFAULT 0,
 moved_at TEXT NOT NULL, staff_id INTEGER NOT NULL REFERENCES staff(staff_id), order_id TEXT REFERENCES orders(order_id),
 source TEXT NOT NULL CHECK(source IN ('manual','scanner','system')), note TEXT NOT NULL,
 CHECK(physical_delta != 0 OR reserved_delta != 0)
);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status,confirmed_at);
CREATE INDEX IF NOT EXISTS idx_item_sku ON order_item(sku);
CREATE INDEX IF NOT EXISTS idx_movement_sku_time ON stock_movement(sku,moved_at);
CREATE TRIGGER IF NOT EXISTS movement_no_update BEFORE UPDATE ON stock_movement BEGIN SELECT RAISE(ABORT,'Stock history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS movement_no_delete BEFORE DELETE ON stock_movement BEGIN SELECT RAISE(ABORT,'Stock history is append-only'); END;
CREATE VIEW IF NOT EXISTS inventory AS
 SELECT p.*, COALESCE(r.reserved,0) AS reserved, p.qty_in_stock-COALESCE(r.reserved,0) AS available
 FROM product p LEFT JOIN (
 SELECT oi.sku, SUM(oi.qty_reserved) AS reserved FROM order_item oi
 JOIN orders o ON o.order_id=oi.order_id WHERE o.status IN ('confirmed','packed') GROUP BY oi.sku
 ) r ON r.sku=p.sku;
"""


def adopt_schema(apps, schema_editor):
    import sqlite3
    statement = ''
    with schema_editor.connection.cursor() as cursor:
        for line in SCHEMA_SQL.splitlines(keepends=True):
            statement += line
            if sqlite3.complete_statement(statement):
                cursor.execute(statement)
                statement = ''
    if statement.strip():
        raise RuntimeError('Incomplete initial schema statement')


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    schema_operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('customer_id', models.AutoField(primary_key=True, serialize=False)),
                ('shop_name', models.CharField(db_collation='nocase', max_length=80, unique=True)),
                ('contact_name', models.CharField(max_length=80)),
                ('phone', models.CharField(max_length=25)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'db_table': 'customer',
            },
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('sku', models.CharField(max_length=20, primary_key=True, serialize=False)),
                ('product_name', models.CharField(max_length=100)),
                ('brand', models.CharField(max_length=40)),
                ('category', models.CharField(max_length=20)),
                ('price_kzt', models.IntegerField()),
                ('qty_in_stock', models.IntegerField(default=0)),
                ('reorder_level', models.IntegerField(default=5)),
                ('location', models.CharField(max_length=30)),
                ('is_active', models.IntegerField(default=1)),
            ],
            options={
                'db_table': 'product',
                'constraints': [models.CheckConstraint(condition=models.Q(('price_kzt__gt', 0)), name='product_positive_price'), models.CheckConstraint(condition=models.Q(('qty_in_stock__gte', 0)), name='product_nonnegative_stock'), models.CheckConstraint(condition=models.Q(('reorder_level__gte', 0)), name='product_nonnegative_reorder'), models.CheckConstraint(condition=models.Q(('is_active__in', [0, 1])), name='product_active_valid')],
            },
        ),
        migrations.CreateModel(
            name='Staff',
            fields=[
                ('staff_id', models.AutoField(primary_key=True, serialize=False)),
                ('full_name', models.CharField(max_length=80)),
                ('login', models.CharField(db_collation='nocase', max_length=150, unique=True)),
                ('password_hash', models.TextField()),
                ('role', models.CharField(choices=[('sales', 'sales'), ('manager', 'manager'), ('admin', 'admin')], max_length=10)),
                ('is_active', models.IntegerField(default=1)),
            ],
            options={
                'db_table': 'staff',
                'constraints': [models.CheckConstraint(condition=models.Q(('role__in', ['sales', 'manager', 'admin'])), name='staff_role_valid'), models.CheckConstraint(condition=models.Q(('is_active__in', [0, 1])), name='staff_active_valid')],
            },
        ),
        migrations.CreateModel(
            name='Session',
            fields=[
                ('token_hash', models.CharField(max_length=64, primary_key=True, serialize=False)),
                ('expires_at', models.DateTimeField()),
                ('staff', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sessions', to='backend.staff')),
            ],
            options={
                'db_table': 'session',
            },
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('order_id', models.CharField(max_length=40, primary_key=True, serialize=False)),
                ('channel', models.CharField(max_length=20)),
                ('status', models.CharField(max_length=10)),
                ('confirmed_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('note', models.TextField(blank=True, default='')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='orders', to='backend.customer')),
                ('staff', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='orders', to='backend.staff')),
            ],
            options={
                'db_table': 'orders',
            },
        ),
        migrations.CreateModel(
            name='StockMovement',
            fields=[
                ('movement_id', models.AutoField(primary_key=True, serialize=False)),
                ('movement_type', models.CharField(max_length=20)),
                ('physical_delta', models.IntegerField(default=0)),
                ('reserved_delta', models.IntegerField(default=0)),
                ('moved_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('source', models.CharField(max_length=10)),
                ('note', models.TextField()),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='movements', to='backend.order')),
                ('sku', models.ForeignKey(db_column='sku', on_delete=django.db.models.deletion.PROTECT, related_name='movements', to='backend.product')),
                ('staff', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='movements', to='backend.staff')),
            ],
            options={
                'db_table': 'stock_movement',
            },
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('item_id', models.AutoField(primary_key=True, serialize=False)),
                ('qty_reserved', models.IntegerField()),
                ('unit_price_kzt', models.IntegerField()),
                ('confirmed_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lines', to='backend.order')),
                ('sku', models.ForeignKey(db_column='sku', on_delete=django.db.models.deletion.PROTECT, related_name='order_lines', to='backend.product')),
            ],
            options={
                'db_table': 'order_item',
                'indexes': [models.Index(fields=['sku'], name='idx_item_sku')],
                'constraints': [models.UniqueConstraint(fields=('order', 'sku'), name='order_item_unique_sku'), models.CheckConstraint(condition=models.Q(('qty_reserved__gt', 0)), name='item_positive_quantity'), models.CheckConstraint(condition=models.Q(('unit_price_kzt__gt', 0)), name='item_positive_price')],
            },
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['status', 'confirmed_at'], name='idx_orders_status'),
        ),
        migrations.AddConstraint(
            model_name='order',
            constraint=models.CheckConstraint(condition=models.Q(('channel__in', ['website', 'sales_manager'])), name='order_channel_valid'),
        ),
        migrations.AddConstraint(
            model_name='order',
            constraint=models.CheckConstraint(condition=models.Q(('status__in', ['confirmed', 'packed', 'shipped', 'cancelled'])), name='order_status_valid'),
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(fields=['sku', 'moved_at'], name='idx_movement_sku_time'),
        ),
        migrations.AddConstraint(
            model_name='stockmovement',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('physical_delta', 0), _negated=True), models.Q(('reserved_delta', 0), _negated=True), _connector='OR'), name='movement_nonzero'),
        ),
        migrations.AddConstraint(
            model_name='stockmovement',
            constraint=models.CheckConstraint(condition=models.Q(('movement_type__in', ['delivery_in', 'reserve', 'release', 'sale', 'correction', 'write_off'])), name='movement_type_valid'),
        ),
        migrations.AddConstraint(
            model_name='stockmovement',
            constraint=models.CheckConstraint(condition=models.Q(('source__in', ['manual', 'scanner', 'system'])), name='movement_source_valid'),
        ),
    ]

    # SQLite constraints, NOCASE collations, inventory view and immutable audit
    # triggers are identical for new databases and existing pre-Django databases.
    operations = [migrations.SeparateDatabaseAndState(
        state_operations=schema_operations,
        database_operations=[migrations.RunPython(adopt_schema)],
    )]
