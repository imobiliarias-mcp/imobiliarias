import type { ProviderInfo, SearchFilters, SearchResponse } from "@/types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { headers: { Accept: "application/json" }, signal });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const message = extractError(body) ?? `Erro ${response.status}`;
    throw new ApiError(message, response.status);
  }
  return body as T;
}

function extractError(body: unknown): string | null {
  if (body && typeof body === "object" && "error" in body && typeof body.error === "string") {
    return body.error;
  }
  return null;
}

export function fetchProviders(signal?: AbortSignal): Promise<ProviderInfo[]> {
  return getJson<ProviderInfo[]>("/api/providers", signal);
}

/** Build the query string for /api/search, dropping blank filters. */
export function buildSearchQuery(filters: SearchFilters): string {
  const params = new URLSearchParams();
  const entries: Array<[string, string]> = [
    ["city", filters.city.trim()],
    ["min_price", filters.minPrice.trim()],
    ["max_price", filters.maxPrice.trim()],
    ["bedrooms", filters.bedrooms.trim()],
  ];
  for (const [key, value] of entries) {
    if (value !== "") {
      params.set(key, value);
    }
  }
  if (filters.providers.length > 0) {
    params.set("providers", filters.providers.join(","));
  }
  return params.toString();
}

export function searchListings(filters: SearchFilters, signal?: AbortSignal): Promise<SearchResponse> {
  const query = buildSearchQuery(filters);
  return getJson<SearchResponse>(`/api/search${query ? `?${query}` : ""}`, signal);
}
