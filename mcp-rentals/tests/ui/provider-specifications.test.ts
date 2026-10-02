import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { JSDOM } from 'jsdom';
import { setupRentalApp } from '../../ui/setup.js';
import { supportsReference } from '../../ui/reference-validation.js';
import { readSchemaForm } from '../../ui/schema-form-reader.js';
import { createSchemaForm, type JsonSchema } from '../../ui/schema-form.js';
import { FakeRentalApp } from './fake-app.js';
import type { RentalProvider } from '../../ui/types.js';

interface ProviderSpecification extends Omit<RentalProvider, 'capabilities' | 'installation'> {}

interface SearchFixture {
  root: HTMLElement;
  app: FakeRentalApp;
}

function readProviderSpecification(providerId: string): ProviderSpecification {
  const path = new URL(`../../provider-specs/${providerId}.json`, import.meta.url);
  return JSON.parse(readFileSync(path, 'utf8')) as ProviderSpecification;
}

function createDocument(): Document {
  return new JSDOM('<!doctype html><html><body></body></html>').window.document;
}

function readFacetSchema(providerId: string): JsonSchema {
  return readProviderSpecification(providerId).facets ?? {};
}

function selectFacetBranch(document: Document, form: HTMLFormElement, selector: string): void {
  const control = form.querySelector<HTMLSelectElement>('[data-schema-variant]')!;
  control.value = selector;
  control.dispatchEvent(new document.defaultView!.Event('change', { bubbles: true }));
}

function createRuntimeProvider(specification: ProviderSpecification, reference = specification.reference): RentalProvider {
  return {
    ...specification,
    reference,
    capabilities: { search: true, detail: true, facets: Boolean(specification.facets) },
    installation: { available: true },
  };
}

function createRoot(): HTMLElement {
  const document = createDocument();
  const root = document.createElement('main');
  document.body.append(root);
  return root;
}

async function startSearch(providerId: string, native: unknown, display: unknown[] = [], reference?: JsonSchema): Promise<SearchFixture> {
  const provider = createRuntimeProvider(readProviderSpecification(providerId), reference);
  const root = createRoot();
  const app = new FakeRentalApp();
  app.queue('list_rental_providers', { structuredContent: { providers: [provider] } });
  app.queue('search_rentals', { structuredContent: { status: 'ok', providers: [{ provider: providerId, status: 'ok', native, display }] } });
  const lifecycle = setupRentalApp(root, app, () => app.connect());
  await lifecycle.ready;
  root.querySelector<HTMLInputElement>('[data-provider-selection]')!.checked = true;
  root.querySelector<HTMLButtonElement>('[data-action="search"]')!.click();
  await new Promise((resolve) => setTimeout(resolve, 0));
  return { root, app };
}

async function requestNextPage(root: HTMLElement, app: FakeRentalApp): Promise<unknown> {
  const button = root.querySelector<HTMLButtonElement>('[data-action="next-page"]');
  assert.ok(button);
  button.click();
  await new Promise((resolve) => setTimeout(resolve, 0));
  return app.calls.filter((call) => call.name === 'search_rentals')[1]?.arguments;
}

test('validates typed Arthuso references from the actual oneOf schema before object fallback', () => {
  const schema = readProviderSpecification('arthusoimoveis').reference;
  assert.equal(supportsReference({ kind: 'slug', value: 'apartamento-centro-123' }, schema), true);
  assert.equal(supportsReference({ kind: 'id', value: '123' }, schema), true);
  assert.equal(supportsReference({ kind: 'id', value: 'abc' }, schema), false);
  assert.equal(supportsReference({ kind: 'slug', value: 'bad slug' }, schema), false);
  const objectSchema = { ...schema, type: 'object' } as JsonSchema;
  assert.equal(supportsReference({ kind: 'slug', value: 'apartamento-centro-123' }, objectSchema), true);
  assert.equal(supportsReference({ kind: 'id', value: 'abc' }, objectSchema), false);
});

