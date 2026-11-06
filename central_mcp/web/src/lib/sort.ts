import type { Listing } from "@/types";

export type SortOrder = "total_asc" | "total_desc";

export const DEFAULT_SORT: SortOrder = "total_asc";

export const SORT_LABELS: Record<SortOrder, string> = {
  total_asc: "Menor preço total",
  total_desc: "Maior preço total",
};

export function isSortOrder(value: string | null): value is SortOrder {
  return value === "total_asc" || value === "total_desc";
}

/** Sort by total monthly cost; listings without a price always go last. */
export function sortListings(listings: Listing[], order: SortOrder): Listing[] {
  const direction = order === "total_asc" ? 1 : -1;
  return [...listings].sort((left, right) => {
    const leftPrice = left.total_price;
    const rightPrice = right.total_price;
    if (leftPrice === null && rightPrice === null) {
      return 0;
    }
    if (leftPrice === null) {
      return 1;
    }
    if (rightPrice === null) {
      return -1;
    }
    return (leftPrice - rightPrice) * direction;
  });
}
