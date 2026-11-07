import { ListingCard } from "@/components/ListingCard";
import { ListingRow } from "@/components/ListingRow";
import { LoadMore } from "@/components/LoadMore";
import { resultKey } from "@/lib/use-paged-search";
import { SORT_LABELS, type SortOrder } from "@/lib/sort";
import { cn } from "@/lib/utils";
import type { Listing, ViewMode } from "@/types";

interface ResultsSectionProps {
  listings: Listing[];
  total: number;
  hasMore: boolean;
  loadingMore: boolean;
  loadMoreError: string | null;
  onLoadMore: () => void;
  activeLabels: string[];
  sortOrder: SortOrder;
  view: ViewMode;
  hiddenWithoutNeighborhood: number;
  onSortChange: (order: SortOrder) => void;
  onViewChange: (view: ViewMode) => void;
  onOpen: (listing: Listing) => void;
  onClearFilters: () => void;
}

/** Toolbar (count, active filters, sort, view) and the listing grid or list. */
export function ResultsSection(props: ResultsSectionProps) {
  const { listings, onOpen } = props;
  return (
    <section className="grid gap-4" aria-label="Resultados">
      <ResultsToolbar {...props} />
      {props.hiddenWithoutNeighborhood > 0 && (
        <p role="status" className="rounded-lg border border-border bg-muted px-4 py-3 text-sm">
          {props.hiddenWithoutNeighborhood} imóvel(is) sem bairro informado foram ocultados pelo filtro de bairro.
        </p>
      )}
      {listings.length === 0 ? (
        <EmptyState onClearFilters={props.onClearFilters} />
      ) : props.view === "list" ? (
        <div className="grid gap-3">
          {listings.map((listing) => (
            <ListingRow key={resultKey(listing)} listing={listing} onOpen={onOpen} />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {listings.map((listing) => (
            <ListingCard key={resultKey(listing)} listing={listing} onOpen={onOpen} />
          ))}
        </div>
      )}
      {listings.length > 0 && (
        <LoadMore hasMore={props.hasMore} loading={props.loadingMore} error={props.loadMoreError} onLoadMore={props.onLoadMore} />
      )}
    </section>
  );
}

function ResultsToolbar({ listings, total, activeLabels, sortOrder, view, onSortChange, onViewChange }: ResultsSectionProps) {
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-medium" aria-live="polite">
          {listings.length} de {total} imóvel(is)
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm">
            Ordenar por
            <select
              value={sortOrder}
              onChange={(event) => onSortChange(event.target.value as SortOrder)}
              className="min-h-11 rounded-md border border-border bg-card px-3 text-sm"
            >
              {(Object.keys(SORT_LABELS) as SortOrder[]).map((order) => (
                <option key={order} value={order}>
                  {SORT_LABELS[order]}
                </option>
              ))}
            </select>
          </label>
          <ViewToggle view={view} onChange={onViewChange} />
        </div>
      </div>
      {activeLabels.length > 0 && (
        <ul className="flex flex-wrap gap-2 text-xs" aria-label="Filtros ativos">
          {activeLabels.map((label) => (
            <li key={label} className="rounded-full bg-muted px-3 py-1">
              {label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ViewToggle({ view, onChange }: { view: ViewMode; onChange: (view: ViewMode) => void }) {
  const options: Array<{ value: ViewMode; label: string }> = [
    { value: "grid", label: "Grade" },
    { value: "list", label: "Lista" },
  ];
  return (
    <div role="group" aria-label="Modo de exibição" className="inline-flex rounded-md border border-border">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={view === option.value}
          onClick={() => onChange(option.value)}
          className={cn("min-h-11 px-3 text-sm", view === option.value ? "bg-primary text-primary-foreground" : "hover:bg-muted")}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function EmptyState({ onClearFilters }: { onClearFilters: () => void }) {
  return (
    <div className="grid justify-items-start gap-3 rounded-xl border border-border p-6">
      <p className="text-sm">Nenhum imóvel encontrado com esses filtros.</p>
      <button type="button" onClick={onClearFilters} className="min-h-11 rounded-md border border-border px-4 hover:bg-muted">
        Limpar filtros
      </button>
    </div>
  );
}
