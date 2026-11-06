from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.contrib.auth import authenticate, login as sign_in, logout as sign_out
from django.http import FileResponse, JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.db import IntegrityError
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
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
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    return Response({"csrfToken": get_token(request)})


class AccountInput(serializers.Serializer):
    login = serializers.EmailField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)
    full_name = serializers.CharField(max_length=80, required=False)


@api_view(["POST"])
@permission_classes([AllowAny])
def account(request, action):
    SessionAuthentication().enforce_csrf(request)
    data = validate(AccountInput, request.data).validated_data
    if action == "register":
        if len(data["password"]) < 10 or len(data.get("full_name", "").strip()) < 2:
            raise ValidationError(
                "Enter your full name and a password of at least 10 characters."
            )
        if Staff.objects.filter(username=data["login"].lower()).exists():
            raise ValidationError("This email is already registered.")
        user = Staff.objects.create_user(
            username=data["login"].lower(),
            email=data["login"].lower(),
            password=data["password"],
            full_name=data["full_name"],
            role="sales",
        )
    elif action == "login":
        user = authenticate(
            request, username=data["login"].lower(), password=data["password"]
        )
        if user is None:
            raise ValidationError("Incorrect email or password.")
    else:
        raise ValidationError("Unknown account action.")
    sign_in(request, user)
    return Response(user_data(user), status=201 if action == "register" else 200)


@api_view(["GET"])
def me(request):
    return Response(user_data(request.user))


@api_view(["POST"])
def logout(request):
    sign_out(request)
    return Response({"ok": True})


@api_view(["GET", "POST"])
def products(request):
    if request.method == "GET":
        return Response(services.inventory())
    warehouse(request.user)
    form = validate(ProductInput, request.data)
    try:
        form.save()
    except IntegrityError:
        raise services.Conflict("This SKU already exists.")
    return Response({"ok": True}, status=201)


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
    if request.method == "GET":
        return Response(
            [
                {
                    "customer_id": c.pk,
                    "shop_name": c.shop_name,
                    "contact_name": c.contact_name,
                    "phone": c.phone,
                }
                for c in Customer.objects.order_by("shop_name")
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
    if request.method == "POST":
        order = services.confirm(
            validate(OrderInput, request.data).validated_data, request.user
        )
        return Response({"order_id": order.pk}, status=201)
    rows = []
    for o in (
        Order.objects.select_related("customer", "staff")
        .prefetch_related("lines__product")
        .order_by("-confirmed_at")
    ):
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


def frontend(request, path=""):
    root = (settings.BASE_DIR.parent / "frontend/dist/stockroom/browser").resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        return JsonResponse({"detail": "Not found"}, status=404)
    if not path:
        target = root / "index.html"
    if not target.is_file():
        return JsonResponse(
            {"detail": "Frontend build missing. See README."}, status=404
        )
    return FileResponse(target.open("rb"))
