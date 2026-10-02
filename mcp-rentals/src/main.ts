import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { serveStdio } from '@modelcontextprotocol/server/stdio';
import { load_configuration } from './configuration.js';
import { ProviderRegistry } from './providers/registry.js';
import { WorkerExecutor } from './workers/executor.js';
import { WorkerLimiter } from './workers/limiter.js';
import { RentalService } from './application/service.js';
import { create_server } from './server.js';
import { start_local_http } from './http.js';
import { project_root } from './paths.js';

/** Start stdio by default; no model, public listener or global host config is required. */
async function main(): Promise<void> {
  load_local_environment();
  const configuration = load_configuration();
  const registry = new ProviderRegistry(configuration);
  if (process.argv.includes('--health')) { registry.catalog(); process.stdout.write('ok\n'); return; }
  const limiter = new WorkerLimiter(configuration.workers);
  const executor = new WorkerExecutor({timeout: configuration.worker_timeout, stdout: configuration.stdout, stderr: configuration.stderr, stdin: configuration.stdin});
  const shutdown = new AbortController();
  const service = new RentalService((provider, operation, arguments_, signal) => limiter.run(provider, signal, () => executor.run(registry.command(provider), {version: 1, provider, operation, arguments: arguments_}, AbortSignal.any([signal, shutdown.signal]))), {deadline: configuration.deadline, aggregate: configuration.aggregate});
  const factory = () => create_server(service, registry);
  const transport = await start_transport(factory, configuration.http_port, configuration.origin_port);
  const close = async () => { shutdown.abort(); limiter.close(); await transport.close(); };
  process.once('SIGTERM', () => void close()); process.once('SIGINT', () => void close());
  process.stdin.once('end', () => { if (!process.argv.includes('--http')) void close(); });
}
function load_local_environment(): void {
  const dotenv = join(project_root(), '.env');
  if (existsSync(dotenv)) process.loadEnvFile(dotenv);
}
async function start_transport(factory: Parameters<typeof serveStdio>[0], port: number, origin_port?: number) {
  if (!process.argv.includes('--http')) return serveStdio(factory, {legacy: 'serve', onerror: () => process.stderr.write('MCP transport error\n')});
  const bind = process.env.RENTAL_HTTP_BIND ?? '127.0.0.1';
  if (bind !== '127.0.0.1' && bind !== '0.0.0.0') throw new Error('Invalid local HTTP bind');
  return start_local_http(factory, port, bind, origin_port);
}
main().catch(() => { process.stderr.write('MCP rentals startup/execution failed; verify local configuration and build.\n'); process.exitCode = 1; });
