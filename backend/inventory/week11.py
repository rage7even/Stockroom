import csv
import io

from django.db import transaction
from django.db.models import Exists, OuterRef, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.urls import reverse
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from . import services
from .models import Customer, Draft, Issue, IssueAttachment, Order, Product, StockReturn
from .serializers import Integer, OrderInput, ProductInput
from .views import validate, warehouse


class DraftLine(serializers.Serializer):
    sku = serializers.CharField(allow_blank=True, max_length=24)
    qty = Integer(allow_null=True, min_value=1, max_value=100000)


class DraftInput(serializers.Serializer):
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), allow_null=True
    )
    channel = serializers.ChoiceField(choices=["website", "sales_manager"])
    note = serializers.CharField(allow_blank=True, max_length=500)
    lines = DraftLine(many=True, max_length=50)


def draft_data(request, serializer=DraftInput):
    data = validate(serializer, request.data).validated_data
    customer = data["customer_id"]
    if customer and request.user.store_id and customer.pk != request.user.store_id:
        raise PermissionDenied("You cannot place an order for this customer.")
    data["customer_id"] = customer.pk if customer else None
    return data


@api_view(["GET", "PUT", "DELETE"])
@transaction.atomic
def drafts(request, draft_id=None):
    if request.user.role == "tech_support":
        raise PermissionDenied("Drafts are unavailable to Tech Support.")
    if (request.method == "GET") != (draft_id is None):
        return Response(status=405)
    owned = Draft.objects.filter(staff=request.user, is_cart=False)
    if request.method == "GET":
        return Response([
            {"id": str(draft.pk), **draft.data}
            for draft in owned.filter(order__isnull=True).order_by("-updated_at")
        ])
    if request.method == "DELETE":
        owned.filter(pk=draft_id, order__isnull=True).delete()
        return Response(status=204)
    data = draft_data(request)
    draft, _ = Draft.objects.get_or_create(
        pk=draft_id, defaults={"staff": request.user, "data": data}
    )
    if draft.staff_id != request.user.pk or draft.is_cart:
        raise services.NotFound("Draft not found.")
    if draft.order_id:
        raise services.Conflict("This draft was already confirmed.")
    draft.data = data
    draft.save(update_fields=["data", "updated_at"])
    return Response({"id": str(draft.pk)})


@api_view(["POST"])
@transaction.atomic
def confirm_draft(request, draft_id):
    draft = get_object_or_404(Draft, pk=draft_id, staff=request.user, is_cart=False)
    return confirm_saved_order(draft, request.data, request.user)


def confirm_saved_order(draft, data, staff):
    if draft.order_id:
        return Response({"order_id": draft.order_id})
    draft.order = services.confirm(
        validate(OrderInput, data).validated_data, staff
    )
    draft.save(update_fields=["order"])
    return Response({"order_id": draft.order_id}, status=201)


class ReturnInput(serializers.Serializer):
    sku = serializers.CharField(max_length=24)
    good = Integer(min_value=0, max_value=100000)
    defective = Integer(min_value=0, max_value=100000)
    reason = serializers.CharField(max_length=100)
    comment = serializers.CharField(allow_blank=True, max_length=300)
    request_id = serializers.UUIDField()


def return_data(item):
    return {
        "id": item.pk, "sku": item.line.product_id, "good": item.good,
        "defective": item.defective, "reason": item.reason, "comment": item.comment,
        "staff": item.staff.full_name, "created_at": item.created_at,
        "status": item.status,
    }


@api_view(["GET"])
def return_queue(request):
    warehouse(request.user)
    records = StockReturn.objects.select_related(
        "staff", "line__product", "line__order__customer"
    ).order_by("-created_at", "-pk")
    return Response([
        {
            **return_data(item),
            "order_id": item.line.order_id,
            "shop_name": item.line.order.customer.shop_name,
            "product_name": item.line.product.product_name,
        }
        for item in records
    ])


