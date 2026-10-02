import type { ProviderEntry } from '../contracts/responses.js';
import { normalize_error } from './errors.js';
import { invalid_result, search_result, single_result } from './results.js';

/** Bound both useful text and structured content without truncating native JSON. */
export function budgeted_search_result(entries: ProviderEntry[], maximum: number) {
  const bounded = [...entries];
  let result = search_result(bounded);
  for (let index = bounded.length - 1; index >= 0 && byte_size(result) > maximum; index--) {
    const entry = bounded[index]!;
    if (entry.status === 'error') continue;
    bounded[index] = {provider: entry.provider, status: 'error', error: normalize_error(new Error('output_limit'))};
    result = search_result(bounded);
  }
  if (byte_size(result) > maximum) return invalid_result('output_limit');
  return result;
}
/** Apply the same total budget to a single detail or atomic facet response. */
export function budgeted_single_result(entry: ProviderEntry, maximum: number, kind?: 'catalog' | 'location_suggestions') {
  const result = single_result(entry, kind);
  if (byte_size(result) <= maximum) return result;
  const error: ProviderEntry = {provider: entry.provider, status: 'error', error: normalize_error(new Error('output_limit'))};
  const failure = single_result(error, kind);
  if (byte_size(failure) > maximum) return invalid_result('output_limit');
  return failure;
}
function byte_size(value: unknown): number {
  return Buffer.byteLength(JSON.stringify(value));
}
