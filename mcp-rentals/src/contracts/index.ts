import { z } from 'zod';
import { provider_ids, specifications, schema_validator, type ProviderId } from './specifications.js';
import { validate_public_url } from './urls.js';
import { validate_combinations } from './constraints.js';
export { provider_ids };

export const search_input = z.strictObject({requests: z.array(z.strictObject({provider: z.enum(provider_ids), filters: z.record(z.string(), z.unknown())})).min(1).max(15)});
export const detail_input = z.strictObject({provider: z.enum(provider_ids), reference: z.unknown()});
export const facets_input = z.strictObject({provider: z.enum(provider_ids), request: z.record(z.string(), z.unknown())});
export interface SearchRequest {provider: ProviderId; filters: Record<string, unknown>}

/** Validate the complete federated transaction before any worker is enqueued. */
export function validate_search(value: unknown): {requests: SearchRequest[]} {
  const parsed = search_input.parse(value);
  const seen = new Set<string>();
  for (const request of parsed.requests) validate_search_entry(request, seen);
  return parsed;
}
function validate_search_entry(request: SearchRequest, seen: Set<string>): void {
  if (seen.has(request.provider)) throw new Error('invalid_input');
  seen.add(request.provider);
  const specification = specifications().find(item => item.id === request.provider)!;
  schema_validator(specification.filters).parse(request.filters);
  if (Buffer.byteLength(JSON.stringify({version: 1, provider: request.provider, operation: 'search', arguments: request.filters})) > 65536) throw new Error('invalid_input');
  reject_empty_text(request.filters);
  validate_ranges(request.filters);
  validate_combinations(request);
}
/** Validate capability selector requirements without supplying an implicit city. */
export function validate_facets(value: unknown) {
  const parsed = facets_input.parse(value);
  const specification = specifications().find(item => item.id === parsed.provider)!;
  if (!specification.facets) throw new Error('unsupported_capability');
  schema_validator(specification.facets).parse(parsed.request);
  reject_empty_text(parsed.request);
  return parsed;
}
/** Preserve each source's ID/code/slug/URL semantics and forbid arbitrary URL fetches. */
export function validate_detail(value: unknown) {
  const parsed = detail_input.parse(value);
  const specification = specifications().find(item => item.id === parsed.provider)!;
  schema_validator(specification.reference).parse(parsed.reference);
  reject_empty_text(parsed.reference);
  if (typeof parsed.reference === 'string' && /^https?:\/\//i.test(parsed.reference)) validate_public_url(parsed.reference, specification);
  return parsed;
}
function reject_empty_text(value: unknown): void {
  if (typeof value === 'string' && (!value.trim() || value.length > 2048)) throw new Error('invalid_input');
  if (Array.isArray(value)) { value.forEach(reject_empty_text); return; }
  if (value && typeof value === 'object') Object.values(value).forEach(reject_empty_text);
}
function validate_ranges(filters: Record<string, unknown>): void {
  const pairs = [['min_price', 'max_price'], ['minimum_price', 'maximum_price'], ['min_area', 'max_area'], ['minimum_area', 'maximum_area']];
  for (const [minimum, maximum] of pairs) validate_range(filters[minimum!], filters[maximum!]);
}
function validate_range(minimum: unknown, maximum: unknown): void {
  if (typeof minimum === 'number' && typeof maximum === 'number' && maximum > 0 && minimum > maximum) throw new Error('invalid_input');
}
