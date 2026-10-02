import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { McpServer, type ServerContext } from '@modelcontextprotocol/server';
import { registerAppTool, registerAppResource, RESOURCE_MIME_TYPE } from '@modelcontextprotocol/ext-apps/server';
import { z } from 'zod';
import { search_input, detail_input, facets_input } from './contracts/index.js';
import { provider_entry, search_output, facets_output } from './contracts/responses.js';
import type { RentalService } from './application/service.js';
import type { ProviderRegistry } from './providers/registry.js';
import { project_root } from './paths.js';

const resource_uri = 'ui://rentals/search.html';
const annotations = {readOnlyHint: true, destructiveHint: false, openWorldHint: true, idempotentHint: true};
const catalog_output = z.strictObject({providers: z.array(z.record(z.string(), z.unknown()))});

/** Create identical registrations for modern and legacy SDK-controlled transports. */
export function create_server(service: RentalService, registry: ProviderRegistry): McpServer {
  const server = new McpServer({name: 'mcp-rentals', version: '0.1.0'});
  server.registerTool('list_rental_providers', {description: 'Lista 15 origens, filtros, referências, capacidades e instalação local; não verifica saúde dos sites.', inputSchema: z.strictObject({}), outputSchema: catalog_output, annotations}, async () => ({content: [{type: 'text', text: JSON.stringify(registry.catalog())}], structuredContent: registry.catalog()}));
  registerAppTool(server, 'search_rentals', {description: 'Pesquisa somente aluguéis em 1–15 origens explícitas. Consulte seus filtros no catálogo.', inputSchema: search_input, outputSchema: search_output, annotations, _meta: {ui: {resourceUri: resource_uri}}}, (input, context) => service.search(input, context.mcpReq.signal, progress_reporter(context)));
  server.registerTool('get_rental_detail', {description: 'Detalhe usando a referência específica da origem; IDs, códigos, slugs e URLs não são intercambiáveis.', inputSchema: detail_input, outputSchema: provider_entry, annotations}, (input, context) => service.detail(input, context.mcpReq.signal));
  server.registerTool('get_rental_facets', {description: 'Catálogo real ou sugestões de localização; seletores e cidades obrigatórias constam no catálogo.', inputSchema: facets_input, outputSchema: facets_output, annotations}, (input, context) => service.facets(input, context.mcpReq.signal));
  register_resource(server);
  return server;
}
function register_resource(server: McpServer): void {
  registerAppResource(server, 'Pesquisa de aluguéis', resource_uri, {description: 'Formulários por origem e resultados seguros, sem acesso direto à rede.'}, async () => ({contents: [{uri: resource_uri, mimeType: RESOURCE_MIME_TYPE, text: await readFile(join(project_root(), 'dist/ui/mcp-app.html'), 'utf8'), _meta: {ui: {csp: {connectDomains: [], resourceDomains: [], frameDomains: []}}}}]}));
}
function progress_reporter(context: ServerContext) {
  const progressToken = context.mcpReq._meta?.progressToken;
  if (progressToken === undefined) return undefined;
  return async (provider: string, progress: number, total: number) => context.mcpReq.notify({method: 'notifications/progress', params: {progressToken, progress, total, message: `Consulta concluída: ${provider}`}});
}
