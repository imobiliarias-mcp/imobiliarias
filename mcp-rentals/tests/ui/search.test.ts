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

async function startSearch(root: HTMLElement, app: FakeRentalApp): Promise<void> {
  app.queue('list_rental_providers', catalogResult);
  const lifecycle = setupRentalApp(root, app, () => app.connect());
  await lifecycle.ready;
}

async function flushUi(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

test('submits separate schema-closed filters for every selected provider', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  await startSearch(root, app);
  const alfa = root.querySelector<HTMLElement>('[data-provider-id="alfa"]')!;
  const beta = root.querySelector<HTMLElement>('[data-provider-id="beta"]')!;
  alfa.querySelector<HTMLInputElement>('[data-provider-selection]')!.checked = true;
  beta.querySelector<HTMLInputElement>('[data-provider-selection]')!.checked = true;
  alfa.querySelector<HTMLInputElement>('input[name="city"]')!.value = 'Timóteo';
  alfa.querySelector<HTMLInputElement>('input[name="bedrooms"]')!.value = '2';
  beta.querySelector<HTMLInputElement>('input[name="city"]')!.value = 'Ipatinga';
  app.queue('search_rentals', {
    structuredContent: {
      status: 'ok',
      providers: [
        { provider: 'alfa', status: 'ok', native: { current_page: 1, max_pages: 2 }, display: [{ reference: 'A-31', url: 'https://imoveis.example/a-31', title: '<img src=x onerror=alert(1)>', location: 'Centro', price: 1450 }] },
        { provider: 'beta', status: 'ok', native: {}, display: [] },
      ],
    },
  });

  root.querySelector<HTMLButtonElement>('[data-action="search"]')!.click();
  await flushUi();

  const call = app.calls.find((entry) => entry.name === 'search_rentals');
  assert.deepEqual(call?.arguments, { requests: [
    { provider: 'alfa', filters: { city: 'Timóteo', bedrooms: 2 } },
    { provider: 'beta', filters: { city: 'Ipatinga' } },
  ] });
  assert.equal(call?.timeout, 180000);
  assert.equal(root.querySelectorAll('img').length, 0);
  assert.match(root.querySelector('[data-provider-results="alfa"]')?.textContent ?? '', /<img src=x onerror=alert\(1\)>/);
  assert.match(root.querySelector('[data-provider-results="beta"]')?.textContent ?? '', /Nenhum imóvel encontrado/);
  assert.equal(root.querySelectorAll('[data-action="next-page"]').length, 1);
  assert.doesNotMatch(root.textContent ?? '', /Total geral|preço médio|deduplicad/i);
});

test('shows native pagination only when the response and provider schema both support it', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  await startSearch(root, app);
  root.querySelector<HTMLInputElement>('[data-provider-id="alfa"] [data-provider-selection]')!.checked = true;
  root.querySelector<HTMLInputElement>('[data-provider-id="beta"] [data-provider-selection]')!.checked = true;
  app.queue('search_rentals', {
    structuredContent: {
      status: 'partial',
      providers: [
        { provider: 'alfa', status: 'ok', native: { current_page: 1, max_pages: 3 }, display: [] },
        { provider: 'beta', status: 'ok', native: { current_page: 1, max_pages: 3 }, display: [] },
      ],
    },
  });

  root.querySelector<HTMLButtonElement>('[data-action="search"]')!.click();
  await flushUi();

  const nextPage = root.querySelector<HTMLButtonElement>('[data-provider-results="alfa"] [data-action="next-page"]');
  assert.ok(nextPage);
  assert.equal(root.querySelector('[data-provider-results="beta"] [data-action="next-page"]'), null);
  assert.equal(root.querySelector('[data-provider-results="alfa"] [data-action="previous-page"]')?.hasAttribute('disabled'), true);
});