@api_view(["GET", "POST"])
@transaction.atomic
def returns(request, order_id):
    shop_id = request.user.store_id
    orders = Order.objects.all()
    if shop_id:
        orders = orders.filter(customer_id=shop_id)
    elif request.method == "GET":
        warehouse(request.user)
    if request.method == "POST" and not shop_id:
        raise PermissionDenied("Only a Sales account linked to a store may submit a return.")
    order = get_object_or_404(orders, pk=order_id)
    records = StockReturn.objects.filter(line__order=order).select_related("staff", "line")
    if request.method == "GET":
        return Response([return_data(item) for item in records.order_by("pk")])
    data = validate(ReturnInput, request.data).validated_data
    line = get_object_or_404(order.lines.select_related("product"), product_id=data["sku"])
    existing = StockReturn.objects.filter(request_id=data["request_id"]).first()
    if existing:
        if existing.line_id != line.pk or existing.staff_id != request.user.pk or any(
            getattr(existing, field) != data[field]
            for field in ("good", "defective", "reason", "comment")
        ):
            raise services.Conflict("This return request was already used.")
        return Response(return_data(existing))
    quantity = data["good"] + data["defective"]
    if order.status != "shipped" or quantity == 0:
        raise ValidationError("Select a shipped item and enter a positive return quantity.")
    totals = records.filter(line=line).exclude(status="rejected").aggregate(
        good=Sum("good"), defective=Sum("defective")
    )
    if quantity + (totals["good"] or 0) + (totals["defective"] or 0) > line.qty_reserved:
        raise services.Conflict("Return quantity exceeds the remaining shipped quantity.")
    item = StockReturn.objects.create(
        line=line, staff=request.user, **{key: value for key, value in data.items() if key != "sku"}
    )
    return Response(return_data(item), status=201)


@api_view(["POST"])
@transaction.atomic
def review_return(request, order_id, return_id):
    warehouse(request.user)
    item = get_object_or_404(
        StockReturn.objects.select_related("line__product", "line__order", "staff"),
        pk=return_id, line__order_id=order_id,
    )
    decision = request.data.get("status")
    if decision not in ("received", "rejected"):
        raise ValidationError("Choose Receive or Reject.")
    if item.status == decision:
        return Response(return_data(item))
    if item.status != "pending":
        raise services.Conflict("This request was already reviewed.")
    if decision == "received" and item.good:
        product = item.line.product
        product.qty_in_stock += item.good
        product.save(update_fields=["qty_in_stock"])
        services.record(
            product, request.user, "store_return", item.good, 0, item.reason, item.line.order
        )
    item.status = decision
    item.reviewed_by = request.user
    item.reviewed_at = timezone.now()
    item.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    return Response(return_data(item))


class IssueInput(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    description = serializers.CharField(max_length=2000)
    attachment = serializers.FileField(required=False)

    def validate_attachment(self, upload):
        from PIL import Image, ImageOps, UnidentifiedImageError

        if upload.size > 5 * 1024 * 1024:
            raise ValidationError("Choose an image up to 5 MB.")
        try:
            with Image.open(upload, formats=["JPEG", "PNG", "WEBP"]) as source:
                if source.width * source.height > 16000000:
                    raise ValidationError("Choose an image up to 16 megapixels.")
                image = ImageOps.exif_transpose(source)
                image.thumbnail((2560, 2560))
                output = io.BytesIO()
                if source.format == "PNG":
                    image.convert("RGBA").save(output, "PNG")
                    return output.getvalue(), "image/png"
                image.convert("RGB").save(output, "JPEG", quality=90)
                return output.getvalue(), "image/jpeg"
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError):
            raise ValidationError("Choose a valid JPEG, PNG or WebP image.")


def can_manage_issues(user):
    return user.role == "tech_support" or user.has_perm("inventory.change_issue")


def issue_data(issue, has_attachment):
    return {
        "id": issue.pk, "title": issue.title, "description": issue.description,
        "status": issue.status, "author": issue.staff.full_name,
        "created_at": issue.created_at,
        "attachment_url": reverse("issue-attachment", args=[issue.pk]) if has_attachment else None,
    }


@api_view(["GET", "POST", "PATCH"])
def issues(request, issue_id=None):
    if (request.method == "PATCH") != (issue_id is not None):
        return Response(status=405)
    can_manage = can_manage_issues(request.user)
    if request.method == "GET":
        rows = Issue.objects.select_related("staff").annotate(
            has_attachment=Exists(IssueAttachment.objects.filter(issue_id=OuterRef("pk")))
        ).order_by("-pk")
        if not can_manage:
            rows = rows.filter(staff=request.user)
        return Response({
            "can_manage": can_manage,
            "items": [issue_data(row, row.has_attachment) for row in rows],
        })
    if request.method == "POST":
        data = validate(IssueInput, request.data).validated_data
        attachment = data.pop("attachment", None)
        with transaction.atomic():
            issue = Issue.objects.create(staff=request.user, **data)
            if attachment:
                content, content_type = attachment
                IssueAttachment.objects.create(issue=issue, content=content, content_type=content_type)
        return Response(issue_data(issue, attachment is not None), status=201)
    if not can_manage:
        raise PermissionDenied("Issue management permission required.")
    issue = get_object_or_404(Issue, pk=issue_id)
    status = request.data.get("status")
    if status not in ("open", "in_progress", "resolved"):
        raise ValidationError("Choose a valid status.")
    issue.status = status
    issue.save(update_fields=["status"])
    return Response(issue_data(issue, IssueAttachment.objects.filter(issue=issue).exists()))


