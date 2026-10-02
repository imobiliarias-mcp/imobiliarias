import type { McpServerFactory } from '@modelcontextprotocol/server';
import { serveStdio } from '@modelcontextprotocol/server/stdio';
import { RentalService, type WorkerRunner } from '../../src/application/service.js';
import { load_configuration } from '../../src/configuration.js';
import { project_root } from '../../src/paths.js';
import { ProviderRegistry } from '../../src/providers/registry.js';
import { create_server } from '../../src/server.js';

export function create_offline_factory(
  on_runner_event: (provider: string, operation: string, stage: 'started' | 'completed') => void = () => undefined,
): McpServerFactory {
  const configuration = load_configuration({...process.env, SOURCES_ROOT: project_root()});
  const registry = new ProviderRegistry(configuration);
  const service = new RentalService(create_offline_runner(on_runner_event));
  return () => create_server(service, registry);
}

function create_offline_runner(
  on_runner_event: (provider: string, operation: string, stage: 'started' | 'completed') => void,
): WorkerRunner {
  return async (provider, operation, arguments_, signal) => {
    on_runner_event(provider, operation, 'started');
    if (is_cancellation_request(provider, arguments_)) await wait_for_cancellation(signal);
    const response = provider === 'arthusoimoveis'
      ? failed_response()
      : successful_response(provider, operation, arguments_);
    on_runner_event(provider, operation, 'completed');
    return response;
  };
}

function is_cancellation_request(provider: string, arguments_: Record<string, unknown>): boolean {
  return provider === 'alecorretoramg' && arguments_.code === 'CANCEL';
}

function failed_response(): Awaited<ReturnType<WorkerRunner>> {
  return {
    version: 1,
    status: 'error',
    error: {code: 'worker_error', message: 'Offline fixture failure'},
  };
}

function successful_response(
  provider: string,
  operation: string,
  arguments_: Record<string, unknown>,
): Awaited<ReturnType<WorkerRunner>> {
  return {
    version: 1,
    status: 'ok',
    native: {provider, operation, arguments: arguments_},
    display: [{reference: 'offline-001', title: 'Offline rental'}],
  };
}

async function wait_for_cancellation(signal: AbortSignal): Promise<void> {
  if (signal.aborted) throw new Error('cancelled');
  await new Promise<void>((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new Error('cancelled')), {once: true});
  });
}

if (process.argv[2] === 'stdio') {
  const factory = create_offline_factory((provider, operation, stage) => {
    process.stderr.write(`E2E_RUNNER_EVENT ${provider} ${operation} ${stage}\n`);
  });
  serveStdio(factory, {legacy: 'serve'});
}
