from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import services
from .models import Order, OrderScan, Product
from .views import validate, warehouse


class ScanInput(serializers.Serializer):
    request_id = serializers.UUIDField()
    barcode = serializers.CharField(max_length=27)
    source = serializers.ChoiceField(choices=["camera", "manual"])

    def validate_barcode(self, value):
        return value.upper()


def get_order(oid, lock=False):
    rows = Order.objects.select_for_update() if lock else Order.objects
    order = rows.filter(pk=oid).first()
    if order is None:
        raise services.NotFound("Order not found")
    return order


def order_progress(order):
    lines = [
        {
            "sku": line.product_id, "product_name": line.product.product_name,
            "location": line.product.location, "expected": line.qty_reserved,
            "verified": line.verified,
        }
        for line in services.verified_lines(order).select_related("product").order_by("pk")
    ]
    history = OrderScan.objects.filter(line__order=order).order_by("-created_at", "-pk")
    latest = history.filter(voided_at__isnull=True).values_list("pk", flat=True).first()
    return {
        "status": order.status,
        "complete": bool(lines) and all(row["verified"] == row["expected"] for row in lines),
        "lines": lines, "latest_active_id": latest,
        "history": [
            {
                "id": row.pk, "sku": row.line.product_id, "barcode": row.barcode,
                "staff": row.staff.full_name, "created_at": row.created_at,
                "source": row.source, "voided_at": row.voided_at,
                "voided_by": row.voided_by.full_name if row.voided_by else None,
            }
            for row in history.select_related("line", "staff", "voided_by")[:30]
        ],
    }


def require_open(order):
    if order.status not in ("confirmed", "packed"):
        raise services.Conflict("This order is closed for verification.")


@api_view(["GET", "POST"])
def verification(request, oid):
    warehouse(request.user)
    if request.method == "GET":
        return Response(order_progress(get_order(oid)))
    data = validate(ScanInput, request.data).validated_data
    with transaction.atomic():
        order = get_order(oid, lock=True)
        existing = OrderScan.objects.filter(pk=data["request_id"]).select_related("line").first()
        if existing is not None:
            if (
                existing.line.order_id != oid or existing.staff_id != request.user.pk
                or existing.barcode != data["barcode"] or existing.source != data["source"]
            ):
                raise services.Conflict("This scan request already belongs to another operation.")
            return Response(order_progress(order))
        require_open(order)
        sku = Product.objects.filter(barcode=data["barcode"]).values_list("pk", flat=True).first()
        if sku is None:
            raise services.NotFound("No product matches this barcode.")
        line = services.verified_lines(order).filter(product_id=sku).first()
        if line is None:
            raise services.Conflict("This product is not in the order.")
        if line.verified >= line.qty_reserved:
            raise services.Conflict("All required units of this product are already verified.")
        latest_at = OrderScan.objects.filter(line__order=order).order_by("-created_at").values_list(
            "created_at", flat=True
        ).first()
        created_at = timezone.now()
        # Two scans can share a clock tick. Keep the undo order deterministic under the order lock.
        if latest_at is not None and created_at <= latest_at:
            created_at = latest_at + timedelta(microseconds=1)
        OrderScan.objects.create(
            pk=data["request_id"], line=line, staff=request.user,
            barcode=data["barcode"], source=data["source"], created_at=created_at,
        )
        return Response(order_progress(order), status=201)


@api_view(["POST"])
@transaction.atomic
def undo_scan(request, oid, scan_id):
    warehouse(request.user)
    order = get_order(oid, lock=True)
    scan = OrderScan.objects.filter(pk=scan_id, line__order=order).first()
    if scan is None:
        raise services.NotFound("Scan not found.")
    if scan.voided_at is not None:
        return Response(order_progress(order))
    require_open(order)
    latest_id = OrderScan.objects.filter(line__order=order, voided_at__isnull=True).order_by(
        "-created_at", "-pk"
    ).values_list("pk", flat=True).first()
    if latest_id != scan.pk:
        raise services.Conflict("Only the most recent accepted scan can be undone.")
    scan.voided_at = timezone.now()
    scan.voided_by = request.user
    scan.save(update_fields=["voided_at", "voided_by"])
    if order.status == "packed":
        order.status = "confirmed"
        order.save(update_fields=["status"])
    return Response(order_progress(order))
