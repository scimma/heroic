import logging
import datetime
import time

from django.conf import settings
from django.contrib.auth import logout
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpResponse

from heroic_api.tasks import write_request_metric

logger = logging.getLogger(__name__)


class SCiMMAAuthSessionRefresh:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        logger.debug(f'Checking Keycloak login OIDC token expiration...')

        # Check the oidc token expiration - if expired, return a HTTP 401 to indicate client should logout
        oidc_expiration_seconds = request.session.get('oidc_id_token_expiration')
        if oidc_expiration_seconds:
            if datetime.datetime.now() > datetime.datetime.fromtimestamp(float(oidc_expiration_seconds)):
                logger.debug(f"OIDC login has expired for user {request.user}, forcing logout and returning 401")
                logout(request)
                return HttpResponse('Unauthorized', status=401)

        response = self.get_response(request)  # pass the request to the next Middleware in the list

        # Code to be executed for each request/response after
        # the view is called.
        return response


class InfluxDBRequestLogger:
    """Middleware that records a metric for every request to an InfluxDB v1 database.

    Each request is turned into a single point capturing the endpoint, authenticated user
    (if any), status code, response size and latency. Rather than writing to InfluxDB inline,
    the point is handed to the write_request_metric dramatiq actor so the actual write happens
    on the worker and adds no latency to the request/response path.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        if not settings.INFLUXDB_ENABLED:
            # Tell Django to drop this middleware entirely so it adds zero overhead.
            raise MiddlewareNotUsed()

        self.measurement = settings.INFLUXDB_MEASUREMENT

    def __call__(self, request):
        start = time.monotonic()
        request_time = datetime.datetime.now(datetime.timezone.utc)

        response = self.get_response(request)

        try:
            latency_ms = (time.monotonic() - start) * 1000.0
            point = self._build_point(request, response, request_time, latency_ms)
            write_request_metric.send(point)
        except Exception:
            logger.exception('Failed to enqueue request metric for InfluxDB.')

        return response

    def _build_point(self, request, response, request_time, latency_ms):
        # Use the resolved URL route (e.g. "api/v0/telescopes/<pk>/") rather than the raw
        # path so tag cardinality stays bounded by the number of routes rather than by
        # every distinct path-parameter value.
        resolver_match = getattr(request, 'resolver_match', None)
        if resolver_match is not None and resolver_match.route:
            endpoint = resolver_match.route
        else:
            endpoint = '<unresolved>'

        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            username = user.get_username()
        else:
            username = 'anonymous'

        content_length = response.get('Content-Length')
        if content_length is not None:
            response_size = int(content_length)
        elif getattr(response, 'streaming', False):
            response_size = -1  # size is unknown for streaming responses
        else:
            response_size = len(response.content)

        # 'time' is serialized to an ISO8601 string so the point survives JSON serialization
        return {
            'measurement': self.measurement,
            'time': request_time.isoformat(),
            'tags': {
                'endpoint': endpoint,
                'method': request.method,
                'status_code': response.status_code,
                'user': username,
                'authenticated': username != 'anonymous',
            },
            'fields': {
                'path': request.get_full_path(),
                'client_ip': self._client_ip(request),
                'response_size': response_size,
                'latency_ms': round(latency_ms, 3),
                'count': 1,
            },
        }

    @staticmethod
    def _client_ip(request):
        # the real client is the leftmost X-Forwarded-For entry
        # REMOTE_ADDR is the fallback for dev. The leftmost x-forwarded-for is
        # client-supplied and therefore spoofable, which is acceptable for observability.
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
