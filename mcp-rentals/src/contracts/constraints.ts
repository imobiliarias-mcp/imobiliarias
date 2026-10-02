import type { SearchRequest } from './index.js';

/** Validate provider-only combinations that JSON Schema cannot express portably. */
export function validate_combinations(request: SearchRequest): void {
  if (request.provider !== 'vivareal') return;
  const filters = request.filters;
  if ('page' in filters && 'offset' in filters) throw new Error('invalid_input');
  const size = typeof filters.size === 'number' ? filters.size : 30;
  if (typeof filters.offset === 'number' && filters.offset % size !== 0) throw new Error('invalid_input');
}
