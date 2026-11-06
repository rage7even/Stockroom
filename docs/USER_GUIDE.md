# Stockroom user guide

Stockroom helps warehouse staff see what is on the shelf, take customer orders, and record deliveries. This guide starts once your team has opened the Stockroom sign-in page.

## Sign in and find your way around

1. Enter your staff email and password, then select **Sign in**. For a class demo, use the [demo accounts](../README.md#run-it-on-windows).
2. Open **Overview** to see low-stock products, recent orders, and older reservations.
3. Use **Refresh data** after a colleague changes an order or a stock count. Use **Sign out** when you finish on a shared computer.

Sales staff can browse products, add customers, and create orders. Managers can also edit products, pack, ship or cancel orders, receive or correct stock, and view stock history. Admins have the same warehouse controls as managers and can manage staff accounts.

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

## Receive or correct stock

1. As a manager, open **Receiving**. Choose **Delivery in** for a delivery or **Stock correction** when the shelf count differs from the recorded count.
2. Enter the product SKU. If you have a scanner that types into the active field, place the cursor in **Product SKU** before scanning. Choose the entry method you used.
3. Enter the quantity received or the signed correction. For example, enter `-2` if the actual shelf count is two units lower. Include the delivery reference or correction reason.
4. Select **Review stock change**. Check the projected count and select **Confirm stock change**.
5. Open **History** and search by SKU or reference to see when the change happened and who recorded it.

## If something goes wrong

| What you see | What to do |
| --- | --- |
| An order is refused because stock is short | Refresh the product list, check **Available**, and agree on a quantity that fits. |
| A stock correction would remove reserved units | Ask a manager to reconcile the active orders before correcting the shelf count. |
| An order gives an error after confirmation | Refresh **Orders** and search for the customer before submitting it again. |
| The app will not open or records are missing | Tell the person who runs Stockroom what happened and share the order number or SKU if you have it. If data needs to be restored, sign in again afterwards and check any orders entered since the backup was taken. |
