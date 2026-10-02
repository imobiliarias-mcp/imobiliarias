import { test } from 'node:test';
import assert from 'node:assert/strict';
import { search_result } from '../../src/application/results.js';

test('text fallback preserves typed reference, price and location plus the exact public link', () => {
  const result = search_result([{provider: 'arthusoimoveis', status: 'ok', native: {}, display: [{reference: {kind: 'slug', value: 'apartamento-centro'}, title: 'Apartamento', location: 'Centro', price: {rent: 1200}, url: 'https://arthusoimoveis.com.br/imovel/apartamento-centro/'}]}]);
  const text = result.content[0]!.text;
  assert.match(text, /"kind":"slug"/);
  assert.match(text, /Centro/);
  assert.match(text, /1200/);
  assert.match(text, /https:\/\/arthusoimoveis\.com\.br\/imovel\/apartamento-centro\//);
});
