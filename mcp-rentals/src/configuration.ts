import { existsSync, statSync } from 'node:fs';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { z } from 'zod';
import { project_root } from './paths.js';

const configuration_schema = z.strictObject({sources_root: z.string(), environments_root: z.string().optional(), workers: z.number().int().min(1).max(15), worker_timeout: z.number().int().min(1).max(180000), deadline: z.number().int().min(1).max(600000), stdout: z.number().int().min(1024).max(8 * 1024 * 1024), stderr: z.number().int().min(1024).max(65536), stdin: z.number().int().min(1024).max(65536), aggregate: z.number().int().min(1024).max(8 * 1024 * 1024), http_port: z.number().int().min(1024).max(65535), origin_port: z.number().int().min(1024).max(65535).optional()});
export type Configuration = z.infer<typeof configuration_schema>;

/** Load trusted local settings and reject invalid paths/limits before serving MCP. */
export function load_configuration(environment = process.env): Configuration {
  const configuration = configuration_schema.parse({
    sources_root: environment.SOURCES_ROOT ?? dirname(project_root()), environments_root: environment.PYTHON_ENVIRONMENTS_ROOT,
    workers: number_setting(environment, 'RENTAL_WORKERS', 3), worker_timeout: number_setting(environment, 'RENTAL_WORKER_TIMEOUT_MS', 30000), deadline: number_setting(environment, 'RENTAL_DEADLINE_MS', 180000),
    stdout: number_setting(environment, 'RENTAL_STDOUT_BYTES', 1024 * 1024), stderr: 65536, stdin: 65536, aggregate: 8 * 1024 * 1024, http_port: number_setting(environment, 'RENTAL_HTTP_PORT', 3001), origin_port: environment.RENTAL_HTTP_ORIGIN_PORT === undefined ? undefined : number_setting(environment, 'RENTAL_HTTP_ORIGIN_PORT', 3001),
  });
  validate_directory(configuration.sources_root);
  if (configuration.environments_root) validate_directory(configuration.environments_root);
  return configuration;
}
function number_setting(environment: NodeJS.ProcessEnv, name: string, fallback: number): number {
  if (environment[name] === undefined) return fallback;
  if (!environment[name]?.trim()) throw new Error('Invalid numeric configuration');
  return Number(environment[name]);
}
function validate_directory(directory: string): void {
  if (!isAbsolute(directory) || !existsSync(directory) || !statSync(directory).isDirectory()) throw new Error('Invalid source/environment directory');
  if (resolve(directory) === join('/', '')) throw new Error('Root directory cannot be a source');
}
