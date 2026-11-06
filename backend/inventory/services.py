from uuid import uuid4
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound
from .models import Product, Order, OrderItem, StockMovement


class Conflict(APIException):
    status_code = 409


def inventory():
    rows = Product.objects.annotate(
        reserved=Sum(
            "order_items__qty_reserved",
            filter=Q(order_items__order__status__in=["confirmed", "packed"]),
        )
    ).order_by("product_name")
    return [
        dict(
            sku=p.sku,
            product_name=p.product_name,
            brand=p.brand,
            category=p.category,
            price_kzt=p.price_kzt,
            qty_in_stock=p.qty_in_stock,
            reorder_level=p.reorder_level,
            location=p.location,
            reserved=p.reserved or 0,
            available=p.qty_in_stock - (p.reserved or 0),
        )
        for p in rows
    ]


def available(product):
    reserved = (
        OrderItem.objects.filter(
            product=product, order__status__in=["confirmed", "packed"]
        ).aggregate(total=Sum("qty_reserved"))["total"]
        or 0
    )
    return product.qty_in_stock - reserved


def record(product, staff, kind, physical, reserved, note, order=None, source="system"):
    StockMovement.objects.create(
        product=product,
        staff=staff,
        movement_type=kind,
        physical_delta=physical,
        reserved_delta=reserved,
        note=note,
        order=order,
        source=source,
    )


@transaction.atomic
def confirm(data, staff):
    checked = []
    for line in data["lines"]:
        product = Product.objects.filter(pk=line["sku"]).first()
        if product is None:
            raise NotFound("Unknown product: " + line["sku"])
        free = available(product)
        if line["qty"] > free:
            raise Conflict(
                f"Only {free} units of {product.sku} are available. Nothing was reserved."
            )
        checked.append((product, line["qty"]))
    order = Order.objects.create(
        order_id=f"ORD-{timezone.now().year}-{uuid4().hex[:12].upper()}",
        customer=data["customer"],
        staff=staff,
        channel=data["channel"],
        note=data["note"],
    )
    for product, qty in checked:
        OrderItem.objects.create(
            order=order,
            product=product,
            qty_reserved=qty,
            unit_price_kzt=product.price_kzt,
        )
        record(product, staff, "reserve", 0, qty, "Order confirmed", order)
    return order


@transaction.atomic
def transition(oid, action, staff):
    order = Order.objects.filter(pk=oid).first()
    if order is None:
        raise NotFound("Order not found")
    if action not in ["pack", "ship", "cancel"]:
        raise NotFound("Unknown action")
    if (
        order.status not in ["confirmed", "packed"]
        or action == "pack"
        and order.status != "confirmed"
    ):
        raise Conflict("This order has already moved past this step.")
    for line in order.lines.select_related("product"):
        if action == "pack":
            continue
        qty = line.qty_reserved
        if action == "ship":
            line.product.qty_in_stock -= qty
            line.product.save(update_fields=["qty_in_stock"])
        record(
            line.product,
            staff,
            "sale" if action == "ship" else "release",
            -qty if action == "ship" else 0,
            -qty,
            "Order " + action,
            order,
        )
    order.status = {"pack": "packed", "ship": "shipped", "cancel": "cancelled"}[action]
    order.save(update_fields=["status"])


@transaction.atomic
def change_stock(action, data, staff):
    if action not in ["receive", "adjust"]:
        raise NotFound("Unknown stock action")
    qty = data["quantity"]
    if qty == 0 or action == "receive" and qty < 1:
        raise Conflict("Enter a positive receipt or a non-zero correction.")
    product = Product.objects.filter(pk=data["sku"]).first()
    if product is None:
        raise NotFound("SKU not found. Check the code.")
    if available(product) + qty < 0:
        raise Conflict("This correction would remove reserved stock.")
    product.qty_in_stock += qty
    product.save(update_fields=["qty_in_stock"])
    record(
        product,
        staff,
        "delivery_in" if action == "receive" else "correction",
        qty,
        0,
        data["note"],
        source=data["source"],
    )
