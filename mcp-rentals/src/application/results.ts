import { provider_entry, search_output, type ProviderEntry } from '../contracts/responses.js';

/** Provide useful text, including public links, to hosts without MCP Apps. */
export function search_result(entries: ProviderEntry[]) {
  const successes = entries.filter(entry => entry.status === 'ok').length;
  const status = successes === entries.length ? 'ok' : successes === 0 ? 'error' : 'partial';
  const structuredContent = search_output.parse({status, providers: entries});
  return {isError: status === 'error', structuredContent, content: [{type: 'text' as const, text: entries.map(describe_entry).join('\n\n')}]};
}
export function single_result(entry: ProviderEntry, kind?: 'catalog' | 'location_suggestions') {
  const structuredContent = {...provider_entry.parse(entry), ...(kind ? {kind} : {})};
  return {isError: entry.status === 'error', structuredContent, content: [{type: 'text' as const, text: describe_entry(entry)}]};
}
export function invalid_result(code = 'invalid_input') {
  return {isError: true, content: [{type: 'text' as const, text: `${code}: Verifique os argumentos e o catálogo de capacidades.`}]};
}
function printable(value: unknown): string | undefined {
  if (value === undefined) return undefined;
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}
function describe_entry(entry: ProviderEntry): string {
  if (entry.status === 'error') return `${entry.provider}: ${entry.error.code} — ${entry.error.message}`;
  const listings = entry.display.map(item => [item.title ?? 'Imóvel', printable(item.reference), printable(item.location), printable(item.price), item.url].filter(value => value !== undefined).join('\n'));
  if (listings.length) return `${entry.provider}: ${listings.length} resultado(s) exibido(s).\n${listings.join('\n\n')}`;
  return `${entry.provider}: consulta concluída.\n${JSON.stringify(entry.native)}`;
}
