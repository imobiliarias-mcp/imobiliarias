"""Security boundary regressions, independent of provider dependencies."""
from typing import ClassVar

import httpx
import pytest
import requests

from rental_bridge.errors import BridgeError
from rental_bridge.transport.safe_http import ensure_response, managed_httpx, managed_requests


@pytest.mark.parametrize(('status', 'code'), [(403, 'blocked'), (429, 'rate_limited'), (503, 'http_error')])
def test_http_failure_is_not_a_collection(status, code):
    response = httpx.Response(status, request=httpx.Request('GET', 'https://example.com'))
    with pytest.raises(BridgeError, match=code):
        ensure_response(response)


def test_http_200_browser_challenge_is_blocked():
    response = httpx.Response(200, text='<html><title>Just a moment...</title><script src="/cdn-cgi/challenge-platform/x"></script></html>', headers={'content-type': 'text/html'})
    with pytest.raises(BridgeError, match='blocked'):
        ensure_response(response)


def test_normal_listing_can_include_turnstile_assets_without_being_blocked():
    response = httpx.Response(200, text='<html><title>Imóveis para alugar - Imovelweb</title><article data-id="123">Imóvel</article><input id="cf-chl-widget-z_response"><script src="/cdn-cgi/challenge-platform/scripts/jsd/main.js"></script><style>.captcha-container{color:red}</style></html>')
    assert ensure_response(response) is response


def test_redirect_is_not_followed_to_arbitrary_host():
    transport = httpx.MockTransport(lambda request: httpx.Response(302, headers={'location': 'http://127.0.0.1/admin'}))
    with managed_httpx(transport=transport) as client, pytest.raises(BridgeError, match='http_error'):
        client.get('https://example.com')


def test_httpx_body_limit_is_checked_while_streaming():
    class LargeStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b'x' * 64
            yield b'x' * 64
            pytest.fail('must stop before reading remaining upstream data')
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=LargeStream()))
    with managed_httpx(transport=transport, response_limit=100) as client, pytest.raises(BridgeError, match='output_limit'):
        client.get('https://example.com')


def test_compressed_body_is_rejected_before_decompression():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, headers={'content-encoding': 'gzip'}, stream=httpx.ByteStream(b'not-read')))
    with managed_httpx(transport=transport) as client, pytest.raises(BridgeError, match='invalid_content'):
        client.get('https://example.com')


def test_requests_reads_are_bounded_and_close_on_size_failure(monkeypatch):
    class Response:
        status_code = 200
        headers: ClassVar[dict[str, str]] = {'content-type': 'application/json'}
        text = '{}'
        closed = False
        def __enter__(self): return self
        def __exit__(self, *arguments): self.closed = True
        def iter_content(self, chunk_size):
            yield b'x' * (8 * 1024 * 1024 + 1)
            pytest.fail('must stop after limit')
    response = Response()
    monkeypatch.setattr(requests.Session, 'request', lambda *arguments, **keywords: response)
    with managed_requests() as client, pytest.raises(BridgeError, match='output_limit'):
        client.get('https://example.com')
    assert response.closed


def test_managed_client_closes_after_error():
    with pytest.raises(ValueError), managed_httpx() as client:
        raise ValueError('fixture')
    assert client.is_closed
