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

function statusText(root: HTMLElement): string {
  return root.querySelector('[role="status"]')?.textContent ?? '';
}

test('registers host handlers before connect and loads provider schemas afterward', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  app.queue('list_rental_providers', catalogResult);
  let handlersAtConnect = 0;
  const connect = app.connect.bind(app);
  app.connect = async () => {
    handlersAtConnect = Array.from(app.listeners.values()).reduce((count, listeners) => count + listeners.size, 0);
    await connect();
  };

  const lifecycle = setupRentalApp(root, app, () => app.connect());
  await lifecycle.ready;

  assert.ok(handlersAtConnect >= 4);
  assert.equal(app.connectCount, 1);
  assert.equal(app.calls[0]?.name, 'list_rental_providers');
  assert.equal(root.querySelector('[data-provider-id="alfa"] h2')?.textContent, 'Imobiliária Alfa');
  assert.equal(root.querySelector('[role="status"]')?.getAttribute('aria-live'), 'polite');
});

test('keeps newer UI search results when an obsolete host result arrives', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  app.queue('list_rental_providers', catalogResult);
  app.queue('search_rentals', { structuredContent: { status: 'ok', providers: [{ provider: 'alfa', status: 'ok', native: {}, display: [{ title: 'Nova UI' }] }] } });
  await setupRentalApp(root, app, () => app.connect()).ready;
  app.notify('toolinput', { arguments: { requests: [{ provider: 'alfa', filters: {} }] } });
  root.querySelector<HTMLInputElement>('[data-provider-selection="alfa"]')!.checked = true;
  root.querySelector<HTMLButtonElement>('[data-action="search"]')!.click();
  await new Promise((resolve) => setTimeout(resolve, 0));
  app.notify('toolresult', { structuredContent: { status: 'ok', providers: [{ provider: 'alfa', status: 'ok', native: {}, display: [{ title: 'Antigo host' }] }] } });
  assert.match(root.textContent ?? '', /Nova UI/);
  assert.doesNotMatch(root.textContent ?? '', /Antigo host/);
});

test('ignores stale host cancellation while a newer UI search is pending', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  app.queue('list_rental_providers', catalogResult);
  let resolveSearch!: (value: unknown) => void;
  app.queue('search_rentals', new Promise((resolve) => { resolveSearch = resolve; }));
  await setupRentalApp(root, app, () => app.connect()).ready;
  root.querySelector<HTMLInputElement>('[data-provider-selection="alfa"]')!.checked = true;
  root.querySelector<HTMLButtonElement>('[data-action="search"]')!.click();
  const request = app.calls.find((call) => call.name === 'search_rentals');
  app.notify('toolcancelled', { reason: 'obsolete host request' });
  assert.equal(request?.signal?.aborted, false);
  resolveSearch({ structuredContent: { status: 'ok', providers: [{ provider: 'alfa', status: 'ok', native: {}, display: [{ title: 'Ainda atual' }] }] } });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.match(root.textContent ?? '', /Ainda atual/);
});

test('applies host theme and reflects host tool input and result notifications', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  app.queue('list_rental_providers', catalogResult);
  const lifecycle = setupRentalApp(root, app, () => app.connect());
  await lifecycle.ready;

  app.notify('hostcontextchanged', { theme: 'dark' });
  app.notify('toolinput', { arguments: { requests: [{ provider: 'alfa', filters: { city: 'Coronel Fabriciano' } }] } });
  assert.equal(root.ownerDocument.documentElement.dataset.theme, 'dark');
  assert.equal(root.querySelector<HTMLInputElement>('[data-provider-id="alfa"] input[name="city"]')?.value, 'Coronel Fabriciano');

  app.notify('toolresult', { structuredContent: { status: 'ok', providers: [{ provider: 'alfa', status: 'ok', native: {}, display: [{ title: 'Resultado recebido' }] }] } });
  assert.match(root.textContent ?? '', /Resultado recebido/);
});

test('ignores malformed host search results without clearing prior valid results', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  app.queue('list_rental_providers', catalogResult);
  const lifecycle = setupRentalApp(root, app, () => app.connect());
  await lifecycle.ready;
  app.notify('toolinput', { arguments: { requests: [{ provider: 'alfa', filters: {} }] } });
  app.notify('toolresult', { structuredContent: { status: 'ok', providers: [{ provider: 'alfa', status: 'ok', native: {}, display: [{ title: 'Resultado anterior' }] }] } });

  app.notify('toolinput', { arguments: { requests: [{ provider: 'alfa', filters: {} }] } });
  assert.doesNotThrow(() => app.notify('toolresult', {
    structuredContent: { status: 'ok', providers: [{ provider: 'alfa', status: 'ok', native: {}, display: [null] }] },
  }));
  assert.doesNotThrow(() => app.notify('toolresult', {
    structuredContent: { status: 'partial', providers: [{ provider: 'alfa', status: 'error', error: { code: 'timeout', message: 5 } }] },
  }));

  assert.match(root.textContent ?? '', /Resultado anterior/);
});

test('fills nested filter controls from complete host tool input', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  app.queue('list_rental_providers', catalogResult);
  const lifecycle = setupRentalApp(root, app, () => app.connect());
  await lifecycle.ready;

  app.notify('toolinput', { arguments: { requests: [{ provider: 'nested', filters: { location: { city: 'Ipatinga' } } }] } });

  assert.equal(root.querySelector<HTMLInputElement>('[data-provider-id="nested"] input[name="location.city"]')?.value, 'Ipatinga');
  assert.equal(root.querySelector<HTMLInputElement>('[data-provider-id="nested"] [data-provider-selection]')?.checked, true);
});

test('renders provider catalog errors in Portuguese and tears down all host subscriptions', async () => {
  const root = createRoot();
  const app = new FakeRentalApp();
  app.queue('list_rental_providers', { isError: true });
  const lifecycle = setupRentalApp(root, app, () => app.connect());
  await lifecycle.ready;

  assert.match(statusText(root), /Não foi possível carregar/);
  assert.doesNotMatch(statusText(root), /undefined|Error|failed/i);
  app.teardown?.();
  assert.equal(Array.from(app.listeners.values()).reduce((count, listeners) => count + listeners.size, 0), 0);
  lifecycle.destroy();
});
