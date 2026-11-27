import logging
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import BoundedSemaphore
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import PasswordResetChallenge, Staff
from .views import validate

CODE_LIFETIME = timedelta(minutes=10)
RESEND_DELAY = timedelta(minutes=1)
MAX_ATTEMPTS = 5
INVALID_CODE = "Invalid or expired reset code."
logger = logging.getLogger(__name__)
mail_workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="stockroom-mail")
mail_slots = BoundedSemaphore(16)


class ResetRequestThrottle(SimpleRateThrottle):
    rate = "60/hour"
    scope = "reset_request"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope, "ident": request.META.get("REMOTE_ADDR", "unknown")
        }


class ResetConfirmThrottle(ResetRequestThrottle):
    rate = "120/hour"
    scope = "reset_confirm"


class ResetRequest(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class ResetConfirm(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    code = serializers.RegexField(r"\A[0-9]{8}\Z")
    password = serializers.CharField(min_length=10, max_length=128, trim_whitespace=False)


def code_digest(token, staff, code):
    value = f"{token}:{staff.recovery_email.lower()}:{staff.password}:{code}"
    return salted_hmac("stockroom.password-reset", value, algorithm="sha256").hexdigest()


MAIL_CODES = {
    "reset": ("Stockroom password reset", "reset your password"),
    "verify_email": ("Stockroom recovery email verification", "verify this recovery email"),
    "approve_email": ("Stockroom recovery email change", "approve replacing your recovery email"),
    "change_password": ("Stockroom password change", "change your password"),
}


def set_validated_password(staff, password):
    try:
        validate_password(password, staff)
    except DjangoValidationError as error:
        raise ValidationError({"password": error.messages}) from error
    staff.set_password(password)
    staff.save(update_fields=["password"])


def deliver_code(email, code, purpose="reset"):
    subject, action = MAIL_CODES[purpose]
    try:
        sent = send_mail(
            subject,
            f"Your Stockroom code to {action} is {code}. It expires in 10 minutes. "
            "If you did not request this change, you can ignore this email.",
            settings.DEFAULT_FROM_EMAIL,
            [email],
        )
        if not sent:
            logger.warning("Account security email was not accepted by the configured mail service.")
    except Exception:
        logger.warning("Account security email could not be sent. Check the configured mail service.")
    finally:
        mail_slots.release()


def queue_code(email, code, purpose="reset"):
    if not mail_slots.acquire(blocking=False):
        logger.warning("Account security email queue is full.")
        return
    try:
        mail_workers.submit(deliver_code, email, code, purpose)
    except RuntimeError:
        mail_slots.release()
        logger.warning("Account security email worker is unavailable.")


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ResetRequestThrottle])
def request_reset(request):
    SessionAuthentication().enforce_csrf(request)
    email = validate(ResetRequest, request.data).validated_data["email"].lower()
    token = uuid4()
    code = f"{secrets.randbelow(100_000_000):08d}"
    now = timezone.now()
    with transaction.atomic():
        staff = Staff.objects.select_for_update().filter(recovery_email__iexact=email, is_active=True).first()
        if staff is not None and staff.has_usable_password():
            challenge = PasswordResetChallenge.objects.filter(staff=staff).first()
            if challenge is None or now >= challenge.issued_at + RESEND_DELAY:
                PasswordResetChallenge.objects.update_or_create(
                    staff=staff,
                    defaults={
                        "token": token, "digest": code_digest(token, staff, code), "issued_at": now, "attempts": 0, "used_at": None,
                    },
                )
                transaction.on_commit(lambda: queue_code(email, code))
    return Response({"ok": True}, status=202)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ResetConfirmThrottle])
def confirm_reset(request):
    SessionAuthentication().enforce_csrf(request)
    data = validate(ResetConfirm, request.data).validated_data
    now = timezone.now()
    with transaction.atomic():
        staff = Staff.objects.select_for_update().filter(recovery_email__iexact=data["email"].lower(), is_active=True).first()
        if staff is None or not staff.has_usable_password():
            raise ValidationError(INVALID_CODE)
        challenge = PasswordResetChallenge.objects.filter(staff=staff).first()
        if (
            challenge is None or challenge.used_at or challenge.attempts >= MAX_ATTEMPTS
            or now >= challenge.issued_at + CODE_LIFETIME
        ):
            raise ValidationError(INVALID_CODE)
        if constant_time_compare(challenge.digest, code_digest(challenge.token, staff, data["code"])):
            set_validated_password(staff, data["password"])
            challenge.used_at = now
            challenge.save(update_fields=["used_at"])
            return Response({"ok": True})
        challenge.attempts += 1
        challenge.save(update_fields=["attempts"])
    raise ValidationError(INVALID_CODE)
