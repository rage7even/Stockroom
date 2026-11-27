from functools import partial
import secrets
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.db import IntegrityError, transaction
from django.http.request import split_domain_port
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import PasswordResetChallenge, ProfileSecurityChallenge, Staff
from .recovery import (
    CODE_LIFETIME, INVALID_CODE, MAX_ATTEMPTS, RESEND_DELAY,
    ResetConfirmThrottle, ResetRequestThrottle, queue_code, set_validated_password,
)
from .views import validate


class SecurityRequest(serializers.Serializer):
    action = serializers.ChoiceField(choices=["recovery_email", "password"])
    current_password = serializers.CharField(max_length=128, trim_whitespace=False)
    email = serializers.EmailField(max_length=254, required=False)


class SecurityConfirm(serializers.Serializer):
    action = serializers.ChoiceField(choices=["recovery_email", "password"])
    code = serializers.RegexField(r"\A[0-9]{8}\Z")
    old_code = serializers.RegexField(r"\A[0-9]{8}\Z", required=False)
    password = serializers.CharField(min_length=10, max_length=128, trim_whitespace=False, required=False)


DEMO_LOGINS = frozenset(f"{role}@stockroom.local" for role in ("admin", "manager", "sales", "shop", "support", "supplier"))
DEMO_EMAIL_REQUIRED = "Ask an administrator to link a recovery email for this shared demo account."


def may_link_email(request, staff):
    if staff.recovery_email or staff.username.lower() not in DEMO_LOGINS:
        return True
    host, _ = split_domain_port(request.get_host())
    return settings.DEBUG and host in ("localhost", "127.0.0.1", "[::1]")


def security_state(request, staff):
    masked = None
    if staff.recovery_email:
        name, _, domain = staff.recovery_email.partition("@")
        masked = name[:1] + "***@" + domain
    return {"recovery_email": masked, "can_link_email": may_link_email(request, staff)}


def get_locked_staff(request):
    staff = Staff.objects.select_for_update().get(pk=request.user.pk)
    if not staff.is_active or staff.password != request.user.password:
        raise PermissionDenied("Sign in again to manage account security.")
    return staff


def digest(staff, action, token, destination, code):
    return salted_hmac(
        "stockroom.profile-security",
        f"{staff.pk}:{action}:{token}:{staff.recovery_email or ''}:{staff.password}:{destination}:{code}",
        algorithm="sha256",
    ).hexdigest()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def status(request):
    return Response(security_state(request, request.user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([ResetRequestThrottle])
def request_code(request):
    data = validate(SecurityRequest, request.data).validated_data
    action = data["action"]
    with transaction.atomic():
        staff = get_locked_staff(request)
        if not staff.check_password(data["current_password"]):
            raise ValidationError({"current_password": ["Current password is incorrect."]})
        if action == "recovery_email":
            if not may_link_email(request, staff):
                raise PermissionDenied(DEMO_EMAIL_REQUIRED)
            destination = data.get("email", "").lower()
            if not destination:
                raise ValidationError({"email": ["This field is required."]})
            previous = staff.recovery_email
            if previous and destination == previous.lower():
                raise ValidationError("This recovery email is already linked.")
        else:
            destination = staff.recovery_email
            previous = None
            if not destination:
                raise ValidationError("Link and verify a recovery email first.")

        now = timezone.now()
        last = ProfileSecurityChallenge.objects.filter(staff=staff, action=action).first()
        if last and last.used_at is None and now < last.issued_at + RESEND_DELAY:
            raise ValidationError("Wait one minute before requesting another code.")
        token = uuid4()
        code = f"{secrets.randbelow(100_000_000):08d}"
        old_code = None
        if previous:
            old_value = (int(code) + 1 + secrets.randbelow(99_999_999)) % 100_000_000
            old_code = f"{old_value:08d}"
        ProfileSecurityChallenge.objects.update_or_create(
            staff=staff,
            action=action,
            defaults={
                "token": token, "email": destination, "issued_at": now, "used_at": None, "attempts": 0,
                "digest": digest(staff, action, token, destination, code),
                "old_digest": digest(staff, action, token, previous, old_code) if previous else "",
            },
        )
        purpose = "verify_email" if action == "recovery_email" else "change_password"
        transaction.on_commit(partial(queue_code, destination, code, purpose))
        if previous:
            transaction.on_commit(partial(queue_code, previous, old_code, "approve_email"))
    return Response({"requires_old_code": previous is not None}, status=202)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([ResetConfirmThrottle])
def confirm_code(request):
    data = validate(SecurityConfirm, request.data).validated_data
    action = data["action"]
    changed_password = False
    with transaction.atomic():
        staff = get_locked_staff(request)
        challenge = ProfileSecurityChallenge.objects.filter(staff=staff, action=action).first()
        now = timezone.now()
        if (
            challenge is None or challenge.used_at or challenge.attempts >= MAX_ATTEMPTS
            or now >= challenge.issued_at + CODE_LIFETIME
        ):
            raise ValidationError(INVALID_CODE)

        valid = constant_time_compare(
            challenge.digest, digest(staff, action, challenge.token, challenge.email, data["code"])
        )
        if challenge.old_digest:
            old_valid = constant_time_compare(
                challenge.old_digest,
                digest(staff, action, challenge.token, staff.recovery_email, data.get("old_code", "")),
            )
            valid = valid and old_valid
        if not valid:
            challenge.attempts += 1
            challenge.save(update_fields=["attempts"])
        else:
            if action == "recovery_email":
                if not may_link_email(request, staff):
                    raise PermissionDenied(DEMO_EMAIL_REQUIRED)
                try:
                    with transaction.atomic():
                        staff.recovery_email = challenge.email
                        staff.save(update_fields=["recovery_email"])
                except IntegrityError as error:
                    raise ValidationError("This recovery email is unavailable.") from error
                PasswordResetChallenge.objects.filter(staff=staff).delete()
            else:
                if "password" not in data:
                    raise ValidationError({"password": ["This field is required."]})
                set_validated_password(staff, data["password"])
                changed_password = True
            challenge.used_at = now
            challenge.save(update_fields=["used_at"])

    if not valid:
        raise ValidationError(INVALID_CODE)
    if changed_password:
        update_session_auth_hash(request, staff)
    return Response(security_state(request, staff))
