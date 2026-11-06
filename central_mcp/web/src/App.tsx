import { useEffect, useMemo, useRef, useState } from "react";
import { ListingCard } from "@/components/ListingCard";
import { ListingDialog } from "@/components/ListingDialog";
import { ProviderStatusBanner } from "@/components/ProviderStatusBanner";
import { SearchForm } from "@/components/SearchForm";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchProviders, searchListings } from "@/lib/api";
import { SORT_LABELS, sortListings, type SortOrder } from "@/lib/sort";
import type { Listing, ProviderInfo, ProviderOutcome, SearchFilters } from "@/types";

const EMPTY_FILTERS: SearchFilters = { providers: [], city: "", minPrice: "", maxPrice: "", bedrooms: "" };
const SKELETON_COUNT = 6;

interface SearchState {
  listings: Listing[];
  outcomes: ProviderOutcome[];
}

/** Single-screen rental finder: filters, aggregated results and per-listing details. */
export function App() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [filters, setFilters] = useState<SearchFilters>(EMPTY_FILTERS);
  const [search, setSearch] = useState<SearchState | null>(null);
  const [sortOrder, setSortOrder] = useState<SortOrder>("total_asc");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Listing | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchProviders(controller.signal)
      .then(setProviders)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(describeError(cause, "Não foi possível carregar as imobiliárias."));
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const sorted = useMemo(() => sortListings(search?.listings ?? [], sortOrder), [search, sortOrder]);

  async function runSearch() {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const response = await searchListings(filters, controller.signal);
      setSearch({ listings: response.results, outcomes: response.providers });
    } catch (cause: unknown) {
      if (!controller.signal.aborted) {
        setError(describeError(cause, "Falha na busca. Tente novamente."));
      }
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 md:px-6">
      <header>
        <h1 className="text-2xl font-semibold">Aluguéis no Vale do Aço</h1>
        <p className="text-sm text-muted-foreground">
          Busca em todas as imobiliárias de uma vez. Fotos, preços e descrições vêm das próprias imobiliárias.
        </p>
      </header>

      <SearchForm
        filters={filters}
        providers={providers}
        busy={loading}
        onChange={setFilters}
        onSubmit={runSearch}
      />

      {error && (
        <p role="alert" className="rounded-lg border border-destructive px-4 py-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {search && <ProviderStatusBanner outcomes={search.outcomes} />}

      {loading && <LoadingGrid />}

      {!loading && search && (
        <ResultsSection
          listings={sorted}
          sortOrder={sortOrder}
          onSortChange={setSortOrder}
          onOpen={setSelected}
        />
      )}

      {!loading && !search && !error && (
        <p className="text-sm text-muted-foreground">Escolha os filtros e clique em Buscar.</p>
      )}

      <ListingDialog listing={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

interface ResultsSectionProps {
  listings: Listing[];
  sortOrder: SortOrder;
  onSortChange: (order: SortOrder) => void;
  onOpen: (listing: Listing) => void;
}

function ResultsSection({ listings, sortOrder, onSortChange, onOpen }: ResultsSectionProps) {
  if (listings.length === 0) {
    return <p className="text-sm text-muted-foreground">Nenhum imóvel encontrado com esses filtros.</p>;
  }
  return (
    <section className="grid gap-4" aria-label="Resultados">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">{listings.length} imóvel(is) encontrado(s)</p>
        <label className="flex items-center gap-2 text-sm">
          Ordenar por
          <select
            value={sortOrder}
            onChange={(event) => onSortChange(event.target.value as SortOrder)}
            className="h-9 rounded-md border border-border bg-card px-3 text-sm"
          >
            {(Object.keys(SORT_LABELS) as SortOrder[]).map((order) => (
              <option key={order} value={order}>
                {SORT_LABELS[order]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {listings.map((listing) => (
          <ListingCard key={`${listing.provider}-${listing.code ?? listing.official_url ?? listing.title}`} listing={listing} onOpen={onOpen} />
        ))}
      </div>
    </section>
  );
}

function LoadingGrid() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true" aria-label="Buscando imóveis">
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
