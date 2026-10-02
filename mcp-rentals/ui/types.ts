import type { JsonSchema } from './schema-form.js';

export interface RentalProvider {
  id: string;
  label: string;
  filters: JsonSchema;
  reference: JsonSchema;
  facets: JsonSchema | null;
  capabilities: { search: boolean; detail: boolean; facets: boolean };
  limitations: string[];
  installation: { available: boolean };
  public_hosts: string[];
  detail_path_pattern: string;
}

export interface DisplayItem {
  reference?: unknown;
  url?: string;
  title?: unknown;
  location?: unknown;
  price?: unknown;
}

export interface ProviderSearchSuccess {
  provider: string;
  status: 'ok';
  native: unknown;
  display: DisplayItem[];
}

export interface ProviderSearchFailure {
  provider: string;
  status: 'error';
  error: { code: string; message: string };
}

export type ProviderSearchResult = ProviderSearchSuccess | ProviderSearchFailure;

export interface SearchResponse {
  status: 'ok' | 'partial' | 'error';
  providers: ProviderSearchResult[];
}

export interface ToolResponse {
  isError?: boolean;
  structuredContent?: unknown;
  content?: unknown;
}

export interface FacetResponse {
  provider?: string;
  kind?: 'catalog' | 'location_suggestions';
  status: 'ok' | 'error';
  native?: unknown;
  display?: unknown;
  error?: { code?: string; message?: string };
}
