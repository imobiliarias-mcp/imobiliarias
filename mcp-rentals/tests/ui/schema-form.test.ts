import assert from 'node:assert/strict';
import { test } from 'node:test';
import { JSDOM } from 'jsdom';
import { createSchemaForm, readSchemaForm } from '../../ui/schema-form.js';

const searchSchema = {
  type: 'object',
  required: ['city'],
  additionalProperties: false,
  properties: {
    city: { type: 'string', title: 'Município', description: 'Nome da cidade.' },
    bedrooms: { type: 'integer', title: 'Quartos', unit: 'quartos', minimum: 1 },
    furnished: { type: 'boolean', title: 'Mobiliado' },
    property_type: { type: 'string', title: 'Tipo', enum: ['house', 'apartment'], enumTitles: ['Casa', 'Apartamento'] },
  },
} as const;

test('schema form exposes labeled required, unit, enum, and optional boolean controls', () => {
  const document = new JSDOM('<!doctype html><html><body></body></html>').window.document;
  const form = createSchemaForm(document, searchSchema, 'filters');
  document.body.append(form);

  assert.equal(form.querySelector('label[for="filters-city"]')?.textContent, 'Município');
  assert.equal(form.querySelector<HTMLInputElement>('#filters-city')?.required, true);
  assert.equal(form.querySelector('label[for="filters-bedrooms"]')?.textContent, 'Quartos (quartos)');
  assert.deepEqual(
    Array.from(form.querySelectorAll('#filters-property_type option')).map((option) => option.textContent),
    ['Selecione', 'Casa', 'Apartamento'],
  );
  assert.equal(form.querySelector<HTMLSelectElement>('#filters-furnished')?.value, '');
});

test('reading schema form returns typed declared fields and excludes unknown input', () => {
  const document = new JSDOM('<!doctype html><html><body></body></html>').window.document;
  const form = createSchemaForm(document, searchSchema, 'filters');
  document.body.append(form);
  form.querySelector<HTMLInputElement>('#filters-city')!.value = 'Timóteo';
  form.querySelector<HTMLInputElement>('#filters-bedrooms')!.value = '2';
  form.querySelector<HTMLSelectElement>('#filters-furnished')!.value = 'false';
  form.querySelector<HTMLSelectElement>('#filters-property_type')!.value = 'apartment';
  const unknown = document.createElement('input');
  unknown.name = 'filters-arbitrary';
  unknown.value = 'ignored';
  form.append(unknown);

  assert.deepEqual(readSchemaForm(form, searchSchema), {
    city: 'Timóteo',
    bedrooms: 2,
    furnished: false,
    property_type: 'apartment',
  });
});

test('multi-select array fields submit only the explicitly selected values', () => {
  const document = new JSDOM('<!doctype html><html><body></body></html>').window.document;
  const schema = {
    type: 'object',
    properties: { cities: { type: 'array', title: 'Cidades', items: { type: 'string', enum: ['timoteo', 'ipatinga'] } } },
  } as const;
  const form = createSchemaForm(document, schema, 'filters');
  const select = form.querySelector<HTMLSelectElement>('#filters-cities')!;
  select.options[1]!.selected = true;
  select.options[2]!.selected = true;

  assert.deepEqual(readSchemaForm(form, schema), { cities: ['timoteo', 'ipatinga'] });
});

test('renders const schema values as fixed options and automatically supplies them', () => {
  const document = new JSDOM('<!doctype html><html><body></body></html>').window.document;
  const schema = {
    type: 'object',
    required: ['selector'],
    properties: { selector: { type: 'string', const: 'location_suggestions' } },
  } as const;
  const form = createSchemaForm(document, schema, 'facets');
  const selector = form.querySelector<HTMLSelectElement>('[name="selector"]');

  assert.ok(selector);
  assert.equal(selector.disabled, true);
  assert.deepEqual(Array.from(selector.options, (option) => option.value), ['location_suggestions']);
  assert.deepEqual(readSchemaForm(form, schema), { selector: 'location_suggestions' });
});

test('reading empty optional fields omits them without inventing defaults', () => {
  const document = new JSDOM('<!doctype html><html><body></body></html>').window.document;
  const form = createSchemaForm(document, searchSchema, 'filters');
  form.querySelector<HTMLInputElement>('#filters-city')!.value = 'Timóteo';

  assert.deepEqual(readSchemaForm(form, searchSchema), { city: 'Timóteo' });
});
