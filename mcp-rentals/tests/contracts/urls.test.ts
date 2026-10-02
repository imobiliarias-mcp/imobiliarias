import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validate_public_url } from '../../src/contracts/urls.js';

const specification = JSON.parse(readFileSync(new URL('../../provider-specs/vivareal.json', import.meta.url), 'utf8'));
test('public URL policy treats explicit default ports consistently in Python and Node', () => {
  assert.throws(() => validate_public_url('https://www.vivareal.com.br:443/imovel/apartamento-123/', specification));
  assert.equal(validate_public_url('https://www.vivareal.com.br/imovel/apartamento-123/', specification), 'https://www.vivareal.com.br/imovel/apartamento-123/');
});
