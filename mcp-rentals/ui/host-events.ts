import { isRecord, readSearchResponse, structuredContent } from './contracts.js';
import { cancelRequests, setStatus, type RentalUiState } from './operations.js';
import { renderSearchResults } from './results-view.js';
import { readSchemaForm } from './schema-form.js';
import type { RentalProvider, ToolResponse } from './types.js';

export function applyHostToolInput(root: HTMLElement, state: RentalUiState, value: unknown): void {
  if (!isRecord(value) || !isRecord(value.arguments)) return;
  const requests = value.arguments.requests;
  if (!Array.isArray(requests) || !requests.some((request) => isValidRequest(state.providers, request))) return;
  state.hostSearchPending = true;
  requests.forEach((request) => applyProviderInput(root, state.providers, request));
}

function isValidRequest(providers: RentalProvider[], value: unknown): boolean {
  if (!isRecord(value) || typeof value.provider !== 'string' || !isRecord(value.filters)) return false;
  return providers.length === 0 || providers.some((provider) => provider.id === value.provider);
}

function applyProviderInput(root: HTMLElement, providers: RentalProvider[], value: unknown): void {
  if (!isRecord(value) || typeof value.provider !== 'string' || !isRecord(value.filters)) return;
  const provider = providers.find((item) => item.id === value.provider);
  if (!provider) return;
  const section = root.querySelector<HTMLElement>(`[data-provider-id="${escapeAttribute(provider.id)}"]`);
  if (!section) return;
  const selection = section.querySelector<HTMLInputElement>('[data-provider-selection]');
  if (selection) selection.checked = true;
  const form = section.querySelector<HTMLFormElement>('[data-search-filters]');
  if (form) applyFilters(form, provider, value.filters);
}

function applyFilters(form: HTMLFormElement, provider: RentalProvider, filters: Record<string, unknown>): void {
  const current = readSchemaForm(form, provider.filters);
  const values = flattenFilters({ ...current, ...filters });
  const controls = Array.from(form.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-schema-path]'));
  values.forEach(([name, value]) => setControlValue(controls, name, value));
}

function flattenFilters(filters: Record<string, unknown>, prefix = ''): Array<[string, string | number | boolean]> {
  return Object.entries(filters).flatMap(([name, value]) => flattenFilter(name, value, prefix));
}

function flattenFilter(name: string, value: unknown, prefix: string): Array<[string, string | number | boolean]> {
  const path = prefix ? `${prefix}.${name}` : name;
  if (isRecord(value)) return flattenFilters(value, path);
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return [[path, value]];
  return [];
}

function setControlValue(controls: (HTMLInputElement | HTMLSelectElement)[], name: string, value: string | number | boolean): void {
  const control = controls.find((candidate) => candidate.name === name);
  if (control) control.value = String(value);
}

export function applyHostToolResult(root: HTMLElement, state: RentalUiState, value: unknown): void {
  if (!state.hostSearchPending || !isRecord(value)) return;
  const response = readSearchResponse(structuredContent(value as ToolResponse));
  if (!response || state.disposed) return;
  state.hostSearchPending = false;
  const resultRoot = root.querySelector<HTMLElement>('[data-region="results"]');
  if (resultRoot) renderSearchResults(resultRoot, response, state.providers);
  setStatus(root, response.status === 'partial' ? 'O resultado da pesquisa contém provedores com falha.' : 'Resultados atualizados pelo host.');
}

export function cancelHostRequest(root: HTMLElement, state: RentalUiState): void {
  if (!state.hostSearchPending) return;
  state.hostSearchPending = false;
  cancelRequests(root, state);
}

function escapeAttribute(value: string): string {
  return value.replaceAll('\\', '\\\\').replaceAll('"', '\\"');
}
