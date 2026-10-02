import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { z } from 'zod';
import { project_root } from '../paths.js';

export const provider_ids = ['alecorretoramg', 'arthusoimoveis', 'cabralporto', 'casalinhares', 'epifanioimoveis', 'helenaimoveis', 'imobiliariaportalmg', 'imobiliariavaleinvest', 'imovelweb', 'marcioimoveis', 'minascaixaimoveis', 'niltoncorretordeimoveis', 'novaimobiliaria', 'veraimobiliaria', 'vivareal'] as const;
export type ProviderId = typeof provider_ids[number];
const json_schema = z.record(z.string(), z.unknown());
const specification_schema = z.strictObject({id: z.enum(provider_ids), label: z.string(), filters: json_schema, reference: json_schema, facets: json_schema.nullable(), limitations: z.array(z.string()), public_hosts: z.array(z.string()).min(1), detail_path_pattern: z.string()});
export type ProviderSpecification = z.infer<typeof specification_schema>;

/** Load fixed trusted contracts; any missing or mismatched source spec fails startup. */
export function specifications(): ProviderSpecification[] {
  return provider_ids.map(load_specification);
}
function load_specification(id: ProviderId): ProviderSpecification {
  const path = join(project_root(), 'provider-specs', `${id}.json`);
  const specification = specification_schema.parse(JSON.parse(readFileSync(path, 'utf8')));
  if (specification.id !== id) throw new Error('Provider contract ID mismatch');
  return specification;
}
/** Derive Zod validators from the same exported schemas consumed by Python and UI. */
export function schema_validator(schema: Record<string, unknown>): z.ZodType {
  return z.fromJSONSchema(schema);
}
