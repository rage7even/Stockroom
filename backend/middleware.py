from django.conf import settings
from django.http import JsonResponse


class RequestGuard:
    """Keep the existing same-origin JSON cookie API contract used by Angular."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Validate Host even without Django's CommonMiddleware.
        host = request.get_host()
        origin = request.headers.get('Origin')
        allowed = {*settings.STOCKROOM_ALLOWED_ORIGINS, f'{request.scheme}://{host}'}
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and origin and origin not in allowed:
            response = JsonResponse({'detail': 'Untrusted request origin'}, status=403)
        elif request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and request.headers.get('Sec-Fetch-Site') == 'cross-site':
            response = JsonResponse({'detail': 'Untrusted request origin'}, status=403)
        else:
            response = self.get_response(request)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        if request.path.startswith('/api/'):
            response['Cache-Control'] = 'no-store'
        return response
