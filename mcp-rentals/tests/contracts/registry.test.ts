import { test } from 'node:test';
import assert from 'node:assert/strict';
import { provider_ids, validate_search, validate_facets, validate_detail } from '../../src/contracts/index.js';

const expected = ['alecorretoramg', 'arthusoimoveis', 'cabralporto', 'casalinhares', 'epifanioimoveis', 'helenaimoveis', 'imobiliariaportalmg', 'imobiliariavaleinvest', 'imovelweb', 'marcioimoveis', 'minascaixaimoveis', 'niltoncorretordeimoveis', 'novaimobiliaria', 'veraimobiliaria', 'vivareal'];
test('catalog enumerates exactly the 15 source IDs', () => assert.deepEqual(provider_ids, expected));
test('whole request rejects unknown providers, duplicates and unsupported filters', () => {
  assert.throws(() => validate_search({requests: [{provider: 'unknown', filters: {}}]}));
  assert.throws(() => validate_search({requests: expected.slice(0, 2).map(() => ({provider: expected[0], filters: {}}))}));
  assert.throws(() => validate_search({requests: [{provider: 'imovelweb', filters: {minimum_price: 100}}]}));
  assert.throws(() => validate_search({requests: [{provider: 'minascaixaimoveis', filters: {neighborhood: 'Centro'}}]}));
  assert.throws(() => validate_search({requests: [{provider: expected[0], filters: {transaction: 'sale'}}]}));
});
test('provider cross-field constraints are rejected before execution', () => {
  assert.throws(() => validate_search({requests: [{provider: 'vivareal', filters: {page: 2, offset: 30}}]}));
  assert.throws(() => validate_search({requests: [{provider: 'vivareal', filters: {offset: 1, size: 30}}]}));
  assert.throws(() => validate_search({requests: [{provider: 'vivareal', filters: {min_price: 2000, max_price: 1000}}]}));
});

test('facets require explicit cities and do not invent Helena capability', () => {
  assert.throws(() => validate_facets({provider: 'veraimobiliaria', request: {selector: 'neighborhoods'}}));
  assert.throws(() => validate_facets({provider: 'minascaixaimoveis', request: {selector: 'neighborhoods'}}));
  assert.throws(() => validate_facets({provider: 'helenaimoveis', request: {selector: 'all'}}));
  assert.throws(() => validate_facets({provider: 'vivareal', request: {selector: 'location_suggestions', query: ' '}}));
});
test('typed detail references reject ID-slug confusion before any worker', () => {
  assert.throws(() => validate_detail({provider: 'arthusoimoveis', reference: {kind: 'id', value: 'apartamento-centro'}}));
  assert.throws(() => validate_detail({provider: 'niltoncorretordeimoveis', reference: 'codigo-comercial'}));
  assert.throws(() => validate_detail({provider: 'novaimobiliaria', reference: '../properties'}));
});

test('detail rejects URL confusion and arbitrary destinations', () => {
  for (const reference of ['http://127.0.0.1/imovel/x', 'https://www.vivareal.com.br/api/x', 'https://user:pass@www.vivareal.com.br/imovel/x', 'https://www.vivareal.com.br:444/imovel/x', 'https://www.vivareal.com.br:443/imovel/x', 'https://www.vivareal.com.br/imovel/../api']) {
    assert.throws(() => validate_detail({provider: 'vivareal', reference}));
  }
  assert.equal(validate_detail({provider: 'vivareal', reference: 'https://www.vivareal.com.br/imovel/apartamento-123/'}).provider, 'vivareal');
});
