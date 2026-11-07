export type SortOrder = "total_asc" | "total_desc";

export const DEFAULT_SORT: SortOrder = "total_asc";

export const SORT_LABELS: Record<SortOrder, string> = {
  total_asc: "Menor preço total",
  total_desc: "Maior preço total",
};

export function isSortOrder(value: string | null): value is SortOrder {
  return value === "total_asc" || value === "total_desc";
}
