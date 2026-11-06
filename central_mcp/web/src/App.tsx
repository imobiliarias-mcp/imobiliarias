import { useEffect, useMemo, useState } from "react";
import { FilterDrawer } from "@/components/FilterDrawer";
import { FilterPanel } from "@/components/FilterPanel";
import { ListingDialog } from "@/components/ListingDialog";
import { ProviderStatusBanner } from "@/components/ProviderStatusBanner";
import { ResultsSection } from "@/components/ResultsSection";
import { Skeleton } from "@/components/ui/skeleton";
import { buildSearchQuery, fetchLocations, fetchProviders, searchListings } from "@/lib/api";
import { loadLastSearch, readCachedResults, saveLastSearch, writeCachedResults } from "@/lib/storage";
import { sortListings, type SortOrder } from "@/lib/sort";
import { readUrlState, writeUrlState, type AppUrlState } from "@/lib/url-state";
import type { Listing, LocationCatalog, ProviderInfo, SearchFilters, SearchResponse, ViewMode } from "@/types";

const SKELETON_COUNT = 6;
const EMPTY_LOCATIONS: LocationCatalog = { cities: [], neighborhoods: [] };

/** Results shown for one query, plus how many listings the neighborhood filter hid. */
type SearchState = SearchResponse;

/** Rental finder: filters live in the URL, results are cached per query, layout adapts to screen width. */
export function App() {
  const [initial] = useState(readInitialState);
  const [applied, setApplied] = useState<AppUrlState>(initial);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [locations, setLocations] = useState<LocationCatalog>(EMPTY_LOCATIONS);
  const [search, setSearch] = useState<SearchState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);
  const [selected, setSelected] = useState<Listing | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [elapsedMs, setElapsedMs] = useState<number | null>(null);

  const query = buildSearchQuery(applied.filters);
  const activeCount = countActive(applied.filters);

  useEffect(() => {
    const search = writeUrlState(applied);
    window.history.replaceState(null, "", `${window.location.pathname}${search}`);
    saveLastSearch(search);
  }, [applied]);

  useEffect(() => {
    const controller = new AbortController();
    fetchProviders(controller.signal).then(setProviders).catch(() => setProviders([]));
    fetchLocations(controller.signal).then(setLocations).catch(() => setLocations(EMPTY_LOCATIONS));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const cached = readCachedResults<SearchResponse>(query);
    setSearch(cached);
    setError(null);
    setLoading(true);
    const startedAt = performance.now();
    searchListings(query, controller.signal)
      .then((response) => {
        writeCachedResults(query, response);
        setSearch(response);
        setElapsedMs(performance.now() - startedAt);
        refreshLocations();
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(describeError(cause, "Falha na busca. Tente novamente."));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [query, retryToken]);

  const sorted = useMemo(
    () => sortListings(search?.results ?? [], applied.sortOrder),
    [search, applied.sortOrder],
  );

  /** The search records newly seen cities and neighborhoods on the server; pull them for the pickers. */
  function refreshLocations() {
    fetchLocations().then(setLocations).catch(() => undefined);
  }

  function applyFilters(filters: SearchFilters) {
    setApplied((current) => ({ ...current, filters }));
  }

  function clearFilters() {
    applyFilters({ ...applied.filters, city: "", neighborhoods: [], providers: [], minPrice: "", maxPrice: "", bedrooms: "" });
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 md:px-6">
      <header className="grid gap-1">
        <h1 className="text-2xl font-semibold">Aluguéis no Vale do Aço</h1>
        <p className="text-sm text-muted-foreground">
          Busca em todas as imobiliárias de uma vez. Fotos, preços e descrições vêm das próprias imobiliárias.
        </p>
      </header>

      <div className="grid gap-6 md:grid-cols-[18rem_1fr] lg:grid-cols-[19rem_1fr]">
        <aside className="hidden md:block md:self-start md:sticky md:top-4 md:max-h-[calc(100dvh-2rem)] md:overflow-y-auto md:rounded-xl md:border md:border-border md:bg-card md:p-4">
          <FilterPanel applied={applied.filters} providers={providers} locations={locations} onApply={applyFilters} />
        </aside>

        <main className="grid min-w-0 content-start gap-4 pb-24 md:pb-0">
          {error && (
            <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive px-4 py-3 text-sm text-destructive">
              <span>{error}</span>
              <button type="button" onClick={() => setRetryToken((value) => value + 1)} className="min-h-11 rounded-md border border-destructive px-4">
                Tentar de novo
              </button>
            </div>
          )}

          {search && <ProviderStatusBanner outcomes={search.providers} />}

          {!search && loading && <LoadingGrid />}

          {search && (
            <>
              {loading && <p className="text-xs text-muted-foreground" aria-live="polite">Atualizando resultados…</p>}
              {!loading && elapsedMs !== null && <p className="text-xs text-muted-foreground">Busca em {(elapsedMs / 1000).toFixed(1)} s</p>}
              <ResultsSection
                listings={sorted}
                activeLabels={activeLabels(applied.filters, locations, providers)}
                sortOrder={applied.sortOrder}
                view={applied.view}
                hiddenWithoutNeighborhood={search.hidden_without_neighborhood}
                onSortChange={(order: SortOrder) => setApplied((current) => ({ ...current, sortOrder: order }))}
                onViewChange={(view: ViewMode) => setApplied((current) => ({ ...current, view }))}
                onOpen={setSelected}
                onClearFilters={clearFilters}
              />
            </>
          )}
        </main>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-10 border-t border-border bg-card p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:hidden">
        <button type="button" onClick={() => setDrawerOpen(true)} className="min-h-11 w-full rounded-md bg-primary text-primary-foreground">
          Filtros{activeCount > 0 ? ` (${activeCount})` : ""}
        </button>
      </div>

      <FilterDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <FilterPanel applied={applied.filters} providers={providers} locations={locations} onApply={applyFilters} />
      </FilterDrawer>

      <ListingDialog listing={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function readInitialState(): AppUrlState {
  const search = window.location.search || loadLastSearch() || "";
  return readUrlState(search);
}

function countActive(filters: SearchFilters): number {
  const scalars = [filters.city, filters.minPrice, filters.maxPrice, filters.bedrooms].filter((value) => value !== "");
  return scalars.length + filters.neighborhoods.length + filters.providers.length;
}

function activeLabels(filters: SearchFilters, locations: LocationCatalog, providers: ProviderInfo[]): string[] {
  const labels: string[] = [];
  const cityName = locations.cities.find((city) => city.key === filters.city)?.name;
  if (filters.city) {
    labels.push(cityName ?? filters.city);
  }
  for (const key of filters.neighborhoods) {
    labels.push(locations.neighborhoods.find((item) => item.key === key)?.name ?? key);
  }
  if (filters.minPrice || filters.maxPrice) {
    labels.push(`Aluguel ${filters.minPrice || "0"} a ${filters.maxPrice || "∞"}`);
  }
  if (filters.bedrooms) {
    labels.push(filters.bedrooms === "4" ? "4+ quartos" : `${filters.bedrooms} quarto(s)`);
  }
  for (const name of filters.providers) {
    labels.push(providers.find((item) => item.provider_name === name)?.provider_name ?? name);
  }
  return labels;
}

function LoadingGrid() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true" aria-label="Buscando imóveis">
      {Array.from({ length: SKELETON_COUNT }, (_, position) => (
        <div key={position} className="grid gap-3 rounded-xl border border-border p-3">
          <Skeleton className="aspect-[4/3] w-full" />
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-6 w-1/3" />
        </div>
      ))}
    </div>
  );
}

function describeError(cause: unknown, fallback: string): string {
  if (cause instanceof Error && cause.message) {
    return cause.message;
  }
  return fallback;
}
