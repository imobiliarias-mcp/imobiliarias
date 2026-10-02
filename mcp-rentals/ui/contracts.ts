import type { JsonSchema } from './schema-form.js';
import type { RentalProvider, SearchResponse, ToolResponse } from './types.js';

export function structuredContent(result: ToolResponse): Record<string, unknown> | undefined {
  if (result.isError || !isRecord(result.structuredContent)) return undefined;
  return result.structuredContent;
}

export function readProviderCatalog(value: unknown): RentalProvider[] | undefined {
  if (!isRecord(value) || !Array.isArray(value.providers)) return undefined;
  const providers = value.providers.filter(isRentalProvider);
  return providers.length === value.providers.length ? providers : undefined;
}

export function readSearchResponse(value: unknown): SearchResponse | undefined {
  if (!isRecord(value) || !isSearchStatus(value.status) || !Array.isArray(value.providers)) return undefined;
  if (!value.providers.every(isProviderResult)) return undefined;
  return value as unknown as SearchResponse;
}

export function readFacetResponse(value: unknown): Record<string, unknown> | undefined {
  if (!isRecord(value) || value.status !== 'ok' && value.status !== 'error') return undefined;
  return value;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isRentalProvider(value: unknown): value is RentalProvider {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.label !== 'string') return false;
  if (!isJsonSchema(value.filters) || !isJsonSchema(value.reference)) return false;
  if (value.facets !== null && !isJsonSchema(value.facets)) return false;
  return hasCapabilities(value.capabilities)
    && hasInstallation(value.installation)
    && hasLimitations(value.limitations)
    && hasPublicHosts(value.public_hosts)
    && isValidPathPattern(value.detail_path_pattern);
}

function isJsonSchema(value: unknown): value is JsonSchema {
  if (!isRecord(value)) return false;
  if (value.type !== undefined && typeof value.type !== 'string') return false;
  if (value.properties === undefined) return true;
  return isRecord(value.properties) && Object.values(value.properties).every(isJsonSchema);
}

function hasCapabilities(value: unknown): value is RentalProvider['capabilities'] {
  if (!isRecord(value)) return false;
  return typeof value.search === 'boolean' && typeof value.detail === 'boolean' && typeof value.facets === 'boolean';
}

function hasInstallation(value: unknown): value is RentalProvider['installation'] {
  return isRecord(value) && typeof value.available === 'boolean';
}

function hasLimitations(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === 'string');
}

function hasPublicHosts(value: unknown): value is string[] {
  return Array.isArray(value) && value.length > 0 && value.every(isNonEmptyString);
}

function isValidPathPattern(value: unknown): value is string {
  if (!isNonEmptyString(value)) return false;
  try {
    new RegExp(value);
    return true;
  } catch {
    return false;
  }
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isSearchStatus(value: unknown): value is SearchResponse['status'] {
  return value === 'ok' || value === 'partial' || value === 'error';
}

function isProviderResult(value: unknown): boolean {
  if (!isRecord(value) || !isNonEmptyString(value.provider)) return false;
  if (value.status === 'error') return isProviderError(value.error);
  return value.status === 'ok' && Array.isArray(value.display) && value.display.every(isDisplayItem);
}

function isProviderError(value: unknown): boolean {
  return isRecord(value) && isNonEmptyString(value.code) && isNonEmptyString(value.message);
}

function isDisplayItem(value: unknown): boolean {
  if (!isRecord(value)) return false;
  if (value.url !== undefined && typeof value.url !== 'string') return false;
  return Object.values(value).every(isJsonValue);
}

function isJsonValue(value: unknown): boolean {
  if (value === null || ['string', 'number', 'boolean'].includes(typeof value)) return true;
  if (Array.isArray(value)) return value.every(isJsonValue);
  if (isRecord(value)) return Object.values(value).every(isJsonValue);
  return false;
}
