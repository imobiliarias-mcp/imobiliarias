"""Verified, owned HTTP clients with guards before existing provider parsers."""
import ssl
from contextlib import contextmanager

import httpx
import requests

from rental_bridge.errors import BridgeError
from rental_bridge.transport.body_limits import (
    RESPONSE_LIMIT,
    read_httpx_response,
    read_requests_response,
)


def ensure_response(response):
    """Reject status failures and contextual browser challenges before parsing."""
    ensure_status(response.status_code)
    ensure_content(response.text)
    return response


def ensure_status(status):
    """Reject upstream status failures before buffering any response body."""
    if status in (401, 403):
        raise BridgeError('blocked')
    if status == 429:
        raise BridgeError('rate_limited')
    if not 200 <= status < 300:
        raise BridgeError('http_error')


def ensure_content(text):
    """Identify contextual challenge documents without blocking legitimate site names."""
    lowered = text.lower()
    markers = ('<title>just a moment', '<title>access denied',
               'id="challenge-form"', "id='challenge-form'", '<title>verify you are human')
    if any(marker in lowered for marker in markers):
        raise BridgeError('blocked')


def _check_response(response, maximum=RESPONSE_LIMIT):
    read_httpx_response(response, maximum)
    ensure_response(response)


@contextmanager
def managed_httpx(**kwargs):
    """Own a verified client; no redirects/retries or untrusted environment proxies."""
    maximum = kwargs.pop('response_limit', RESPONSE_LIMIT)
    if not isinstance(maximum, int) or not 1 <= maximum <= RESPONSE_LIMIT:
        raise BridgeError('invalid_input')
    kwargs.update(verify=True, follow_redirects=False, trust_env=False)
    kwargs.setdefault('timeout', 25)
    kwargs['headers'] = {**kwargs.get('headers', {}), 'Accept-Encoding': 'identity'}
    kwargs['event_hooks'] = {'response': [lambda response: _check_response(response, maximum)]}
    try:
        with httpx.Client(**kwargs) as client:
            yield client
    except httpx.TransportError as error:
        raise BridgeError(_transport_code(error)) from error


def _transport_code(error):
    current = error
    while current is not None:
        if isinstance(current, ssl.SSLError) or 'CERTIFICATE_VERIFY_FAILED' in str(current):
            return 'tls_error'
        current = current.__cause__
    return 'http_error'


class GuardedSession(requests.Session):
    """Keep the public requests.Session protocol without permitting redirect fetches."""

    def request(self, method, url, **kwargs):
        """Request with verified TLS and guard content before returning to a parser."""
        kwargs.update(verify=True, allow_redirects=False, stream=True)
        kwargs.setdefault('timeout', 25)
        kwargs['headers'] = {**kwargs.get('headers', {}), 'Accept-Encoding': 'identity'}
        try:
            with super().request(method, url, **kwargs) as response:
                return _snapshot_response(response, method, url)
        except requests.exceptions.SSLError as error:
            raise BridgeError('tls_error') from error
        except requests.exceptions.RequestException as error:
            raise BridgeError('http_error') from error


def _snapshot_response(response, method, url):
    ensure_status(response.status_code)
    content = read_requests_response(response, RESPONSE_LIMIT)
    snapshot = httpx.Response(response.status_code, headers=response.headers, content=content, request=httpx.Request(method, url))
    return ensure_response(snapshot)


@contextmanager
def managed_requests():
    """Own a guarded requests session for core providers using its public interface."""
    with GuardedSession() as session:
        session.trust_env = False
        yield session


def safe_url(url, provider):
    """Validate a public card URL against the installed provider-specific contract."""
    from rental_bridge.contracts import validate_public_url
    return validate_public_url(url, provider)
