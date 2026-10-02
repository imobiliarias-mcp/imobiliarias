import { accessSync, constants, existsSync } from 'node:fs';
import { delimiter, join } from 'node:path';
import { specifications, type ProviderId } from '../contracts/specifications.js';
import { verify_installed_contracts } from '../contracts/build.js';
import type { Configuration } from '../configuration.js';
import type { WorkerCommand } from '../workers/process.js';
import { project_root } from '../paths.js';

/** Fixed registry mapping IDs to trusted source directories and interpreter paths. */
export class ProviderRegistry {
  constructor(private configuration: Configuration) { verify_installed_contracts(specifications()); }
  catalog() {
    return {providers: specifications().map(specification => ({...specification, capabilities: {search: true, detail: true, facets: specification.facets !== null}, installation: {available: this.available(specification.id)}}))};
  }
  command(provider: ProviderId): WorkerCommand {
    if (!this.available(provider)) throw new Error('not_installed');
    const directory = join(this.configuration.sources_root, provider);
    const root = project_root();
    const environment = {...process.env, PYTHONPATH: [join(root, 'python'), join(directory, 'src'), directory].join(delimiter), PYTHONDONTWRITEBYTECODE: '1', RENTAL_CONTRACTS: join(root, 'dist/contracts/providers.json')};
    return {python: this.interpreter(provider), args: ['-m', 'rental_bridge.worker'], directory, environment};
  }
  available(provider: ProviderId): boolean {
    if (!existsSync(join(this.configuration.sources_root, provider))) return false;
    try { accessSync(this.interpreter(provider), constants.X_OK); return true; }
    catch { return false; }
  }
  private interpreter(provider: ProviderId): string {
    if (this.configuration.environments_root) return join(this.configuration.environments_root, provider, 'bin/python');
    return join(this.configuration.sources_root, provider, '.venv/bin/python');
  }
}
