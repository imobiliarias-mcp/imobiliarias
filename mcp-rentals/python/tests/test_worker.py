"""The bridge never imports a provider or contaminates stdout for invalid input."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize('payload', [b'{', b'NaN', b'{"version":true,"provider":"unknown","operation":"search","arguments":{}}', b'{"version":1,"provider":"alecorretoramg","operation":"search","arguments":{"min_price":1e999}}', b'x' * 65537])
def test_invalid_stdin_emits_one_safe_input_error(payload):
    env = {
        **os.environ,
        'PYTHONPATH': str(Path(__file__).resolve().parents[1]),
        'RENTAL_CONTRACTS': str(Path(__file__).resolve().parents[2] / 'dist/contracts/providers.json'),
    }
    result = subprocess.run([sys.executable, '-m', 'rental_bridge.worker'], input=payload, capture_output=True, check=True, env=env, timeout=5)
    response = json.loads(result.stdout)
    assert response['status'] == 'error'
    assert response['error']['code'] == 'invalid_input'
    assert result.stderr == b''
    assert response['version'] == 1
