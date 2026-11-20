# Stockroom user guide

Stockroom helps warehouse staff see what is on the shelf, take customer orders, and record deliveries. This guide starts once your team has opened the Stockroom sign-in page.

## Sign in and find your way around

1. Enter your staff email and password, then select **Sign in**. For a class demo, use the [demo accounts](../README.md#run-it-on-windows).
2. Open **Overview** to see low-stock products, recent orders, and older reservations.
3. Use **Refresh data** after a colleague changes an order or a stock count. Use **Sign out** when you finish on a shared computer.

Sales staff can browse products, add customers, and create orders. Managers can also edit products, pack, ship or cancel orders, receive or correct stock, and view stock history. Ask your administrator to create an account for you. Admins have the same warehouse controls as managers and can manage staff accounts.

## Check stock before promising a quantity

Open **Products** and search by name, SKU, or brand. Select a product to open its details.

| Field | What it tells you |
| --- | --- |
| **On shelf** | How many units are physically in the warehouse. |
| **Reserved** | How many of those units are set aside for confirmed or packed orders. |
| **Available** | How many units you can still promise to another customer. This is the on-shelf count minus the reserved count. |

For example, 10 units on the shelf with 6 reserved leaves 4 available. If a customer asks for 5, confirm a smaller quantity with them first.

## Take and fulfil an order

1. Check **Customers** for the shop. If it is new, use **Add customer** and enter the shop name, contact name, and phone.
2. Open **Orders** and select **Create order**. Pick the customer and the sales channel, then add the product and quantity for each line. Add any instructions in the note.
3. Select **Confirm & reserve stock**. If one line exceeds the available quantity, review that line and submit again. The entire order has to fit the available stock.
4. When the order is ready, a manager opens it by its order number. Use **Mark as packed** when the items are packed and **Ship order** when they leave the warehouse. Choose **Confirm action** to apply the change. Shipping reduces the physical count and clears the reservation.
5. If the customer cancels before shipment, a manager selects **Cancel order** and **Confirm action**. The reserved items become available again.

Use the order number or customer name to search **Orders**. If the page flags a reservation older than 14 days, check with the customer and decide whether to ship or cancel.

### Start an order from the catalogue

Select **Add to cart** on a product, then open **Cart** to adjust quantities and enter the customer, channel and note. Use **Save cart** to continue later from the same account. **Confirm and reserve** checks the latest stock and prices, reserves the order and opens it in **Orders**. If there is a shortage, adjust the quantities in the saved cart.

## Import and export the catalogue

As a manager, open **Import / export**. Download **Export CSV** for a template, edit product details and choose the file under **Import products**. Select **Validate CSV** to see how many products will be added or updated and which rows need corrections. Select **Apply import** to save the validated file. New SKUs start at zero stock. Use **Receiving** to add units.

## Review store returns

A store account submits its return from a shipped order. Managers can open **Returns & defects** to find pending requests, search by order, shop or SKU, and open the original order to review the request. **Receive return** adds sellable units back to stock and records defective units separately. The queue also shows received and rejected requests.

## Receive or correct stock

For a supplier order, use **Purchase receiving**. To record a standalone delivery or correction, use **Receiving**.

1. As a manager, open **Receiving**. Choose **Delivery in** for a delivery or **Stock correction** when the shelf count differs from the recorded count.
2. Enter the product SKU. If you have a scanner that types into the active field, place the cursor in **Product SKU** before scanning. Choose the entry method you used.
3. Enter the quantity received or the signed correction. For example, enter `-2` if the actual shelf count is two units lower. Include the delivery reference or correction reason.
4. Select **Review stock change**. Check the projected count and select **Confirm stock change**.
5. Open **History** and search by SKU or reference to see when the change happened and who recorded it.

## Buy from a supplier

1. Sign in as a Manager or Admin. From **Suppliers**, add a supplier, enter the lead time and agreement terms, and mark the agreement active. Add offers linked to existing Stockroom products. Stock and its update date describe the supplier's latest reported availability.
2. Select **Create purchase order**, enter the quantities and place the order. In **Purchase orders**, open the order to see the expected delivery and mark it in transit after confirmation from the supplier.
3. Open **Receive delivery**. Take a label from **Products → product details → Print label** or read the printed barcode value. Use **Scan barcode** to open a camera, or enter the barcode in the same dialog with a keyboard or a USB scanner. For camera use on a phone, open Stockroom over HTTPS.
4. Confirm the counted quantities. If six of ten units arrive, enter six and confirm. The order remains open for the remaining four. Previous receipts are visible below the order.
5. Open **History** and filter by **Purchase receipt** to find the stock movement. The notification bell links back to the purchase. The bell can also report when available stock crosses below its reorder threshold.

## If something goes wrong

| What you see | What to do |
| --- | --- |
| An order is refused because stock is short | Refresh the product list, check **Available**, and agree on a quantity that fits. |
| A stock correction would remove reserved units | Ask a manager to reconcile the active orders before correcting the shelf count. |
| An order gives an error after confirmation | Refresh **Orders** and search for the customer before submitting it again. |
| The app will not open or records are missing | Tell the person who runs Stockroom what happened and share the order number or SKU if you have it. If data needs to be restored, sign in again afterwards and check any orders entered since the backup was taken. |
