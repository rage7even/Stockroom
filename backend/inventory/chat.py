from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .chat_moderation import check_message
from .models import (
    DirectConversation, DirectMessage, PurchaseConversation, PurchaseMessage, PurchaseOrder, Staff,
)
from .services import Conflict
from .views import validate


class Filters(serializers.Serializer):
    supplier = serializers.CharField(required=False, max_length=100, allow_blank=True)
    purchase = serializers.CharField(required=False, max_length=20, allow_blank=True)


class StaffFilter(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=100, allow_blank=True)


class MessageInput(serializers.Serializer):
    request_id = serializers.UUIDField()
    body = serializers.CharField(max_length=1500)


class MessageCursor(serializers.Serializer):
    after = serializers.IntegerField(required=False, min_value=1, max_value=9223372036854775807)
    before = serializers.IntegerField(required=False, min_value=1, max_value=9223372036854775807)

    def validate(self, value):
        if "after" in value and "before" in value:
            raise serializers.ValidationError("Use one message cursor.")
        return value


def visible_purchases(staff):
    purchases = PurchaseOrder.objects.select_related("supplier")
    if staff.role in ("manager", "admin"):
        return purchases
    if staff.role == "supplier" and staff.supplier_id:
        return purchases.filter(supplier_id=staff.supplier_id)
    raise PermissionDenied("Purchase chat access is unavailable.")


def internal_colleagues(staff):
    if not staff.is_active or staff.role == "supplier" or staff.store_id is not None:
        raise PermissionDenied("Staff chat is only available to internal employees.")
    return Staff.objects.filter(is_active=True).exclude(
        Q(role="supplier") | Q(role="sales", shop__isnull=False) | Q(pk=staff.pk)
    )


def message_data(row):
    return {
        "id": row.pk, "body": row.body, "sender_id": row.sender_id,
        "sender": row.sender.full_name or (row.sender.username if isinstance(row, PurchaseMessage) else "Staff #" + str(row.sender_id)),
        "created_at": row.created_at,
    }


def message_page(request, rows):
    cursor = validate(MessageCursor, request.query_params).validated_data
    if "after" in cursor:
        page = list(rows.filter(pk__gt=cursor["after"]).order_by("pk")[:51])
        return Response({"messages": [message_data(row) for row in page[:50]], "more": len(page) > 50})
    if "before" in cursor:
        rows = rows.filter(pk__lt=cursor["before"])
    page = list(rows.order_by("-pk")[:51])
    return Response({"messages": [message_data(row) for row in reversed(page[:50])], "more": len(page) > 50})


def save_message(model, thread, sender, data):
    row, created = model.objects.get_or_create(
        request_id=data["request_id"],
        defaults={"conversation": thread, "sender": sender, "body": data["body"]},
    )
    if row.conversation_id != thread.pk or row.sender_id != sender.pk or row.body != data["body"]:
        raise Conflict("This message request already belongs to another operation.")
    return Response(message_data(row), status=201 if created else 200)


def checked_message(request):
    data = validate(MessageInput, request.data).validated_data
    check_message(data["body"])
    return data


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conversations(request):
    purchases = visible_purchases(request.user)
    filters = validate(Filters, request.query_params).validated_data
    if filters.get("supplier"):
        purchases = purchases.filter(supplier__name__icontains=filters["supplier"])
    if filters.get("purchase"):
        number = filters["purchase"].lower().removeprefix("po-").strip()
        if not number.isascii() or not number.isdecimal() or int(number) > 9223372036854775807:
            return Response([])
        purchases = purchases.filter(pk=int(number))
    return Response([
        {"id": row.pk, "supplier_name": row.supplier.name, "expected_on": row.expected_on}
        for row in purchases.order_by("-pk")
    ])


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def messages(request, purchase_id):
    purchase = get_object_or_404(visible_purchases(request.user), pk=purchase_id)
    if request.method == "POST":
        data = checked_message(request)
        with transaction.atomic():
            thread, _ = PurchaseConversation.objects.get_or_create(purchase=purchase)
            return save_message(PurchaseMessage, thread, request.user, data)
    rows = PurchaseMessage.objects.filter(conversation_id=purchase.pk).select_related("sender")
    return message_page(request, rows)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def colleagues(request):
    staff = internal_colleagues(request.user)
    query = validate(StaffFilter, request.query_params).validated_data.get("name")
    rows = [
        {"id": person.pk, "name": person.full_name or "Staff #" + str(person.pk), "role": person.role}
        for person in staff.only("full_name", "role")
    ]
    if query:
        term = query.casefold()
        rows = [row for row in rows if term in row["name"].casefold()]
    return Response(sorted(rows, key=lambda row: (row["name"].casefold(), row["id"])))


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def direct_messages(request, staff_id):
    peer = get_object_or_404(internal_colleagues(request.user), pk=staff_id)
    first, second = sorted((request.user.pk, peer.pk))
    participants = {"first_id": first, "second_id": second}
    if request.method == "POST":
        data = checked_message(request)
        with transaction.atomic():
            thread, _ = DirectConversation.objects.get_or_create(**participants)
            return save_message(DirectMessage, thread, request.user, data)
    thread = DirectConversation.objects.filter(**participants).first()
    rows = DirectMessage.objects.filter(conversation=thread).select_related("sender") if thread else DirectMessage.objects.none()
    return message_page(request, rows)
