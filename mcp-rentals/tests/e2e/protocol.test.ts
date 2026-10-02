import assert from 'node:assert/strict';
import { after, before, describe, test } from 'node:test';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  Client,
  StreamableHTTPClientTransport,
  type Transport,
} from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';
import { start_local_http } from '../../src/http.js';
import { project_root } from '../../src/paths.js';
import { create_offline_factory } from './offline-server.js';

const test_directory = dirname(fileURLToPath(import.meta.url));
const offline_server_path = join(test_directory, 'offline-server.ts');
const expected_tool_names = [
  'get_rental_detail',
  'get_rental_facets',
  'list_rental_providers',
  'search_rentals',
];
const expected_provider_ids = [
  'alecorretoramg',
  'arthusoimoveis',
  'cabralporto',
  'casalinhares',
  'epifanioimoveis',
  'helenaimoveis',
  'imobiliariaportalmg',
  'imobiliariavaleinvest',
  'imovelweb',
  'marcioimoveis',
  'minascaixaimoveis',
  'niltoncorretordeimoveis',
  'novaimobiliaria',
  'veraimobiliaria',
  'vivareal',
];
const protocol_eras = [
  {name: 'legacy initialize', client_options: {versionNegotiation: {mode: 'legacy'}}},
  {name: '2026-07-28 discovery', client_options: {versionNegotiation: {mode: {pin: '2026-07-28'}}}},
] as const;

type TransportMode = 'stdio' | 'http';
type OfflineHarness = {
  transport: Transport;
  runner_calls: string[];
  runner_events: string[];
  wait_for_runner_event: (event: string, from_index: number) => Promise<void>;
  close: () => Promise<void>;
};

for (const transport_mode of ['stdio', 'http'] as const) {
  for (const era of protocol_eras) {
    describe(`${transport_mode} with ${era.name}`, () => {
      let harness: OfflineHarness | undefined;
      let client: Client | undefined;

      before(async () => {
        harness = await open_offline_harness(transport_mode);
        client = new Client({name: 'rental-protocol-test', version: '1.0.0'}, era.client_options);
        await client.connect(harness.transport, {timeout: 10_000});
      });

      after(async () => {
        try {
          await client?.close();
        } finally {
          await harness?.close();
        }
      });

      test('exposes the four rental tools after protocol negotiation', async () => {
        const connected_client = require_client(client);
        const result = await connected_client.listTools();
        const tool_names = result.tools.map(tool => tool.name).sort();

        assert.deepEqual(tool_names, expected_tool_names);
      });

      test('loads all fifteen providers from the real local registry', async () => {
        const result = await require_client(client).callTool({
          name: 'list_rental_providers',
          arguments: {},
        });
        const catalog = as_record(result.structuredContent);
        const providers = as_array(catalog.providers);
        const provider_ids = providers.map(provider => as_record(provider).id).sort();

        assert.equal(providers.length, 15);
        assert.deepEqual(provider_ids, expected_provider_ids);
      });

      test('returns version-one native and display data for a successful search', async () => {
        const result = await require_client(client).callTool({
          name: 'search_rentals',
          arguments: {requests: [{provider: 'alecorretoramg', filters: {}}]},
        });
        const search = as_record(result.structuredContent);
        const providers = as_array(search.providers);
        const provider = as_record(providers[0]);

        assert.equal(result.isError, false);
        assert.equal(search.status, 'ok');
        assert.equal(provider.status, 'ok');
        assert.deepEqual(provider.native, {
          provider: 'alecorretoramg',
          operation: 'search',
          arguments: {},
        });
        assert.equal(as_record(as_array(provider.display)[0]).title, 'Offline rental');
      });

      test('reports requested search progress without disrupting the result', async () => {
        const progress_notifications: unknown[] = [];
        const result = await require_client(client).callTool({
          name: 'search_rentals',
          arguments: {requests: [{provider: 'alecorretoramg', filters: {}}]},
        }, {onprogress: progress => progress_notifications.push(progress), timeout: 10_000});
        assert.equal(result.isError, false, JSON.stringify(result));
        assert.ok(result.structuredContent !== undefined, JSON.stringify(result));
        const search = as_record(result.structuredContent);
        const notification = as_record(progress_notifications[0]);

        assert.equal(search.status, 'ok');
        assert.equal(progress_notifications.length, 1);
        assert.equal(notification.progress, 1);
        assert.equal(notification.total, 1);
      });

      test('returns partial status when one provider fails', async () => {
        const result = await require_client(client).callTool({
          name: 'search_rentals',
          arguments: {
            requests: [
              {provider: 'alecorretoramg', filters: {}},
              {provider: 'arthusoimoveis', filters: {}},
            ],
          },
        });
        const search = as_record(result.structuredContent);
        const providers = as_array(search.providers);

        assert.equal(result.isError, false);
        assert.equal(search.status, 'partial');
        assert.equal(as_record(providers[0]).status, 'ok');
        assert.equal(as_record(providers[1]).status, 'error');
        assert.equal(as_record(as_record(providers[1]).error).code, 'worker_error');
      });

      test('marks a search with only failed providers as an error', async () => {
        const result = await require_client(client).callTool({
          name: 'search_rentals',
          arguments: {requests: [{provider: 'arthusoimoveis', filters: {}}]},
        });
        const search = as_record(result.structuredContent);
        const provider = as_record(as_array(search.providers)[0]);

        assert.equal(result.isError, true);
        assert.equal(search.status, 'error');
        assert.equal(provider.status, 'error');
        assert.equal(as_record(provider.error).code, 'worker_error');
      });

      test('rejects an invalid filter before invoking any worker', async () => {
        const runner_calls_before = require_harness(harness).runner_calls.length;
        const result = await require_client(client).callTool({
          name: 'search_rentals',
          arguments: {
            requests: [{provider: 'alecorretoramg', filters: {bedrooms: -1}}],
          },
        });

        assert.equal(result.isError, true);
        assert.equal(require_harness(harness).runner_calls.length, runner_calls_before);
      });

      test('reads the bundled app with empty resource, frame, and connect CSP lists', async () => {
        const result = await require_client(client).readResource({uri: 'ui://rentals/search.html'});
        const content = as_record(result.contents[0]);
        const metadata = as_record(content._meta);
        const ui = as_record(metadata.ui);
        const csp = as_record(ui.csp);

        assert.match(String(content.text), /<html/i);
        assert.deepEqual(csp.connectDomains, []);
        assert.deepEqual(csp.resourceDomains, []);
        assert.deepEqual(csp.frameDomains, []);
      });

      test('cancels an in-flight mixed search without returning partial success', async () => {
        const connected_client = require_client(client);
        const connected_harness = require_harness(harness);
        const controller = new AbortController();
        const first_runner_event = connected_harness.runner_events.length;
        const pending_search = connected_client.callTool({
          name: 'search_rentals',
          arguments: {
            requests: [
              {provider: 'alecorretoramg', filters: {code: 'CANCEL'}},
              {provider: 'helenaimoveis', filters: {}},
            ],
          },
        }, {signal: controller.signal, timeout: 10_000}).then(
          result => ({result}),
          error => ({error}),
        );

        await Promise.all([
          connected_harness.wait_for_runner_event('alecorretoramg:search:started', first_runner_event),
          connected_harness.wait_for_runner_event('helenaimoveis:search:completed', first_runner_event),
        ]);
        controller.abort();
        const outcome = await pending_search;
        assert.ok('error' in outcome && is_cancellation_error(outcome.error));
      });
    });
  }
}

