import { test } from 'node:test';
import assert from 'node:assert/strict';
import { facets_output } from '../../src/contracts/responses.js';

import { display_item } from '../../src/contracts/responses.js';

test('display preserves a typed detail reference instead of converting slug into ID', () => {
  const item = {reference: {kind: 'slug', value: 'apartamento-centro'}, title: 'Apartamento'};
  assert.deepEqual(display_item.parse(item), item);
});

test('facet output schema accepts its discriminator without weakening provider envelopes', () => {
  const result = {provider: 'vivareal', status: 'ok', native: {suggestions: []}, display: [], kind: 'location_suggestions'};
  assert.deepEqual(facets_output.parse(result), result);
  assert.throws(() => facets_output.parse({...result, command: 'arbitrary'}));
});
