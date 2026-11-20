from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .models import Draft, Product
from .serializers import LineInput, OrderInput
from .services import Conflict, NotFound
from .views import validate
from .week11 import DraftInput, confirm_saved_order, draft_data


class CartInput(DraftInput):
    version = serializers.CharField(max_length=40)
    lines = LineInput(many=True, max_length=50)
    validate_lines = OrderInput.validate_lines


class AddProductInput(serializers.Serializer):
    sku = serializers.CharField(max_length=24)


def cart_for(user):
    if user.role == "tech_support":
        raise PermissionDenied("The cart is unavailable to Tech Support.")
    return Draft.objects.filter(staff=user, is_cart=True)


def empty_cart(user):
    return {"customer_id": user.store_id, "channel": "sales_manager", "note": "", "lines": []}


def version(draft):
    return draft.updated_at.isoformat()


def cart_response(draft, user):
    if draft is None:
        return Response({"id": None, "version": None, **empty_cart(user)})
    return Response({"id": str(draft.pk), "version": version(draft), **draft.data})


def check_version(draft, expected):
    if version(draft) != expected:
        raise Conflict("The cart changed in another tab. Reload the cart and try again.")


@api_view(["GET", "POST", "PUT"])
@transaction.atomic
def cart(request):
    carts = cart_for(request.user).filter(order__isnull=True)
    draft = carts.first()
    if request.method == "GET":
        return cart_response(draft, request.user)
    if request.method == "POST":
        sku = validate(AddProductInput, request.data).validated_data["sku"]
        if not Product.objects.filter(pk=sku).exists():
            raise NotFound("Product not found.")
        if draft is None:
            draft = Draft(id=uuid4(), staff=request.user, is_cart=True, data=empty_cart(request.user))
        lines = draft.data["lines"]
        for line in lines:
            if line["sku"] == sku:
                if line["qty"] == 100000:
                    raise ValidationError("A line can contain at most 100000 units.")
                line["qty"] += 1
                break
        else:
            if len(lines) == 50:
                raise ValidationError("The cart can contain at most 50 different products.")
            lines.append({"sku": sku, "qty": 1})
    else:
        data = draft_data(request, CartInput)
        if draft is None:
            raise Conflict("This cart is no longer active. Reload the cart and try again.")
        check_version(draft, data.pop("version"))
        skus = {line["sku"] for line in data["lines"]}
        if len(Product.objects.in_bulk(skus)) != len(skus):
            raise ValidationError("Remove unavailable products before saving the cart.")
        draft.data = data
    previous = draft.updated_at
    draft.save()
    if previous is not None and draft.updated_at <= previous:
        draft.updated_at = previous + timedelta(microseconds=1)
        Draft.objects.filter(pk=draft.pk).update(updated_at=draft.updated_at)
    return cart_response(draft, request.user)


@api_view(["POST"])
@transaction.atomic
def checkout(request, draft_id):
    draft = get_object_or_404(cart_for(request.user), pk=draft_id)
    if not draft.order_id:
        check_version(draft, request.data.get("version"))
    return confirm_saved_order(draft, draft.data, request.user)
