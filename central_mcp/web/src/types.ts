export interface ProviderInfo {
  provider_name: string;
  coverage_region: string;
  supported_operations: string[];
}

export interface ListingPhotos {
  photos: string[];
}

export interface Listing {
  provider: string;
  code: string | null;
  title: string | null;
  location: string | null;
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
}

export interface SearchFilters {
  providers: string[];
  city: string;
  minPrice: string;
  maxPrice: string;
  bedrooms: string;
}
