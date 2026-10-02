import { errorMessage } from './messages.js';
import { renderProviderCatalog } from './catalog-view.js';
import { readProviderCatalog, readSearchResponse, isRecord, structuredContent } from './contracts.js';
import { readSchemaForm, type JsonSchema } from './schema-form.js';
import { renderSearchResults } from './results-view.js';
import type { RentalAppPort } from './app-port.js';
import type { RentalProvider } from './types.js';

export interface RentalUiState {
  providers: RentalProvider[];
  controllers: Set<AbortController>;
  searchGeneration: number;
  disposed: boolean;
  hostSearchPending: boolean;
  readonly pageFilters: Map<string, Record<string, unknown>>;
  readonly detailGenerations: Map<string, number>;
  readonly facetGenerations: Map<string, number>;
}

export function createUiState(): RentalUiState {
  return {
    providers: [],
    controllers: new Set(),
    searchGeneration: 0,
    disposed: false,
    hostSearchPending: false,
    pageFilters: new Map(),
    detailGenerations: new Map(),
    facetGenerations: new Map(),
  };
}

export async function runCatalog(root: HTMLElement, app: RentalAppPort, state: RentalUiState, signal: AbortSignal): Promise<void> {
  setStatus(root, 'Carregando provedores de aluguel.');
  try {
    await receiveCatalog(root, app, state, signal);
  } catch (error) {
    if (state.disposed || signal.aborted) return;
    setStatus(root, `Não foi possível carregar os provedores. ${errorMessage(readErrorCode(error))}`, true);
  }
}

async function receiveCatalog(root: HTMLElement, app: RentalAppPort, state: RentalUiState, signal: AbortSignal): Promise<void> {
  const result = await app.callServerTool('list_rental_providers', {}, { timeout: 180_000, signal });
  if (state.disposed || signal.aborted) return;
  const catalog = readProviderCatalog(structuredContent(result));
  if (!catalog) throw new Error('invalid_output');
  state.providers = catalog;
  const providers = root.querySelector<HTMLElement>('[data-region="providers"]');
  if (providers) renderProviderCatalog(providers, catalog);
  setStatus(root, catalog.length ? 'Selecione uma ou mais imobiliárias e informe os filtros disponíveis.' : 'Nenhum provedor de aluguel está disponível.');
}

export async function runSearch(root: HTMLElement, app: RentalAppPort, state: RentalUiState, providerIds?: string[], pageOverride?: { providerId: string; page: number }): Promise<void> {
  const selected = selectedProviders(root, state.providers, providerIds);
  if (selected.length === 0) {
    setStatus(root, 'Selecione ao menos uma imobiliária disponível para pesquisar.', true);
    return;
  }
  const requests = selected.map((provider) => createProviderRequest(root, provider, pageOverride));
  if (requests.some((request) => request === undefined)) {
    setStatus(root, 'Revise os campos obrigatórios e os formatos informados.', true);
    return;
  }
  await callSearch(root, app, state, requests as { provider: string; filters: Record<string, unknown> }[]);
}

function selectedProviders(root: HTMLElement, providers: RentalProvider[], only?: string[]): RentalProvider[] {
  return providers.filter((provider) => {
    if (only && !only.includes(provider.id)) return false;
    const selection = root.querySelector<HTMLInputElement>(`[data-provider-selection="${escapeAttribute(provider.id)}"]`);
    return selection?.checked && !selection.disabled;
  });
}

function createProviderRequest(root: HTMLElement, provider: RentalProvider, pageOverride?: { providerId: string; page: number }): { provider: string; filters: Record<string, unknown> } | undefined {
  const form = root.querySelector<HTMLFormElement>(`[data-search-filters="${escapeAttribute(provider.id)}"]`);
  if (!form || !form.checkValidity()) return undefined;
  const filters = readSchemaForm(form, provider.filters);
  if (pageOverride?.providerId === provider.id) filters[pageField(provider.filters) ?? ''] = pageOverride.page;
  delete filters[''];
  return { provider: provider.id, filters };
}

