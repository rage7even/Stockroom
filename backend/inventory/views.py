from base64 import b64encode
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from django.conf import settings
from django.contrib.auth import authenticate, login as sign_in, logout as sign_out
from django.http import FileResponse, HttpResponseRedirect, JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.db import IntegrityError
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import Staff, Product, Customer, Order, StockMovement
from .serializers import ProductInput, CustomerInput, OrderInput, MovementInput
from . import services


def warehouse(user):
    if user.role not in ["manager", "admin"]:
        raise PermissionDenied("Manager access required.")


def validate(serializer, data, instance=None):
    form = serializer(instance=instance, data=data)
    form.is_valid(raise_exception=True)
    return form


def user_data(user):
    return {
        "staff_id": user.pk,
        "full_name": user.full_name,
        "login": user.username,
        "role": user.role,
        "shop_id": user.store_id,
        "shop_name": user.shop.shop_name if user.store_id else None,
        "phone": user.phone,
        "job_title": user.job_title,
        "avatar": user.avatar,
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    return Response({"csrfToken": get_token(request)})


class LoginInput(serializers.Serializer):
    login = serializers.EmailField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    SessionAuthentication().enforce_csrf(request)
    data = validate(LoginInput, request.data).validated_data
    user = authenticate(
        request, username=data["login"].lower(), password=data["password"]
    )
    if user is None:
        raise ValidationError("Incorrect email or password.")
    sign_in(request, user)
    return Response(user_data(user))


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def me(request):
    if request.method == "PATCH":
        class ProfileInput(serializers.Serializer):
            full_name = serializers.CharField(max_length=80)
            phone = serializers.RegexField(r"^\+?[0-9 ()-]{7,25}$", allow_blank=True, required=False)
            job_title = serializers.CharField(max_length=80, allow_blank=True, required=False)
            photo = serializers.FileField(required=False)
            remove_photo = serializers.BooleanField(required=False)

        data = validate(ProfileInput, request.data).validated_data
        photo = data.pop("photo", None)
        remove = data.pop("remove_photo", False)
        if photo is not None:
            from PIL import Image, ImageOps, UnidentifiedImageError

            if photo.size > 2 * 1024 * 1024:
                raise ValidationError("Choose a photo up to 2 MB.")
            try:
                with Image.open(photo, formats=["JPEG", "PNG", "WEBP"]) as source:
                    if source.width * source.height > 16000000:
                        raise ValidationError("Choose a photo up to 16 megapixels.")
                    image = ImageOps.exif_transpose(source)
                    image.thumbnail((256, 256))
                    output = BytesIO()
                    image.convert("RGB").save(output, "JPEG", quality=85)
            except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
                raise ValidationError("Choose a valid JPEG, PNG or WebP photo.")
            data["avatar"] = "data:image/jpeg;base64," + b64encode(output.getvalue()).decode("ascii")
        elif remove:
            data["avatar"] = ""
        for field, value in data.items():
            setattr(request.user, field, value)
        request.user.save(update_fields=list(data))
    return Response(user_data(request.user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    sign_out(request)
    return Response({"ok": True})


@api_view(["GET", "POST"])
def products(request):
    if request.user.role == "tech_support":
        raise PermissionDenied("Catalogue access is unavailable to Tech Support.")
    if request.method == "GET":
        return Response(services.inventory())
    warehouse(request.user)
    form = validate(ProductInput, request.data)
    try:
        form.save()
    except IntegrityError:
        raise services.Conflict("This SKU already exists.")
    return Response({"ok": True}, status=201)


@api_view(["GET"])
def product_barcode(request):
    if request.user.role == "tech_support":
        raise PermissionDenied("Catalogue access is unavailable to Tech Support.")
    code = request.query_params.get("code", "").strip().upper()
    matches = services.inventory(Product.objects.filter(barcode=code))
    if not matches:
        raise services.NotFound("No product matches this barcode.")
    return Response(matches[0])


@api_view(["PUT"])
def product_edit(request, sku):
    warehouse(request.user)
    if request.data.get("sku") != sku:
        raise ValidationError("The SKU cannot be changed.")
    product = Product.objects.filter(pk=sku).first()
    if product is None:
        raise services.NotFound("Product not found")
    validate(ProductInput, request.data, product).save()
    return Response({"ok": True})


@api_view(["GET", "POST"])
def customers(request):
    if request.user.role == "tech_support":
        raise PermissionDenied("Customer access is unavailable to Tech Support.")
    rows = Customer.objects.order_by("shop_name")
    if request.user.store_id:
        if request.method != "GET":
            raise PermissionDenied("Store accounts cannot add customers.")
        rows = rows.filter(pk=request.user.store_id)
    if request.method == "GET":
        return Response(
            [
                {
                    "customer_id": c.pk,
                    "shop_name": c.shop_name,
                    "contact_name": c.contact_name,
                    "phone": c.phone,
                }
                for c in rows
            ]
        )
    form = validate(CustomerInput, request.data)
    try:
        form.save()
    except IntegrityError:
        raise services.Conflict("This shop already exists.")
    return Response({"ok": True}, status=201)


@api_view(["GET", "POST"])
def orders(request):
    if request.user.role == "tech_support":
        raise PermissionDenied("Order access is unavailable to Tech Support.")
    if request.method == "POST":
        order = services.confirm(
            validate(OrderInput, request.data).validated_data, request.user
        )
        return Response({"order_id": order.pk}, status=201)
    rows = []
    orders_query = (
        Order.objects.select_related("customer", "staff")
        .prefetch_related("lines__product")
        .order_by("-confirmed_at")
    )
    if request.user.store_id:
        orders_query = orders_query.filter(customer_id=request.user.store_id)
    for o in orders_query:
        lines = [
            {
                "sku": l.product_id,
                "product_name": l.product.product_name,
                "qty_reserved": l.qty_reserved,
                "unit_price_kzt": l.unit_price_kzt,
            }
            for l in o.lines.all()
        ]
        rows.append(
            {
                "order_id": o.pk,
                "customer_id": o.customer_id,
                "shop_name": o.customer.shop_name,
                "channel": o.channel,
                "status": o.status,
                "confirmed_at": o.confirmed_at,
                "staff_name": o.staff.full_name,
                "note": o.note,
                "lines": lines,
                "total_kzt": sum(
                    l["qty_reserved"] * l["unit_price_kzt"] for l in lines
                ),
                "stale": o.status in ["confirmed", "packed"]
                and o.confirmed_at < timezone.now() - timedelta(days=14),
            }
        )
    return Response(rows)


@api_view(["POST"])
def order_action(request, oid, action):
    warehouse(request.user)
    services.transition(oid, action, request.user)
    return Response({"ok": True})


@api_view(["POST"])
def stock(request, action):
    warehouse(request.user)
    services.change_stock(
        action, validate(MovementInput, request.data).validated_data, request.user
    )
    return Response({"ok": True})


@api_view(["GET"])
def history(request):
    warehouse(request.user)
    return Response(
        [
            {
                "movement_id": m.pk,
                "sku": m.product_id,
                "product_name": m.product.product_name,
                "movement_type": m.movement_type,
                "physical_delta": m.physical_delta,
                "reserved_delta": m.reserved_delta,
                "moved_at": m.moved_at,
                "staff_name": m.staff.full_name,
                "source": m.source,
                "note": m.note,
                "order_id": m.order_id,
            }
            for m in StockMovement.objects.select_related("product", "staff").order_by(
                "-moved_at", "-pk"
            )
        ]
    )


def api_not_found(request, path):
    return JsonResponse({"detail": f"API endpoint not found: /api/{path}"}, status=404)


def frontend(request, path=""):
    root = (settings.BASE_DIR.parent / "frontend/dist/stockroom/browser").resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        return JsonResponse({"detail": "Not found"}, status=404)
    if path in {"products", "orders", "receiving", "history", "customers", "profile", "issues",
                "cart", "returns", "data", "suppliers", "purchases", "purchase-receiving"}:
        return HttpResponseRedirect("/#/" + path)
    if not path:
        target = root / "index.html"
    if not target.is_file():
        detail = "Not found" if path else "Frontend build missing. See README."
        return JsonResponse({"detail": detail}, status=404)
    return FileResponse(target.open("rb"))
