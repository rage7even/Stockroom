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
