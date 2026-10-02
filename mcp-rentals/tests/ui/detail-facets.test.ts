import assert from 'node:assert/strict';
import { test } from 'node:test';
import { JSDOM } from 'jsdom';
import { setupRentalApp } from '../../ui/setup.js';
import { FakeRentalApp } from './fake-app.js';
import { catalogResult } from './catalog-fixture.js';

function createRoot(): HTMLElement {
  const document = new JSDOM('<!doctype html><html><body><main id="app"></main></body></html>').window.document;
  return document.querySelector<HTMLElement>('#app')!;
}

async function flushUi(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

async function startRentalSearch(root: HTMLElement, app: FakeRentalApp, display: unknown[]): Promise<void> {
  app.queue('list_rental_providers', catalogResult);
  app.queue('search_rentals', { structuredContent: { status: 'ok', providers: [{ provider: 'alfa', status: 'ok', native: {}, display }] } });
  const lifecycle = setupRentalApp(root, app, () => app.connect());
  await lifecycle.ready;
  root.querySelector<HTMLInputElement>('[data-provider-id="alfa"] [data-provider-selection]')!.checked = true;
  root.querySelector<HTMLButtonElement>('[data-action="search"]')!.click();
  await flushUi();
}

test('calls detail only for a reference allowed by that provider schema', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  await startRentalSearch(root, app, [
    { reference: 'A-31', url: 'https://imoveis.example/a-31', title: 'Apartamento' },
    { reference: 'https://imoveis.example/api/private', title: 'Referência não compatível' },
  ]);
  app.queue('get_rental_detail', { structuredContent: { provider: 'alfa', status: 'ok', native: {}, display: [{ title: 'Detalhe do imóvel', price: 1700 }] } });

  const detailButtons = root.querySelectorAll<HTMLButtonElement>('[data-provider-results="alfa"] [data-action="detail"]');
  assert.equal(detailButtons.length, 1);
  detailButtons[0]!.click();
  await flushUi();

  const detailCall = app.calls.find((entry) => entry.name === 'get_rental_detail');
  assert.deepEqual(detailCall?.arguments, { provider: 'alfa', reference: 'A-31' });
  assert.equal(detailCall?.timeout, 180000);
  assert.match(root.textContent ?? '', /Detalhe do imóvel/);
});

test('preserves closed typed slug references when requesting Arthuso details', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  const typedReference = { kind: 'slug', value: 'apartamento-centro-123' };
  app.queue('list_rental_providers', catalogResult);
  app.queue('search_rentals', {
    structuredContent: {
      status: 'ok',
      providers: [{
        provider: 'arthuso',
        status: 'ok',
        native: {},
        display: [
          { reference: typedReference, title: 'Imóvel com referência tipada' },
          { reference: { kind: 'url', value: 'https://arthuso.example/apartamento-centro-123' }, title: 'Tipo inválido' },
          { reference: { kind: 'slug', value: '' }, title: 'Slug vazio' },
          { reference: { kind: 'slug', value: 'apartamento-centro-123', extra: true }, title: 'Campo extra' },
        ],
      }],
    },
  });
  const lifecycle = setupRentalApp(root, app, () => app.connect());
  await lifecycle.ready;
  root.querySelector<HTMLInputElement>('[data-provider-id="arthuso"] [data-provider-selection]')!.checked = true;
  root.querySelector<HTMLButtonElement>('[data-action="search"]')!.click();
  await flushUi();
  app.queue('get_rental_detail', { structuredContent: { provider: 'arthuso', status: 'ok', native: {}, display: { title: 'Detalhe Arthuso' } } });

  const detailButtons = root.querySelectorAll<HTMLButtonElement>('[data-provider-results="arthuso"] [data-action="detail"]');
  assert.equal(detailButtons.length, 1);
  detailButtons[0]!.click();
  await flushUi();

  const detailCall = app.calls.find((entry) => entry.name === 'get_rental_detail');
  assert.deepEqual(detailCall?.arguments, { provider: 'arthuso', reference: typedReference });
  assert.match(root.textContent ?? '', /Detalhe Arthuso/);
});

test('opens only validated HTTP(S) listing links through the MCP host', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  await startRentalSearch(root, app, [
    { reference: 'A-31', url: 'https://imoveis.example/a-31', title: 'Link seguro' },
    { reference: 'A-32', url: 'javascript:alert(1)', title: 'Link inválido' },
    { reference: 'A-33', url: 'https://user:pass@imoveis.example/a-33', title: 'Link com credenciais' },
    { reference: 'A-34', url: 'https://evil.example/a-34', title: 'Domínio inválido' },
    { reference: 'A-35', url: 'https://imoveis.example/search', title: 'Caminho inválido' },
  ]);

  const safeLink = Array.from(root.querySelectorAll<HTMLButtonElement>('[data-action="open-link"]')).find((button) => button.textContent === 'Abrir anúncio');
  assert.ok(safeLink);
  assert.equal(root.querySelectorAll('[data-action="open-link"]').length, 1);
  safeLink.click();

  assert.deepEqual(app.openedLinks, ['https://imoveis.example/a-31']);
});

test('rejects links to loopback and private network destinations', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  await startRentalSearch(root, app, [
    { reference: 'A-41', url: 'http://127.0.0.1/admin', title: 'Loopback' },
    { reference: 'A-42', url: 'https://localhost/private', title: 'Local host' },
    { reference: 'A-43', url: 'https://192.168.1.20/property', title: 'Private network' },
  ]);

  assert.equal(root.querySelectorAll('[data-action="open-link"]').length, 0);
});

test('automatically submits the Viva Real location suggestions const', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  app.queue('list_rental_providers', catalogResult);
  app.queue('get_rental_facets', { structuredContent: { provider: 'viva', kind: 'location_suggestions', status: 'ok', native: [] } });
  const lifecycle = setupRentalApp(root, app, () => app.connect());
  await lifecycle.ready;
  root.querySelector<HTMLButtonElement>('[data-provider-id="viva"] [data-action="facets"]')!.click();
  await flushUi();

  const facetCall = app.calls.find((entry) => entry.name === 'get_rental_facets');
  assert.deepEqual(facetCall?.arguments, { provider: 'viva', request: { selector: 'location_suggestions' } });
});

test('submits provider facet requests and labels the returned facet kind', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  app.queue('list_rental_providers', catalogResult);
  app.queue('get_rental_facets', { structuredContent: { provider: 'alfa', kind: 'catalog', status: 'ok', native: { cities: ['Timóteo', 'Ipatinga'] } } });
  const lifecycle = setupRentalApp(root, app, () => app.connect());
  await lifecycle.ready;
  const panel = root.querySelector<HTMLElement>('[data-provider-id="alfa"]')!;
  panel.querySelector<HTMLSelectElement>('select[name="selector"]')!.value = 'cities';
  panel.querySelector<HTMLButtonElement>('[data-action="facets"]')!.click();
  await flushUi();

  const facetCall = app.calls.find((entry) => entry.name === 'get_rental_facets');
  assert.deepEqual(facetCall?.arguments, { provider: 'alfa', request: { selector: 'cities' } });
  assert.match(root.textContent ?? '', /Catálogo/);
  assert.match(root.textContent ?? '', /Timóteo/);
});
