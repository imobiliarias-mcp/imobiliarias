import { DEFAULT_SORT, isSortOrder, type SortOrder } from "@/lib/sort";
import type { SearchFilters, ViewMode } from "@/types";

/** Everything that shapes the page; serialized into the URL so reloads keep the search. */
export interface AppUrlState {
  filters: SearchFilters;
  sortOrder: SortOrder;
  view: ViewMode;
}

export const EMPTY_FILTERS: SearchFilters = {
  city: "",
  neighborhoods: [],
  providers: [],
  minPrice: "",
  maxPrice: "",
  bedrooms: "",
};

const DEFAULT_STATE: AppUrlState = { filters: EMPTY_FILTERS, sortOrder: DEFAULT_SORT, view: "grid" };

/** Read page state from a query string (with or without the leading `?`). */
export function readUrlState(search: string): AppUrlState {
  const params = new URLSearchParams(search);
  const filters: SearchFilters = {
    city: params.get("cidade") ?? "",
    neighborhoods: splitList(params.get("bairros")),
    providers: splitList(params.get("imobs")),
    minPrice: params.get("min") ?? "",
    maxPrice: params.get("max") ?? "",
    bedrooms: params.get("quartos") ?? "",
  };
  const sort = params.get("ordem");
  return {
    filters,
    sortOrder: isSortOrder(sort) ? sort : DEFAULT_STATE.sortOrder,
    view: params.get("vista") === "lista" ? "list" : DEFAULT_STATE.view,
  };
}

/** Serialize page state, omitting values that equal the defaults. Returns "" or "?..." */
export function writeUrlState(state: AppUrlState): string {
  const params = new URLSearchParams();
  const { filters } = state;
  setIfPresent(params, "cidade", filters.city);
  setIfPresent(params, "bairros", filters.neighborhoods.join(","));
  setIfPresent(params, "imobs", filters.providers.join(","));
  setIfPresent(params, "min", filters.minPrice);
  setIfPresent(params, "max", filters.maxPrice);
  setIfPresent(params, "quartos", filters.bedrooms);
  if (state.sortOrder !== DEFAULT_STATE.sortOrder) {
    params.set("ordem", state.sortOrder);
  }
  if (state.view === "list") {
    params.set("vista", "lista");
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

function splitList(raw: string | null): string[] {
  if (!raw) {
    return [];
  }
  return raw.split(",").map((part) => part.trim()).filter((part) => part !== "");
}

function setIfPresent(params: URLSearchParams, key: string, value: string): void {
  if (value.trim() !== "") {
    params.set(key, value.trim());
  }
}
