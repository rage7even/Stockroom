-- Products below the threshold, including products with no reservations.
SELECT p.sku,p.product_name,p.qty_in_stock,COALESCE(r.reserved,0) AS reserved,
       p.qty_in_stock-COALESCE(r.reserved,0) AS available
FROM product p
LEFT JOIN (
 SELECT i.sku,SUM(i.qty_reserved) AS reserved
 FROM order_item i JOIN orders o ON o.order_id=i.order_id
 WHERE o.status IN ('confirmed','packed') GROUP BY i.sku
) r ON r.sku=p.sku
WHERE p.qty_in_stock-COALESCE(r.reserved,0)<p.reorder_level
ORDER BY available;

-- Old reservations for the manager to review, not automatically cancel.
SELECT o.order_id,c.shop_name,o.confirmed_at,o.status
FROM orders o JOIN customer c ON c.id=o.customer_id
WHERE o.status IN ('confirmed','packed')
AND julianday(o.confirmed_at)<julianday('now','-14 days');

-- Explain a stock change using the product and staff foreign keys.
SELECT m.moved_at,p.product_name,m.movement_type,m.physical_delta,
       m.reserved_delta,s.full_name,m.source,m.note
FROM stock_movement m JOIN product p ON p.sku=m.sku
JOIN staff s ON s.id=m.staff_id ORDER BY m.moved_at DESC;
