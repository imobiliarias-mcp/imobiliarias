import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/** Resolve the installed central project independently of the host working directory. */
export function project_root(): string {
  let directory = dirname(fileURLToPath(import.meta.url));
  while (!existsSync(join(directory, 'provider-specs'))) {
    const parent = dirname(directory);
    if (parent === directory) throw new Error('Central project not installed');
    directory = parent;
  }
  return directory;
}
