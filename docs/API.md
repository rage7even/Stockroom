# Stockroom Django API

Base URL: `http://127.0.0.1:8000/api`. URL paths have no trailing slash.
Send JSON with `Content-Type: application/json`; keep the `stockroom_session` cookie.
Angular uses exactly the same paths and JSON fields as before the Django migration.

| Method | Path | Access | Body / result |
|---|---|---|---|
| GET | /health | Public | status, version |
| POST | /auth/login | Public, rate limited | login, password → account and cookie |
| POST | /auth/register | Public, rate limited | full_name, login, password → sales account and cookie; 201 |
| GET | /auth/me | Signed in | staff_id, full_name, login, role, is_active |
| POST | /auth/logout | Public | Revoke current cookie session |
| GET | /products | Signed in | Product array with qty_in_stock, reserved, available |
| POST | /products | Manager/admin | sku, product_name, brand, category, price_kzt, reorder_level, location; 201 |
| PUT | /products/{sku} | Manager/admin | Same fields; SKU is permanent |
| GET | /customers | Signed in | Customer array |
| POST | /customers | Signed in | shop_name, contact_name, phone → customer_id; 201 |
| GET | /orders | Signed in | Orders with lines, historical price, total_kzt, stale |
| POST | /orders | Signed in | customer_id, channel, note (optional), lines: [{sku, qty}] → order_id; 201 |
| POST | /orders/{id}/pack | Manager/admin | confirmed → packed |
| POST | /orders/{id}/ship | Manager/admin | confirmed/packed → shipped |
| POST | /orders/{id}/cancel | Manager/admin | confirmed/packed → cancelled |
| POST | /stock/receive | Manager/admin | sku, quantity > 0, source (manual/scanner), note |
| POST | /stock/adjust | Manager/admin | sku, nonzero quantity, source, note |
| GET | /movements | Manager/admin | Append-only stock history |
| GET | /staff | Admin | Accounts without password hashes |
| PATCH | /staff/{id} | Admin | role, is_active (0/1); revokes all sessions of target |
| GET | /backups | Admin | name, size_bytes, created_at |
| POST | /backups | Admin | name of verified snapshot; 201 |
| GET | /backups/{name} | Admin | SQLite download |

Order channel is `website` or `sales_manager`. Each SKU appears once per order.
Integer fields reject fractions, booleans and numeric strings. Unknown fields are rejected.

Errors use `{"detail": "message"}` or `{"detail": [{"loc": ["body", "field"], "msg": "message"}]}`.
Codes: 401 sign-in required, 403 role/origin denied, 404 missing resource, 405 wrong method,
409 conflict, 413 oversized body, 422 invalid input, 429 authentication rate limit.

The demo login password is `Stockroom2026!`, for example `manager@stockroom.local`.
Runnable requests: [API_EXAMPLES.http](../integration/API_EXAMPLES.http).