test('requests the selected provider next page using its native page field', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  await startSearch(root, app);
  root.querySelector<HTMLInputElement>('[data-provider-id="alfa"] [data-provider-selection]')!.checked = true;
  app.queue('search_rentals',
    { structuredContent: { status: 'ok', providers: [{ provider: 'alfa', status: 'ok', native: { current_page: 1, max_pages: 3 }, display: [] }] } },
    { structuredContent: { status: 'ok', providers: [{ provider: 'alfa', status: 'ok', native: { current_page: 2, max_pages: 3 }, display: [] }] } },
  );
  const search = root.querySelector<HTMLButtonElement>('[data-action="search"]')!;
  search.click();
  await flushUi();
  root.querySelector<HTMLButtonElement>('[data-provider-results="alfa"] [data-action="next-page"]')!.click();
  await flushUi();

  const pageRequest = app.calls.filter((call) => call.name === 'search_rentals')[1];
  assert.deepEqual(pageRequest?.arguments, { requests: [{ provider: 'alfa', filters: { page_number: 2 } }] });
  assert.equal(pageRequest?.timeout, 180000);
});

test('ignores an older search result after a newer request replaces it', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  await startSearch(root, app);
  root.querySelector<HTMLInputElement>('[data-provider-id="alfa"] [data-provider-selection]')!.checked = true;
  let resolveOlder!: (value: unknown) => void;
  app.queue('search_rentals', new Promise((resolve) => { resolveOlder = resolve; }), {
    structuredContent: { status: 'ok', providers: [{ provider: 'alfa', status: 'ok', native: {}, display: [{ title: 'Consulta nova' }] }] },
  });

  const button = root.querySelector<HTMLButtonElement>('[data-action="search"]')!;
  button.click();
  button.click();
  await flushUi();
  resolveOlder({ structuredContent: { status: 'ok', providers: [{ provider: 'alfa', status: 'ok', native: {}, display: [{ title: 'Consulta antiga' }] }] } });
  await flushUi();

  assert.match(root.textContent ?? '', /Consulta nova/);
  assert.doesNotMatch(root.textContent ?? '', /Consulta antiga/);
});

test('preserves prior search results when display items or error fields are malformed', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  await startSearch(root, app);
  root.querySelector<HTMLInputElement>('[data-provider-id="alfa"] [data-provider-selection]')!.checked = true;
  app.queue('search_rentals',
    { structuredContent: { status: 'ok', providers: [{ provider: 'alfa', status: 'ok', native: {}, display: [{ title: 'Existing result' }] }] } },
    { structuredContent: { status: 'ok', providers: [{ provider: 'alfa', status: 'ok', native: {}, display: [null] }] } },
    { structuredContent: { status: 'partial', providers: [{ provider: 'alfa', status: 'error', error: { code: 'timeout', message: 99 } }] } },
  );
  const search = root.querySelector<HTMLButtonElement>('[data-action="search"]')!;
  search.click();
  await flushUi();
  search.click();
  await flushUi();
  assert.match(root.textContent ?? '', /Existing result/);
  search.click();
  await flushUi();

  assert.match(root.textContent ?? '', /Existing result/);
  assert.doesNotMatch(root.textContent ?? '', /Nenhum imóvel encontrado/);
});

test('renders provider error codes in Portuguese without exposing raw error messages', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  await startSearch(root, app);
  root.querySelector<HTMLInputElement>('[data-provider-id="alfa"] [data-provider-selection]')!.checked = true;
  app.queue('search_rentals', {
    structuredContent: {
      status: 'partial',
      providers: [{ provider: 'alfa', status: 'error', error: { code: 'timeout', message: '/private/path?token=secret' } }],
    },
  });

  root.querySelector<HTMLButtonElement>('[data-action="search"]')!.click();
  await flushUi();

  assert.match(root.querySelector('[role="status"]')?.textContent ?? '', /resultados parciais/);
  assert.match(root.querySelector('[data-provider-results="alfa"]')?.textContent ?? '', /tempo limite/);
  assert.doesNotMatch(root.textContent ?? '', /private\/path|secret/);
});

test('cancels active requests and gives a localized status', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  await startSearch(root, app);
  root.querySelector<HTMLInputElement>('[data-provider-id="alfa"] [data-provider-selection]')!.checked = true;
  app.queue('search_rentals', new Promise(() => undefined));

  root.querySelector<HTMLButtonElement>('[data-action="search"]')!.click();
  app.notify('toolinput', { arguments: { requests: [{ provider: 'alfa', filters: {} }] } });
  app.notify('toolcancelled', { reason: 'user action' });

  assert.equal(app.calls.at(-1)?.signal?.aborted, true);
  assert.match(root.querySelector('[role="status"]')?.textContent ?? '', /cancelad/i);
});