test('rejects invalid Arthuso IDs before requesting details using actual provider metadata', async () => {
  const schema = readProviderSpecification('arthusoimoveis').reference;
  const result = await startSearch('arthusoimoveis', {}, [
    { reference: { kind: 'slug', value: 'apartamento-centro-123' }, title: 'Valid slug' },
    { reference: { kind: 'id', value: 'abc' }, title: 'Invalid ID' },
  ], schema);
  const buttons = result.root.querySelectorAll<HTMLButtonElement>('[data-provider-results="arthusoimoveis"] [data-action="detail"]');
  assert.equal(buttons.length, 1);
  result.app.queue('get_rental_detail', { structuredContent: { provider: 'arthusoimoveis', status: 'ok', native: {}, display: { title: 'Details' } } });
  buttons[0]!.click();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(result.app.calls.find((call) => call.name === 'get_rental_detail')?.arguments, {
    provider: 'arthusoimoveis', reference: { kind: 'slug', value: 'apartamento-centro-123' },
  });
});

test('renders branch-specific facets from the actual Minas Caixa schema', () => {
  const document = createDocument();
  const schema = readFacetSchema('minascaixaimoveis');
  const form = createSchemaForm(document, schema, 'minas-facets');
  const branchControl = form.querySelector<HTMLSelectElement>('[data-schema-variant]');
  assert.ok(branchControl);
  assert.equal(form.querySelector('input[name="city"]'), null);

  selectFacetBranch(document, form, 'neighborhoods');
  const city = form.querySelector<HTMLInputElement>('input[name="city"]');
  assert.equal(city?.required, true);
  if (city) city.value = 'timoteo-mg';
  assert.deepEqual(readSchemaForm(form, schema), { selector: 'neighborhoods', city: 'timoteo-mg' });
});

test('renders typed Vera facet fields from the actual oneOf schema', () => {
  const document = createDocument();
  const schema = readFacetSchema('veraimobiliaria');
  const form = createSchemaForm(document, schema, 'vera-facets');
  selectFacetBranch(document, form, 'neighborhoods');
  const city = form.querySelector<HTMLInputElement>('input[name="city_id"]');
  assert.equal(city?.required, true);
  if (city) city.value = '42';
  assert.deepEqual(readSchemaForm(form, schema), { selector: 'neighborhoods', city_id: 42, transaction_type: 1 });
});

test('uses Nova offset pagination from native total-page metadata', async () => {
  const nova = await startSearch('novaimobiliaria', { meta: { pagination: { current_page: 2, total_pages: 5 } } });
  assert.match(nova.root.textContent ?? '', /Página 2 de 5/);
  assert.deepEqual(await requestNextPage(nova.root, nova.app), {
    requests: [{ provider: 'novaimobiliaria', filters: { city: 'timoteo-mg', offset: 3 } }],
  });
});

test('uses Vera has-next metadata without inventing a maximum', async () => {
  const vera = await startSearch('veraimobiliaria', { items: [], current_page: 2, has_next_page: true });
  assert.match(vera.root.textContent ?? '', /Página 2/);
  assert.doesNotMatch(vera.root.textContent ?? '', /Página 2 de/);
  assert.deepEqual(await requestNextPage(vera.root, vera.app), {
    requests: [{ provider: 'veraimobiliaria', filters: { page: 3 } }],
  });
});

test('uses Viva page pagination when native metadata confirms another page', async () => {
  const viva = await startSearch('vivareal', { current_page: 4, has_next_page: true });
  assert.deepEqual(await requestNextPage(viva.root, viva.app), {
    requests: [{ provider: 'vivareal', filters: { page: 5 } }],
  });
});

test('does not offer Vera next page when the native flag is false', async () => {
  const vera = await startSearch('veraimobiliaria', { items: [], current_page: 2, has_next_page: false });
  assert.equal(vera.root.querySelector('[data-action="next-page"]'), null);
  assert.ok(vera.root.querySelector('[data-action="previous-page"]'));
});
