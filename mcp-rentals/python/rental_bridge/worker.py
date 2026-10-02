"""One request per provider process; stdout contains only the versioned contract."""
import importlib
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from rental_bridge.contracts import load_contracts, validate_public_url, validate_request
from rental_bridge.errors import BridgeError, safe_error
from rental_bridge.serialization.projection import clean_projection

REGISTRY = {
    'alecorretoramg': 'rental_bridge.providers.alecorretoramg',
    'arthusoimoveis': 'rental_bridge.providers.arthusoimoveis',
    'cabralporto': 'rental_bridge.providers.cabralporto',
    'casalinhares': 'rental_bridge.providers.casalinhares',
    'epifanioimoveis': 'rental_bridge.providers.epifanioimoveis',
    'helenaimoveis': 'rental_bridge.providers.helenaimoveis',
    'imobiliariaportalmg': 'rental_bridge.providers.imobiliariaportalmg',
    'imobiliariavaleinvest': 'rental_bridge.providers.imobiliariavaleinvest',
    'imovelweb': 'rental_bridge.providers.imovelweb',
    'marcioimoveis': 'rental_bridge.providers.marcioimoveis',
    'minascaixaimoveis': 'rental_bridge.providers.minascaixaimoveis',
    'niltoncorretordeimoveis': 'rental_bridge.providers.niltoncorretordeimoveis',
    'novaimobiliaria': 'rental_bridge.providers.novaimobiliaria',
    'veraimobiliaria': 'rental_bridge.providers.veraimobiliaria',
    'vivareal': 'rental_bridge.providers.vivareal',
}


def read_request():
    """Bound raw input before JSON parsing; reject nonfinite numeric extensions."""
    raw = sys.stdin.buffer.read(65537)
    if len(raw) > 65536:
        raise BridgeError('invalid_input')
    try:
        return validate_request(json.loads(raw, parse_constant=_invalid_constant, parse_float=_parse_float))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise BridgeError('invalid_input') from error


def _invalid_constant(value):
    raise BridgeError('invalid_input')


def _parse_float(value):
    import math
    number = float(value)
    if not math.isfinite(number):
        raise BridgeError('invalid_input')
    return number


def execute_request(request):
    """Call only an adapter selected from the fixed registry, suppressing legacy logs."""
    with open(os.devnull, 'w') as sink, redirect_stdout(sink), redirect_stderr(sink):
        module = importlib.import_module(REGISTRY[request['provider']])
        payload = module.execute(request['operation'], request['arguments'])
    result = {'version': 1, 'status': 'ok', **payload}
    result['display'] = list(map(clean_projection, result['display']))
    _validate_output(result, request['provider'])
    return result


def _validate_output(result, provider):
    Draft202012Validator(load_contracts()['worker_response']).validate(result)
    for item in result['display']:
        if 'url' in item:
            validate_public_url(item['url'], provider)
    json.dumps(result, allow_nan=False)


def main():
    """Serve one safe response; unexpected exceptions cross only as normalized errors."""
    try:
        result = execute_request(read_request())
    except (BridgeError, ImportError, ValueError, TypeError, KeyError, RuntimeError, OSError, ValidationError, OverflowError) as error:
        result = {'version': 1, 'status': 'error', 'error': safe_error(error)}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
