"""Validate the versioned schemas exported by the central TypeScript build."""
import json
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from rental_bridge.errors import BridgeError

PROVIDER_IDS = (
    'alecorretoramg', 'arthusoimoveis', 'cabralporto', 'casalinhares',
    'epifanioimoveis', 'helenaimoveis', 'imobiliariaportalmg', 'imobiliariavaleinvest',
    'imovelweb', 'marcioimoveis', 'minascaixaimoveis', 'niltoncorretordeimoveis',
    'novaimobiliaria', 'veraimobiliaria', 'vivareal',
)


def load_contracts():
    """Read only installed build schemas; missing or mismatched versions fail early."""
    default = Path(__file__).resolve().parents[2] / 'dist/contracts/providers.json'
    path = Path(os.environ.get('RENTAL_CONTRACTS', default))
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('version') != 1 or [item['id'] for item in data['providers']] != list(PROVIDER_IDS):
        raise BridgeError('invalid_input')
    return data


def specification(provider):
    """Resolve an ID from the fixed installed registry, never from a module path."""
    if provider not in PROVIDER_IDS:
        raise BridgeError('invalid_input')
    return next(item for item in load_contracts()['providers'] if item['id'] == provider)


def validate_request(value):
    """Validate operation and arguments again before importing any source modules."""
    _validate_envelope(value)
    source = specification(value['provider'])
    operation = value['operation']
    arguments = value['arguments']
    _validate_arguments(_operation_schema(source, operation), arguments)
    _validate_combinations(value)
    if operation == 'detail' and str(arguments['reference']).startswith(('http://', 'https://')):
        validate_public_url(arguments['reference'], value['provider'])
    return value


def _operation_schema(source, operation):
    if operation == 'detail':
        return {'type': 'object', 'properties': {'reference': source['reference']}, 'required': ['reference'], 'additionalProperties': False}
    if operation == 'facets':
        return source['facets']
    return source['filters']


def _validate_combinations(request):
    if request['provider'] != 'vivareal' or request['operation'] != 'search':
        return
    arguments = request['arguments']
    if 'page' in arguments and 'offset' in arguments:
        raise BridgeError('invalid_input')
    if arguments.get('offset', 0) % arguments.get('size', 30):
        raise BridgeError('invalid_input')


def _validate_envelope(value):
    required = {'version', 'provider', 'operation', 'arguments'}
    if not isinstance(value, dict) or set(value) != required or type(value['version']) is not int or value['version'] != 1:
        raise BridgeError('invalid_input')
    if value['operation'] not in ('search', 'detail', 'facets') or not isinstance(value['arguments'], dict):
        raise BridgeError('invalid_input')


def _validate_arguments(schema, arguments):
    if schema is None:
        raise BridgeError('unsupported_capability')
    try:
        Draft202012Validator(schema).validate(arguments)
    except ValidationError as error:
        raise BridgeError('invalid_input') from error
    _reject_empty_text(arguments)
    _validate_ranges(arguments)


def _reject_empty_text(value):
    if isinstance(value, str) and (not value.strip() or len(value) > 2048):
        raise BridgeError('invalid_input')
    if isinstance(value, dict):
        list(map(_reject_empty_text, value.values()))
    if isinstance(value, list):
        list(map(_reject_empty_text, value))


def _validate_ranges(arguments):
    pairs = [('min_price', 'max_price'), ('minimum_price', 'maximum_price'), ('min_area', 'max_area'), ('minimum_area', 'maximum_area')]
    for minimum, maximum in pairs:
        lower, upper = arguments.get(minimum), arguments.get(maximum)
        if isinstance(lower, (int, float)) and isinstance(upper, (int, float)) and upper > 0 and lower > upper:
            raise BridgeError('invalid_input')


def validate_public_url(value, provider):
    """Preserve only genuine public property URLs on a provider-specific allowlist."""
    source = specification(provider)
    try:
        parsed = urlsplit(value)
        decoded = value
        for _ in range(4):
            decoded = unquote(decoded)
        _validate_url_parts(parsed, decoded, source)
    except (TypeError, ValueError) as error:
        raise BridgeError('invalid_input') from error
    return value


def _validate_url_parts(parsed, decoded, source):
    if parsed.scheme not in ('http', 'https') or parsed.hostname not in source['public_hosts']:
        raise BridgeError('invalid_input')
    if parsed.username or parsed.password or parsed.port or parsed.fragment:
        raise BridgeError('invalid_input')
    if '\\' in decoded or re.search(r'(?:/|^)\.{1,2}(?:/|[?#]|$)|[\x00-\x20]', decoded):
        raise BridgeError('invalid_input')
    target = parsed.path
    if parsed.query:
        target += '?' + parsed.query
    if not re.search(source['detail_path_pattern'], target):
        raise BridgeError('invalid_input')
