import { test } from 'node:test';
import assert from 'node:assert/strict';
import { verify_contract_build } from '../../src/contracts/build.js';

test('missing or stale exported Python contracts fail before serving tools', () => {
  const providers = [{id: 'source', filters: {type: 'object'}}];
  assert.throws(() => verify_contract_build(undefined, providers));
  assert.throws(() => verify_contract_build({version: 2, providers}, providers));
  assert.throws(() => verify_contract_build({version: 1, providers: [{id: 'source', filters: {type: 'string'}}]}, providers));
  assert.doesNotThrow(() => verify_contract_build({version: 1, providers}, providers));
});