@api_view(["GET"])
def issue_attachment(request, issue_id):
    attachments = IssueAttachment.objects.filter(issue_id=issue_id)
    if not can_manage_issues(request.user):
        attachments = attachments.filter(issue__staff=request.user)
    attachment = get_object_or_404(attachments)
    response = HttpResponse(attachment.content, content_type=attachment.content_type)
    response["Cache-Control"] = "private, no-store"
    return response


CSV_FIELDS = tuple(ProductInput.Meta.fields)


def spreadsheet_formula(value):
    return value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@"))


def csv_cell(value):
    if isinstance(value, str) and (value.startswith("'") or spreadsheet_formula(value)):
        return "'" + value
    return value


def read_csv_cell(value):
    if value.startswith("'") and (value[1:].startswith("'") or spreadsheet_formula(value[1:])):
        return value[1:]
    return value


def product_csv_rows(upload, existing, updating):
    reader = csv.DictReader(io.StringIO(upload.read().decode("utf-8-sig")), strict=True)
    if reader.fieldnames != list(CSV_FIELDS):
        raise ValidationError("CSV header must be: " + ",".join(CSV_FIELDS))
    records, errors = {}, []
    seen = set()
    for index, row in enumerate(reader, 1):
        line = reader.line_num
        if updating and index > 1000:
            raise ValidationError("Use a CSV file with at most 1000 product rows.")
        if None in row or any(value is None for value in row.values()):
            errors.append({"row": line, "message": "Incorrect number of columns."})
            continue
        try:
            for field in ("price_kzt", "reorder_level"):
                row[field] = int(row[field])
        except ValueError:
            errors.append({"row": line, "message": f"{field} must be a whole number."})
            continue
        for field in ("product_name", "brand", "location"):
            row[field] = read_csv_cell(row[field])
        form = ProductInput(data=row)
        if not form.is_valid():
            message = " ".join(f"{field}: {values[0]}" for field, values in form.errors.items())
            errors.append({"row": line, "message": message})
            continue
        data = dict(form.validated_data)
        sku = data.pop("sku")
        if sku in seen or (not updating and sku in existing):
            errors.append({"row": line, "message": f"Duplicate SKU {sku}."})
            continue
        seen.add(sku)
        records[sku] = data
    if not records and not errors:
        raise ValidationError("The CSV has no product rows.")
    return records, errors


@api_view(["GET", "POST"])
@transaction.atomic
def catalog_csv(request):
    warehouse(request.user)
    if request.method == "GET":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="stockroom-products.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(CSV_FIELDS)
        for row in Product.objects.order_by("sku").values_list(*CSV_FIELDS):
            writer.writerow([csv_cell(cell) for cell in row])
        return response

    operation = request.data.get("operation")
    if operation not in (None, "preview", "apply"):
        raise ValidationError("Choose Preview or Apply.")
    upload = request.FILES.get("file")
    if upload is None or upload.size > 1024 * 1024:
        raise ValidationError("Select a UTF-8 CSV file up to 1 MB.")
    existing = Product.objects.in_bulk()
    try:
        records, errors = product_csv_rows(upload, existing, updating=operation is not None)
    except (UnicodeDecodeError, csv.Error):
        raise ValidationError("The file must be a valid UTF-8 CSV.")
    if errors:
        if operation is None:
            first = errors[0]
            raise ValidationError(f"Row {first['row']}: {first['message']}")
        return Response({"errors": errors, "applied": False}, status=400)

    new = [Product(sku=sku, **fields) for sku, fields in records.items() if sku not in existing]
    updates = {
        sku: fields for sku, fields in records.items()
        if sku in existing and any(getattr(existing[sku], name) != value for name, value in fields.items())
    }
    if operation != "preview":
        Product.objects.bulk_create(new)
        for sku, fields in updates.items():
            Product.objects.filter(pk=sku).update(**fields)
    if operation is None:
        return Response({"imported": len(new)}, status=201)
    return Response({
        "created": len(new), "updated": len(updates),
        "unchanged": len(records) - len(new) - len(updates),
        "applied": operation == "apply",
        "errors": [],
    })
