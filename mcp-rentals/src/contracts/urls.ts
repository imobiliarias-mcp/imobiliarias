import type { ProviderSpecification } from './specifications.js';

/** Validate source-specific public property links, not API/search/image URLs. */
export function validate_public_url(value: string, specification: ProviderSpecification): string {
  const parsed = new URL(value);
  if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('invalid_input');
  if (parsed.username || parsed.password || parsed.port || parsed.hash || /^https?:\/\/[^/?#]*:\d+/i.test(value)) throw new Error('invalid_input');
  if (!specification.public_hosts.includes(parsed.hostname)) throw new Error('invalid_input');
  if (has_traversal(value)) throw new Error('invalid_input');
  if (!new RegExp(specification.detail_path_pattern).test(parsed.pathname + parsed.search)) throw new Error('invalid_input');
  return value;
}
function has_traversal(value: string): boolean {
  let decoded = value;
  for (let count = 0; count < 4; count++) decoded = decodeURIComponent(decoded);
  return decoded.includes('\\') || /(?:\/|^)\.{1,2}(?:\/|[?#]|$)/.test(decoded) || /[\u0000- ]/.test(decoded);
}
