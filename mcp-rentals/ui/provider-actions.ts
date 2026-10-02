import { errorFrom, errorMessage } from './messages.js';
import { readFacetResponse, isRecord, structuredContent } from './contracts.js';
import { createRequestController, nextGeneration, setStatus, type RentalUiState } from './operations.js';
import { readSchemaForm } from './schema-form.js';
import { renderFacetResult, safeProviderUrl } from './results-view.js';
import { supportsReference } from './reference-validation.js';
import type { RentalAppPort } from './app-port.js';
import type { RentalProvider } from './types.js';

export async function runFacets(root: HTMLElement, app: RentalAppPort, state: RentalUiState, provider: RentalProvider): Promise<void> {
  if (!provider.capabilities.facets || !provider.facets) return;
  const form = root.querySelector<HTMLFormElement>(`[data-facet-form="${escapeAttribute(provider.id)}"]`);
  if (!form || !form.checkValidity()) return setStatus(root, 'Informe os campos obrigatórios para consultar as facetas.', true);
  await callFacets(root, app, state, provider, readSchemaForm(form, provider.facets));
}

async function callFacets(root: HTMLElement, app: RentalAppPort, state: RentalUiState, provider: RentalProvider, request: Record<string, unknown>): Promise<void> {
  const generation = nextGeneration(state.facetGenerations, provider.id);
  const controller = createRequestController(state);
  try {
    await receiveFacets(root, app, state, provider, request, controller, generation);
  } catch (error) {
    if (!controller.signal.aborted && !state.disposed) setStatus(root, `Não foi possível consultar as facetas. ${readError(error)}`, true);
  } finally {
    state.controllers.delete(controller);
  }
}

async function receiveFacets(root: HTMLElement, app: RentalAppPort, state: RentalUiState, provider: RentalProvider, request: Record<string, unknown>, controller: AbortController, generation: number): Promise<void> {
  const result = await app.callServerTool('get_rental_facets', { provider: provider.id, request }, { timeout: 180_000, signal: controller.signal });
  if (isStale(state, controller, provider.id, generation)) return;
  const response = readFacetResponse(structuredContent(result));
  if (!response) throw new Error('invalid_output');
  const results = root.querySelector<HTMLElement>('[data-region="results"]');
  if (results) renderFacetResult(results, provider, response);
  if (response.status === 'error') setStatus(root, errorFrom(response.error), true);
}

export async function runDetail(root: HTMLElement, app: RentalAppPort, state: RentalUiState, providerId: string, reference: unknown): Promise<void> {
  const provider = state.providers.find((item) => item.id === providerId);
  if (!provider?.capabilities.detail || !supportsReference(reference, provider.reference)) return;
  await callDetail(root, app, state, provider, reference);
}

async function callDetail(root: HTMLElement, app: RentalAppPort, state: RentalUiState, provider: RentalProvider, reference: unknown): Promise<void> {
  const generation = nextGeneration(state.detailGenerations, provider.id);
  const controller = createRequestController(state);
  try {
    await receiveDetail(root, app, state, provider, reference, controller, generation);
  } catch (error) {
    if (!controller.signal.aborted && !state.disposed) setStatus(root, `Não foi possível carregar os detalhes. ${readError(error)}`, true);
  } finally {
    state.controllers.delete(controller);
  }
}

async function receiveDetail(root: HTMLElement, app: RentalAppPort, state: RentalUiState, provider: RentalProvider, reference: unknown, controller: AbortController, generation: number): Promise<void> {
  const result = await app.callServerTool('get_rental_detail', { provider: provider.id, reference }, { timeout: 180_000, signal: controller.signal });
  if (isStale(state, controller, provider.id, generation, true)) return;
  const response = structuredContent(result);
  if (!isRecord(response) || response.status !== 'ok' && response.status !== 'error') throw new Error('invalid_output');
  appendDetail(root, provider.id, response);
  if (response.status === 'error') setStatus(root, errorFrom(response.error), true);
}

function isStale(state: RentalUiState, controller: AbortController, providerId: string, generation: number, detail = false): boolean {
  const generations = detail ? state.detailGenerations : state.facetGenerations;
  return state.disposed || controller.signal.aborted || generations.get(providerId) !== generation;
}

function appendDetail(root: HTMLElement, providerId: string, response: Record<string, unknown>): void {
  const results = root.querySelector<HTMLElement>(`[data-provider-results="${escapeAttribute(providerId)}"]`);
  if (!results) return;
  const detail = root.ownerDocument.createElement('details');
  detail.open = true;
  detail.className = 'detail-view';
  detail.append(createDetailSummary(root), createDetailContent(root, response.display ?? response.native));
  results.append(detail);
}

function createDetailSummary(root: HTMLElement): HTMLElement {
  const heading = root.ownerDocument.createElement('summary');
  heading.textContent = 'Detalhes do imóvel';
  return heading;
}

function createDetailContent(root: HTMLElement, value: unknown): HTMLElement {
  const text = root.ownerDocument.createElement('pre');
  text.textContent = safeJson(value);
  return text;
}

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? 'Detalhes indisponíveis.';
  } catch {
    return 'Detalhes indisponíveis.';
  }
}

export async function openListingLink(root: HTMLElement, app: RentalAppPort, state: RentalUiState, providerId: string, value: unknown): Promise<void> {
  const provider = state.providers.find((entry) => entry.id === providerId);
  if (!provider) return;
  const url = safeProviderUrl(value, provider);
  if (!url) return;
  try {
    const result = await app.openLink(url);
    if (result.isError) setStatus(root, 'O host não autorizou abrir este anúncio.', true);
  } catch {
    setStatus(root, 'Não foi possível abrir este anúncio.', true);
  }
}

function readError(error: unknown): string {
  const code = error instanceof Error ? error.message : undefined;
  return errorMessage(code);
}

function escapeAttribute(value: string): string {
  return value.replaceAll('\\', '\\\\').replaceAll('"', '\\"');
}
