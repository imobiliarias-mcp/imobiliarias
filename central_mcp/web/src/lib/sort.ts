export type SortOrder = "total_asc" | "total_desc";

export const DEFAULT_SORT: SortOrder = "total_asc";

export const SORT_LABELS: Record<SortOrder, string> = {
  total_asc: "Menor preço total",
  total_desc: "Maior preço total",
};

export function isSortOrder(value: string | null): value is SortOrder {
  return value === "total_asc" || value === "total_desc";
}

/** Order listings by total monthly cost in the chosen direction; listings without a price always go last. */
export function sortByTotalPrice<T extends { total_price: number | null }>(items: T[], order: SortOrder): T[] {
  const direction = order === "total_asc" ? 1 : -1;
  return [...items].sort((left, right) => {
    if (left.total_price === null || right.total_price === null) {
      return Number(left.total_price === null) - Number(right.total_price === null);
    }
    return (left.total_price - right.total_price) * direction;
  });
}
