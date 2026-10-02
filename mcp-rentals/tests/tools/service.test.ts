import { test } from 'node:test';
import assert from 'node:assert/strict';
import { RentalService } from '../../src/application/service.js';

const success = {version: 1, status: 'ok', native: {listings: [], current_page: 1, total_found: null}, display: []} as const;
test('one invalid entry starts zero workers including valid origins', async () => {
  let launches = 0;
  const service = new RentalService(async () => { launches++; return success; });
  const result = await service.search({requests: [{provider: 'alecorretoramg', filters: {}}, {provider: 'imovelweb', filters: {minimum_price: 5}}]}, new AbortController().signal);
  assert.equal(result.isError, true); assert.equal(launches, 0);
});
test('partial results retain order and native counts without global totals', async () => {
  const service = new RentalService(async provider => {
    if (provider === 'imovelweb') throw new Error('blocked');
    return success;
  });
  const result = await service.search({requests: [{provider: 'imovelweb', filters: {}}, {provider: 'alecorretoramg', filters: {}}]}, new AbortController().signal);
  assert.equal(result.isError, false);
  assert.equal(result.structuredContent!.status, 'partial');
  assert.deepEqual(result.structuredContent!.providers.map((entry: any) => entry.provider), ['imovelweb', 'alecorretoramg']);
  assert.deepEqual((result.structuredContent!.providers[1] as any).native, success.native);
  assert.match(result.content[0]!.text, /imovelweb/);
});
test('all failures return isError and redact raw error secrets', async () => {
  const service = new RentalService(async () => { throw new Error('password=secret'); });
  const result = await service.search({requests: [{provider: 'alecorretoramg', filters: {}}]}, new AbortController().signal);
  assert.equal(result.isError, true);
  assert.equal(result.structuredContent!.status, 'error');
  assert.equal(JSON.stringify(result).includes('secret'), false);
});
test('detail and facets deadlines include queued work, not only process runtime', async () => {
  const service = new RentalService(async (_provider, _operation, _args, signal) => {
    await new Promise<void>(resolve => signal.addEventListener('abort', () => resolve(), {once: true}));
    return success;
  }, {deadline: 25, aggregate: 1000});
  const calls = [service.detail({provider: 'vivareal', reference: 'https://www.vivareal.com.br/imovel/apartamento-123/'}, new AbortController().signal), service.facets({provider: 'veraimobiliaria', request: {selector: 'cities'}}, new AbortController().signal)];
  const timeout = new Promise(resolve => setTimeout(() => resolve('hung'), 100));
  const result = await Promise.race([Promise.allSettled(calls), timeout]);
  assert.notEqual(result, 'hung');
});

test('aggregate limit bounds the complete text and structured MCP response', async () => {
  const service = new RentalService(async () => ({version: 1, status: 'ok', native: {}, display: [{title: 'x'.repeat(700)}]}), {deadline: 1000, aggregate: 1000});
  const result = await service.search({requests: [{provider: 'alecorretoramg', filters: {}}]}, new AbortController().signal);
  assert.ok(Buffer.byteLength(JSON.stringify(result)) <= 1000);
  assert.equal(result.isError, true);
  assert.match(result.content[0]!.text, /output_limit/);
});

test('individual detail and facet results share the complete MCP output budget', async () => {
  const service = new RentalService(async () => ({version: 1, status: 'ok', native: {body: 'x'.repeat(700)}, display: []}), {deadline: 1000, aggregate: 1000});
  const signal = new AbortController().signal;
  const results = [await service.detail({provider: 'vivareal', reference: 'https://www.vivareal.com.br/imovel/apartamento-123/'}, signal), await service.facets({provider: 'veraimobiliaria', request: {selector: 'cities'}}, signal)];
  for (const result of results) {
    assert.ok(Buffer.byteLength(JSON.stringify(result)) <= 1000);
    assert.equal(result.isError, true);
    assert.match(result.content[0]!.text, /output_limit/);
  }
});

test('whole call cancellation cannot become partial success', async () => {
  const controller = new AbortController();
  const service = new RentalService(async () => { controller.abort(); return success; });
  await assert.rejects(service.search({requests: [{provider: 'alecorretoramg', filters: {}}]}, controller.signal), /cancelled/);
});
