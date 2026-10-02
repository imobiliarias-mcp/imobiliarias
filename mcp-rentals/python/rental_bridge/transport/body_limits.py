"""Bound identity-encoded response streams before provider parsers buffer data."""
import httpx

from rental_bridge.errors import BridgeError

RESPONSE_LIMIT = 8 * 1024 * 1024


class LimitedStream(httpx.SyncByteStream):
    """Preserve the HTTPX stream protocol while enforcing a byte budget."""

    def __init__(self, stream, maximum):
        self.stream = stream
        self.maximum = maximum

    def __iter__(self):
        total = 0
        for chunk in self.stream:
            total += len(chunk)
            if total > self.maximum:
                raise BridgeError('output_limit')
            yield chunk

    def close(self):
        """Close the owned upstream stream on success and failures."""
        self.stream.close()


def verify_body_headers(headers, maximum):
    """Reject compression before any decoder runs and oversized declared bodies."""
    encoding = headers.get('content-encoding', 'identity').lower()
    if encoding not in ('', 'identity'):
        raise BridgeError('invalid_content')
    length = headers.get('content-length')
    if length is not None and (not str(length).isdigit() or int(length) > maximum):
        raise BridgeError('output_limit')


def read_httpx_response(response, maximum):
    """Use public response/stream interfaces, never private HTTPX transport state."""
    verify_body_headers(response.headers, maximum)
    if not response.is_stream_consumed:
        response.stream = LimitedStream(response.stream, maximum)
    content = response.read()
    if len(content) > maximum:
        raise BridgeError('output_limit')


def read_requests_response(response, maximum):
    """Read bounded chunks from a streamed requests response and return its bytes."""
    verify_body_headers(response.headers, maximum)
    pieces = []
    total = 0
    for chunk in response.iter_content(chunk_size=65536):
        total += len(chunk)
        if total > maximum:
            raise BridgeError('output_limit')
        pieces.append(chunk)
    return b''.join(pieces)
