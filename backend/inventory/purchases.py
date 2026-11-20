from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Case, Value, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import services
from .models import (
    Notification, Product, PurchaseLine, PurchaseOrder, PurchaseReceipt,
    PurchaseReceiptLine, Supplier, SupplierOffer,
)
from .serializers import Integer, LineInput, OrderInput
from .views import validate, warehouse


class SupplierInput(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    location = serializers.CharField(max_length=150)
    agreement = serializers.CharField(max_length=300, allow_blank=True)
    agreement_active = serializers.BooleanField()
    lead_days = Integer(min_value=0, max_value=365)


class OfferInput(serializers.Serializer):
    unit_cost = Integer(min_value=1, max_value=10000000)
    available_qty = Integer(min_value=0, max_value=1000000, allow_null=True)


class PurchaseInput(serializers.Serializer):
    supplier_id = serializers.IntegerField(min_value=1)
    lines = LineInput(many=True, allow_empty=False, max_length=50)
    validate_lines = OrderInput.validate_lines


class ReceiptInput(serializers.Serializer):
    receipt_id = serializers.UUIDField()
    lines = LineInput(many=True, allow_empty=False, max_length=50)
    validate_lines = OrderInput.validate_lines


def supplier_data(supplier):
    return {
        "id": supplier.pk, "name": supplier.name, "location": supplier.location,
        "agreement": supplier.agreement, "agreement_active": supplier.agreement_active,
        "lead_days": supplier.lead_days,
        "offers": [
            {
                "sku": offer.product_id, "product_name": offer.product.product_name,
                "unit_cost": offer.unit_cost, "available_qty": offer.available_qty,
                "updated_at": offer.updated_at,
            }
            for offer in supplier.offers.all()
        ],
    }


@api_view(["GET", "POST"])
def suppliers(request):
    warehouse(request.user)
    if request.method == "GET":
        rows = Supplier.objects.prefetch_related("offers__product").order_by("name")
        return Response([supplier_data(row) for row in rows])
    data = validate(SupplierInput, request.data).validated_data
    try:
        row = Supplier.objects.create(**data)
    except IntegrityError:
        raise services.Conflict("This supplier name already exists.")
    return Response(supplier_data(row), status=201)


@api_view(["PUT"])
def edit_supplier(request, supplier_id):
    warehouse(request.user)
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    data = validate(SupplierInput, request.data).validated_data
    try:
        Supplier.objects.filter(pk=supplier.pk).update(**data)
    except IntegrityError:
        raise services.Conflict("This supplier name already exists.")
    supplier.refresh_from_db()
    return Response(supplier_data(supplier))


@api_view(["PUT"])
def edit_offer(request, supplier_id, sku):
    warehouse(request.user)
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    product = get_object_or_404(Product, pk=sku)
    data = validate(OfferInput, request.data).validated_data
    SupplierOffer.objects.update_or_create(supplier=supplier, product=product, defaults=data)
    return Response(supplier_data(supplier))


def purchase_rows():
    return PurchaseOrder.objects.select_related("supplier").prefetch_related(
        "lines__product", "lines__receipts", "receipts__staff", "receipts__lines__purchase_line"
    )


def balance(line):
    return line.ordered_qty - sum(receipt.qty for receipt in line.receipts.all())


def receipt_data(receipt):
    return {
        "id": str(receipt.pk), "created_at": receipt.created_at,
        "staff_name": receipt.staff.full_name,
        "lines": [
            {"sku": row.purchase_line.product_id, "qty": row.qty}
            for row in receipt.lines.all()
        ],
    }


def purchase_data(order):
    lines = []
    for row in order.lines.all():
        remaining = balance(row)
        lines.append({
            "sku": row.product_id, "product_name": row.product.product_name,
            "ordered": row.ordered_qty, "received": row.ordered_qty - remaining,
            "remaining": remaining, "unit_cost": row.unit_cost,
        })
    return {
        "id": order.pk, "supplier_id": order.supplier_id, "supplier_name": order.supplier.name,
        "created_at": order.created_at, "expected_on": order.expected_on, "status": order.status,
        "lines": lines, "receipts": [receipt_data(receipt) for receipt in order.receipts.all()],
    }


@transaction.atomic
def place_purchase(data, staff):
    supplier = get_object_or_404(Supplier, pk=data["supplier_id"])
    if not supplier.agreement_active:
        raise services.Conflict("An active supplier agreement is required.")
    requested = {row["sku"]: row["qty"] for row in data["lines"]}
    offers = {row.product_id: row for row in supplier.offers.filter(product_id__in=requested)}
    for sku, qty in requested.items():
        if sku not in offers:
            raise ValidationError(f"{sku} is not in this supplier's catalogue.")
        stock = offers[sku].available_qty
        if stock is not None and qty > stock:
            raise services.Conflict(f"{sku}: the supplier reports {stock} available.")
    order = PurchaseOrder.objects.create(
        supplier=supplier, staff=staff,
        expected_on=timezone.localdate() + timedelta(days=supplier.lead_days),
    )
    PurchaseLine.objects.bulk_create([
        PurchaseLine(order=order, product_id=sku, ordered_qty=qty, unit_cost=offers[sku].unit_cost)
        for sku, qty in requested.items()
    ])
    return order


@api_view(["GET", "POST"])
def purchases(request):
    warehouse(request.user)
    if request.method == "GET":
        return Response([purchase_data(row) for row in purchase_rows().order_by("-pk")])
    data = validate(PurchaseInput, request.data).validated_data
    return Response(purchase_data(place_purchase(data, request.user)), status=201)


@api_view(["GET"])
def purchase_detail(request, order_id):
    warehouse(request.user)
    return Response(purchase_data(get_object_or_404(purchase_rows(), pk=order_id)))


@api_view(["POST"])
@transaction.atomic
def mark_in_transit(request, order_id):
    warehouse(request.user)
    order = get_object_or_404(PurchaseOrder, pk=order_id)
    if order.status == PurchaseOrder.Status.IN_TRANSIT:
        return Response({"status": order.status})
    if order.status != PurchaseOrder.Status.ORDERED:
        raise services.Conflict("Only an ordered purchase can be marked in transit.")
    order.status = PurchaseOrder.Status.IN_TRANSIT
    order.save(update_fields=["status"])
    return Response({"status": order.status})


@api_view(["POST"])
@transaction.atomic
def receive_purchase(request, order_id):
    warehouse(request.user)
    data = validate(ReceiptInput, request.data).validated_data
    requested = {row["sku"]: row["qty"] for row in data["lines"]}
    existing = PurchaseReceipt.objects.filter(pk=data["receipt_id"]).first()
    if existing:
        result = receipt_data(existing)
        previous = {row["sku"]: row["qty"] for row in result["lines"]}
        if existing.order_id != order_id or existing.staff_id != request.user.pk or previous != requested:
            raise services.Conflict("This receipt identifier already belongs to another submission.")
        return Response(result)

    order = get_object_or_404(PurchaseOrder, pk=order_id)
    if order.status == PurchaseOrder.Status.RECEIVED:
        raise services.Conflict("This order has already been received.")
    lines = {
        row.product_id: row
        for row in order.lines.select_related("product").prefetch_related("receipts")
    }
    if requested.keys() - lines.keys():
        raise ValidationError("The receipt contains a product outside this order.")
    remaining = {sku: balance(row) for sku, row in lines.items()}
    for sku, qty in requested.items():
        if qty > remaining[sku]:
            raise services.Conflict(f"{sku}: only {remaining[sku]} still expected.")

    receipt = PurchaseReceipt.objects.create(pk=data["receipt_id"], order=order, staff=request.user)
    for sku, qty in requested.items():
        line = lines[sku]
        PurchaseReceiptLine.objects.create(receipt=receipt, purchase_line=line, qty=qty)
        line.product.qty_in_stock += qty
        line.product.save(update_fields=["qty_in_stock"])
        services.record(
            line.product, request.user, "purchase_receipt", qty, 0,
            f"Supplier purchase #{order.pk} · Receipt {receipt.pk}",
        )
        remaining[sku] -= qty
    order.status = PurchaseOrder.Status.PARTIAL if any(remaining.values()) else PurchaseOrder.Status.RECEIVED
    order.save(update_fields=["status"])
    services.notify_warehouse(
        f"Received {sum(requested.values())} units for purchase #{order.pk} from {order.supplier.name}.",
        purchase_order=order,
    )
    return Response(receipt_data(receipt), status=201)


@api_view(["GET"])
def notifications(request):
    rows = request.user.notifications.order_by(
        Case(When(read_at__isnull=True, then=Value(0)), default=Value(1)),
        "-created_at", "-pk",
    )
    return Response({
        "unread": rows.filter(read_at__isnull=True).count(),
        "items": [
            {
                "id": row.pk, "message": row.message, "created_at": row.created_at,
                "read": row.read_at is not None, "sku": row.product_id,
                "purchase_id": row.purchase_order_id,
            }
            for row in rows[:50]
        ],
    })


@api_view(["POST"])
def read_notification(request, notification_id):
    rows = Notification.objects.filter(recipient=request.user)
    row = get_object_or_404(rows, pk=notification_id)
    rows.filter(pk=row.pk, read_at__isnull=True).update(read_at=timezone.now())
    return Response({"ok": True})