async function open_offline_harness(mode: TransportMode): Promise<OfflineHarness> {
  const tracker = create_runner_tracker();
  if (mode === 'http') return open_http_harness(tracker);
  return open_stdio_harness(tracker);
}

async function open_http_harness(tracker: RunnerTracker): Promise<OfflineHarness> {
  const http = await start_local_http(create_offline_factory((provider, operation, stage) => {
    tracker.record(`${provider}:${operation}:${stage}`);
  }), 0);
  return {
    transport: new StreamableHTTPClientTransport(new URL(`${http.url}/mcp`)),
    runner_calls: tracker.calls,
    runner_events: tracker.events,
    wait_for_runner_event: tracker.wait_for,
    close: http.close,
  };
}

async function open_stdio_harness(tracker: RunnerTracker): Promise<OfflineHarness> {
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: ['--import', 'tsx', offline_server_path, 'stdio'],
    cwd: project_root(),
    env: {PATH: process.env.PATH ?? '', SOURCES_ROOT: project_root()},
    stderr: 'pipe',
  });
  let stderr_buffer = '';
  transport.stderr?.on('data', chunk => {
    stderr_buffer += chunk.toString();
    const lines = stderr_buffer.split(/\r?\n/);
    stderr_buffer = lines.pop() ?? '';
    for (const line of lines) collect_runner_events(line, tracker.record);
  });
  return {
    transport,
    runner_calls: tracker.calls,
    runner_events: tracker.events,
    wait_for_runner_event: tracker.wait_for,
    close: () => transport.close(),
  };
}

type RunnerTracker = {
  calls: string[];
  events: string[];
  record: (event: string) => void;
  wait_for: (event: string, from_index: number) => Promise<void>;
};

function create_runner_tracker(): RunnerTracker {
  const calls: string[] = [];
  const events: string[] = [];
  const waiting: {event: string; from_index: number; resolve: () => void}[] = [];
  return {
    calls,
    events,
    record(event) {
      events.push(event);
      if (event.endsWith(':started')) calls.push(event.slice(0, -':started'.length));
      for (const item of [...waiting]) {
        if (events.slice(item.from_index).includes(item.event)) {
          item.resolve();
          waiting.splice(waiting.indexOf(item), 1);
        }
      }
    },
    wait_for(event, from_index) {
      if (events.slice(from_index).includes(event)) return Promise.resolve();
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error(`No runner event observed for ${event}`)), 5_000);
        const resolve_and_clear_timeout = () => {
          clearTimeout(timeout);
          resolve();
        };
        waiting.push({event, from_index, resolve: resolve_and_clear_timeout});
      });
    },
  };
}

function collect_runner_events(line: string, record: (event: string) => void): void {
  const match = /^E2E_RUNNER_EVENT ([a-z]+) ([a-z]+) (started|completed)$/.exec(line);
  if (match) record(`${match[1]}:${match[2]}:${match[3]}`);
}

function require_client(client: Client | undefined): Client {
  assert.ok(client, 'The MCP client should be connected before each protocol assertion');
  return client;
}

function require_harness(harness: OfflineHarness | undefined): OfflineHarness {
  assert.ok(harness, 'The offline transport should be running before each protocol assertion');
  return harness;
}

function as_record(value: unknown): Record<string, unknown> {
  assert.ok(value !== null && typeof value === 'object' && !Array.isArray(value));
  return value as Record<string, unknown>;
}

function as_array(value: unknown): unknown[] {
  assert.ok(Array.isArray(value));
  return value;
}

function is_cancellation_error(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  return /abort|cancel/i.test(`${error.name} ${error.message}`);
}
