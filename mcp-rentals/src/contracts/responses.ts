import { z } from 'zod';

export const error_codes = z.enum(['invalid_input', 'unsupported_capability', 'not_installed', 'blocked', 'rate_limited', 'http_error', 'invalid_content', 'tls_error', 'timeout', 'cancelled', 'output_limit', 'invalid_output', 'worker_error', 'shutdown']);
export const safe_error = z.strictObject({code: error_codes, message: z.string().max(300)});
export const display_item = z.strictObject({reference: z.union([z.string().max(2048), z.record(z.string(), z.unknown())]).optional(), url: z.url().optional(), title: z.string().optional(), location: z.unknown().optional(), price: z.unknown().optional()});
export const worker_response = z.discriminatedUnion('status', [
  z.strictObject({version: z.literal(1), status: z.literal('ok'), native: z.unknown(), display: z.array(display_item)}),
  z.strictObject({version: z.literal(1), status: z.literal('error'), error: safe_error}),
]);
export const provider_entry = z.discriminatedUnion('status', [
  z.strictObject({provider: z.string(), status: z.literal('ok'), native: z.unknown(), display: z.array(display_item)}),
  z.strictObject({provider: z.string(), status: z.literal('error'), error: safe_error}),
]);
export const facets_output = z.discriminatedUnion('status', [
  provider_entry.options[0].extend({kind: z.enum(['catalog', 'location_suggestions'])}),
  provider_entry.options[1].extend({kind: z.enum(['catalog', 'location_suggestions'])}),
]);
export const search_output = z.strictObject({status: z.enum(['ok', 'partial', 'error']), providers: z.array(provider_entry)});
export type WorkerResponse = z.infer<typeof worker_response>;
export type ProviderEntry = z.infer<typeof provider_entry>;
