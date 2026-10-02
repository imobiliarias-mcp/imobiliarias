import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { project_root } from '../paths.js';

/** Reject stale cross-language provider schemas before serving any MCP tools. */
export function verify_contract_build(exported: unknown, providers: unknown): void {
  if (!exported || typeof exported !== 'object') throw new Error('Missing exported contracts; run build');
  const document = exported as {version?: number; providers?: unknown};
  if (document.version !== 1 || JSON.stringify(document.providers) !== JSON.stringify(providers)) throw new Error('Stale exported contracts; run build');
}
/** Validate only installed build artifacts, never temporary development schemas. */
export function verify_installed_contracts(providers: unknown): void {
  const path = join(project_root(), 'dist/contracts/providers.json');
  verify_contract_build(JSON.parse(readFileSync(path, 'utf8')), providers);
}
