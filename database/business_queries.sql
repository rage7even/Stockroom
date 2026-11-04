-- Corrected Task 9 query: include low-stock products without reservations.
SELECT sku, product_name, qty_in_stock, reserved, available
FROM inventory
WHERE is_active = 1 AND available < reorder_level
ORDER BY available, product_name;

-- Reservations older than 14 days, including packed but unshipped orders.
SELECT o.order_id, c.shop_name, o.confirmed_at, o.status,
       SUM(i.qty_reserved) AS total_reserved_units
FROM orders o
JOIN customer c ON c.customer_id = o.customer_id
JOIN order_item i ON i.order_id = o.order_id
WHERE o.status IN ('confirmed', 'packed')
  AND julianday(o.confirmed_at) < julianday('now', '-14 days')
GROUP BY o.order_id, c.shop_name, o.confirmed_at, o.status
ORDER BY o.confirmed_at;

-- Stock truth: this query must return no rows.
SELECT sku, qty_in_stock, reserved, available
FROM inventory
WHERE available < 0 OR qty_in_stock < reserved;

-- Shipped revenue, using each order line's historical unit price.
SELECT c.customer_id, c.shop_name,
       SUM(i.qty_reserved * i.unit_price_kzt) AS shipped_value_kzt
FROM customer c
JOIN orders o ON o.customer_id = c.customer_id AND o.status = 'shipped'
JOIN order_item i ON i.order_id = o.order_id
GROUP BY c.customer_id, c.shop_name;
