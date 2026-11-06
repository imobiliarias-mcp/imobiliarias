import type { LocationCatalog, ProviderInfo, SearchFilters, SearchResponse } from "@/types";

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

export function fetchLocations(signal?: AbortSignal): Promise<LocationCatalog> {
  return getJson<LocationCatalog>("/api/locations", signal);
}

/** Build the query string for /api/search from filters; blank values are dropped. */
export function buildSearchQuery(filters: SearchFilters): string {
  const params = new URLSearchParams({ transaction: "rent" });
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
  if (filters.neighborhoods.length > 0) {
    params.set("neighborhoods", filters.neighborhoods.join(","));
  }
  if (filters.providers.length > 0) {
    params.set("providers", filters.providers.join(","));
  }
  return params.toString();
}

export function searchListings(query: string, signal?: AbortSignal): Promise<SearchResponse> {
  return getJson<SearchResponse>(`/api/search?${query}`, signal);
}