async function callSearch(root: HTMLElement, app: RentalAppPort, state: RentalUiState, requests: { provider: string; filters: Record<string, unknown> }[]): Promise<void> {
  state.hostSearchPending = false;
  abortPendingRequests(state);
  const controller = createRequestController(state);
  const generation = ++state.searchGeneration;
  rememberPageFilters(state, requests);
  setStatus(root, 'Pesquisando imóveis nos provedores selecionados.');
  await executeSearch(root, app, state, requests, controller, generation);
}

function abortPendingRequests(state: RentalUiState): void {
  state.controllers.forEach((controller) => controller.abort());
  state.controllers.clear();
}

function rememberPageFilters(state: RentalUiState, requests: { provider: string; filters: Record<string, unknown> }[]): void {
  requests.forEach((request) => state.pageFilters.set(request.provider, request.filters));
}

async function executeSearch(root: HTMLElement, app: RentalAppPort, state: RentalUiState, requests: { provider: string; filters: Record<string, unknown> }[], controller: AbortController, generation: number): Promise<void> {
  try {
    await receiveSearchResults(root, app, state, requests, controller, generation);
  } catch (error) {
    if (isCurrentSearch(state, controller, generation)) setStatus(root, `A pesquisa não foi concluída. ${errorMessage(readErrorCode(error))}`, true);
  } finally {
    state.controllers.delete(controller);
  }
}

async function receiveSearchResults(root: HTMLElement, app: RentalAppPort, state: RentalUiState, requests: { provider: string; filters: Record<string, unknown> }[], controller: AbortController, generation: number): Promise<void> {
  const result = await app.callServerTool('search_rentals', { requests }, { timeout: 180_000, signal: controller.signal });
  if (!isCurrentSearch(state, controller, generation)) return;
  const response = readSearchResponse(structuredContent(result));
  if (!response) throw new Error('invalid_output');
  const region = root.querySelector<HTMLElement>('[data-region="results"]');
  if (region) renderSearchResults(region, response, state.providers);
  setStatus(root, statusForSearch(response.status));
}

function isCurrentSearch(state: RentalUiState, controller: AbortController, generation: number): boolean {
  return !controller.signal.aborted && !state.disposed && generation === state.searchGeneration;
}

function statusForSearch(status: string): string {
  if (status === 'partial') return 'A pesquisa terminou com resultados parciais. Consulte o estado de cada provedor.';
  if (status === 'error') return 'Não foi possível pesquisar nos provedores selecionados.';
  return 'Pesquisa concluída. Os resultados estão separados por provedor.';
}

export function cancelRequests(root: HTMLElement, state: RentalUiState): void {
  state.controllers.forEach((controller) => controller.abort());
  state.controllers.clear();
  state.searchGeneration += 1;
  setStatus(root, 'A consulta foi cancelada.');
}

export function setStatus(root: HTMLElement, message: string, isError = false): void {
  const status = root.querySelector<HTMLElement>('[role="status"]');
  if (!status) return;
  status.textContent = message;
  status.dataset.state = isError ? 'error' : 'ready';
}

export function createRequestController(state: RentalUiState): AbortController {
  const controller = new AbortController();
  state.controllers.add(controller);
  return controller;
}

export function nextGeneration(generations: Map<string, number>, providerId: string): number {
  const generation = (generations.get(providerId) ?? 0) + 1;
  generations.set(providerId, generation);
  return generation;
}

function pageField(schema: JsonSchema): string | undefined {
  return ['page_number', 'pageNumber', 'page', 'offset'].find((field) => ['integer', 'number'].includes(schema.properties?.[field]?.type ?? ''));
}

function escapeAttribute(value: string): string {
  return value.replaceAll('\\', '\\\\').replaceAll('"', '\\"');
}

function readErrorCode(error: unknown): string | undefined {
  if (error instanceof Error) return error.message;
  if (isRecord(error) && typeof error.code === 'string') return error.code;
  return undefined;
}
