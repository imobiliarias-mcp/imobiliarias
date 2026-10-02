import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { z } from 'zod';
import { specifications, schema_validator } from '../src/contracts/specifications.js';
import { worker_response } from '../src/contracts/responses.js';
import { project_root } from '../src/paths.js';

const providers = specifications();
for (const provider of providers) {
  schema_validator(provider.filters);
  schema_validator(provider.reference);
  if (provider.facets) schema_validator(provider.facets);
}
const directory = join(project_root(), 'dist/contracts');
await mkdir(directory, {recursive: true});
await writeFile(join(directory, 'providers.json'), JSON.stringify({version: 1, providers, worker_response: z.toJSONSchema(worker_response)}, null, 2) + '\n');
