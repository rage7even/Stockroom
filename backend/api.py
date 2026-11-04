import json
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta
from functools import wraps
from threading import Lock

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.db import IntegrityError
from django.http import JsonResponse
from django.utils import timezone

from backend.models import Session
from backend.security import token_hash

attempts = defaultdict(deque)
attempts_lock = Lock()


class APIError(Exception):
    def __init__(self, status, detail):
        self.status = status
        self.detail = detail


def current_user(request):
    session = Session.objects.select_related('staff').filter(
        token_hash=token_hash(request.COOKIES.get('stockroom_session', '')),
        staff__is_active=1,
    ).first()
    # Compare parsed datetimes: legacy SQLite rows used ISO "T", Django uses a space.
    if session is None or session.expires_at <= timezone.now():
        raise APIError(401, 'Please sign in to continue')
    return session.staff


def endpoint(methods, roles=None):
    """Django view boundary: JSON errors, authentication and server-side roles."""
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                response = JsonResponse({'detail': 'Method not allowed'}, status=405)
                response['Allow'] = ', '.join(methods)
                return response
            try:
                if roles is not None:
                    request.staff = current_user(request)
                    if request.staff.role not in roles:
                        raise APIError(403, 'You do not have permission for this action')
                result = view(request, *args, **kwargs)
                if isinstance(result, (dict, list)):
                    return JsonResponse(result, safe=isinstance(result, dict))
                return result
            except APIError as exc:
                return JsonResponse({'detail': exc.detail}, status=exc.status)
            except RequestDataTooBig:
                return JsonResponse({'detail': 'Request body is too large'}, status=413)
            except IntegrityError:
                return JsonResponse({'detail': 'This record conflicts with a unique value or a data rule. Nothing was saved.'}, status=409)
        return wrapped
    return decorate


def payload(request, form_type):
    if request.content_type != 'application/json':
        raise APIError(422, 'Send a JSON object')
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise APIError(422, 'Invalid JSON')
    if not isinstance(data, dict):
        raise APIError(422, 'Send a JSON object')
    form = form_type(data)
    if not form.is_valid():
        detail = [
            {'loc': ['body', field], 'msg': str(message)}
            for field, messages in form.errors.items() for message in messages
        ]
        raise APIError(422, detail)
    return form.cleaned_data


def staff_data(staff, active=False):
    keys = ('staff_id', 'full_name', 'login', 'role') + (('is_active',) if active else ())
    return {key: getattr(staff, key) for key in keys}


def set_session(response, staff):
    token = secrets.token_urlsafe(32)
    Session.objects.filter(expires_at__lt=timezone.now()).delete()
    Session.objects.create(token_hash=token_hash(token), staff=staff, expires_at=timezone.now() + timedelta(hours=8))
    response.set_cookie('stockroom_session', token, httponly=True, samesite='Strict',
                        secure=settings.STOCKROOM_SECURE_COOKIE, max_age=28800, path='/')


def rate_limit(request):
    key = request.META.get('REMOTE_ADDR', 'local')
    moment = time.monotonic()
    with attempts_lock:
        queue = attempts[key]
        while queue and queue[0] < moment - 60:
            queue.popleft()
        if len(queue) >= 12:
            raise APIError(429, 'Too many sign-in attempts. Try again in one minute.')
        queue.append(moment)
