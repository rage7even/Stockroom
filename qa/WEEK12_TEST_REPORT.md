# Week 12 test report

Checks ran on November 19, 2026, with Django, SQLite and the Angular production build.

| Check | Observed result |
| --- | --- |
| Django regression and Week 12 API tests | **26 passed.** Tests covered barcode lookup, CSV-created barcodes, supplier agreements, supplier availability, permissions, purchase prices, receipts and notifications. |
| Angular production build | **Passed.** The build contains the three purchasing pages, barcode scanner and notification menu. |
| Upgrade of the existing database | **Passed.** On a copy of the database, the migration preserved existing records across 18 tables, kept both append-only history triggers, and generated 121 distinct barcodes. The working database migration also passed integrity and foreign-key checks. |
| Concurrent receipt requests over HTTP | **Passed.** Two sessions each submitted 6 units against a 10-unit order. One request succeeded, the other received HTTP 409. Repeating the successful request returned HTTP 200 and left 4 pending. |
| Complete the remaining delivery over HTTP | **Passed.** Accepting the remaining 4 produced a received order with two receipts, 10 additional units on the shelf and two notifications. Marking a notification as read reduced the unread count. |
| Code 128 rendering and decoder | **Passed on synthetic input.** Four labels at three scales read in both directions, for 24 correct reads. A blank row produced no match. |

To reproduce the Django checks, run `python backend/manage.py test inventory --noinput` from the project folder using its Python environment.

## Device demo checklist

These cases require a phone and a hardware scanner. Use an HTTPS deployment and the training order **PO-1** or an equivalent demo order.

1. Open the product card for `DEM-C35W-WHT` and print the label `SR-DEM-C35W-WHT`.
2. From **Products**, open the camera on a phone and scan the printed label. Expect the matching product card.
3. From **Purchase receiving**, select the demo order. Scan once and expect **Receive now** to increase by one. Use **Scan next item** for a second count.
4. Put the cursor in the barcode field and read the same label with a keyboard-mode USB scanner. Expect the same product.
5. Enter 6 and confirm, then receive the remaining 4. Verify the purchase order, movement history and notification bell.
