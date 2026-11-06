export interface ProviderInfo {
  provider_name: string;
  coverage_region: string;
  supported_operations: string[];
}

export interface Listing {
  provider: string;
  code: string | null;
  title: string | null;
  location: string | null;
  city: string | null;
  neighborhood: string | null;
  transaction: string | null;
  rent_price: number | null;
  condo_fee: number | null;
  iptu: number | null;
  total_price: number | null;
  bedrooms: number | null;
  official_url: string | null;
  cover_photo: string | null;
  photos: string[];
  description: string | null;
}

export interface ProviderOutcome {
  provider: string;
  status: "ok" | "error" | "unavailable";
  count: number;
  error_code: string | null;
  error: string | null;
}

export interface SearchResponse {
  status: "ok" | "partial" | "error";
  providers: ProviderOutcome[];
  results: Listing[];
  hidden_without_neighborhood: number;
}

export interface City {
  key: string;
  name: string;
}

export interface Neighborhood {
  key: string;
  name: string;
  city_key: string;
}

export interface LocationCatalog {
  cities: City[];
  neighborhoods: Neighborhood[];
}

/** Filters as the user sees them; city and neighborhoods are catalog keys. */
export interface SearchFilters {
  city: string;
  neighborhoods: string[];
  providers: string[];
  minPrice: string;
  maxPrice: string;
  bedrooms: string;
}

export type ViewMode = "grid" | "list";
