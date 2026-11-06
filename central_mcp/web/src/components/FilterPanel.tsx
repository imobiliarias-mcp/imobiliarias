import { useEffect, useId, useRef, useState } from "react";
import { NeighborhoodPicker } from "@/components/NeighborhoodPicker";
import { Button } from "@/components/ui/button";
import { providerLabel } from "@/lib/format";
import { EMPTY_FILTERS } from "@/lib/url-state";
import type { City, LocationCatalog, ProviderInfo, SearchFilters } from "@/types";

const BEDROOM_OPTIONS = ["", "1", "2", "3", "4"] as const;

interface FilterPanelProps {
  applied: SearchFilters;
  providers: ProviderInfo[];
  locations: LocationCatalog;
  onApply: (filters: SearchFilters) => void;
}

const APPLY_DELAY_MS = 400;

/**
 * Filter controls. Changes apply on their own after a short pause (debounce), so typing a
 * price does not fire a search per keystroke. Outside changes (e.g. "Limpar filtros") sync in.
 */
export function FilterPanel({ applied, providers, locations, onApply }: FilterPanelProps) {
  const [draft, setDraft] = useState<SearchFilters>(applied);
  const lastEmitted = useRef<SearchFilters>(applied);
  useSyncWithOutside(applied, lastEmitted, setDraft);
  useDebouncedApply(draft, lastEmitted, APPLY_DELAY_MS, (filters) => emit(filters));
  const ids = { price: useId(), max: useId(), bedrooms: useId(), city: useId() };
  const cityNeighborhoods = locations.neighborhoods.filter((item) => item.city_key === draft.city);

  function update<K extends keyof SearchFilters>(key: K, value: SearchFilters[K]) {
    setDraft({ ...draft, [key]: value });
  }

  function changeCity(city: string) {
    setDraft({ ...draft, city, neighborhoods: [] });
  }

  function toggleProvider(name: string) {
    const selected = draft.providers.includes(name)
      ? draft.providers.filter((item) => item !== name)
      : [...draft.providers, name];
    update("providers", selected);
  }

  function emit(filters: SearchFilters) {
    lastEmitted.current = filters;
    onApply(filters);
  }

  function clearAll() {
    setDraft(EMPTY_FILTERS);
    emit(EMPTY_FILTERS);
  }

  return (
    <div className="grid gap-5 text-sm" role="group" aria-label="Filtros de busca">
      <fieldset className="grid gap-2">
        <legend className="mb-1 font-medium">Negócio</legend>
        <div className="grid grid-cols-2 gap-2" role="group" aria-label="Tipo de negócio">
          <button type="button" aria-pressed="true" className="min-h-11 rounded-md border border-primary bg-primary text-primary-foreground">
            Aluguel
          </button>
          <button
            type="button"
            disabled
            title="Venda estará disponível em breve"
            className="min-h-11 rounded-md border border-border text-muted-foreground opacity-60"
          >
            Venda
          </button>
        </div>
      </fieldset>

      <div className="grid gap-2">
        <label htmlFor={ids.city} className="font-medium">
          Cidade
        </label>
        <select
          id={ids.city}
          value={draft.city}
          onChange={(event) => changeCity(event.target.value)}
          className="min-h-11 rounded-md border border-border bg-card px-3"
        >
          <option value="">Todas as cidades</option>
          {locations.cities.map((city: City) => (
            <option key={city.key} value={city.key}>
              {city.name}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-2">
        <span className="font-medium">Bairros</span>
        {draft.city === "" ? (
          <p className="text-xs text-muted-foreground">Escolha uma cidade para filtrar por bairro.</p>
        ) : (
          <NeighborhoodPicker
            neighborhoods={cityNeighborhoods}
            selectedKeys={draft.neighborhoods}
            onChange={(keys) => update("neighborhoods", keys)}
          />
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label htmlFor={ids.price} className="grid min-w-0 gap-1">
          <span className="font-medium">Aluguel mínimo</span>
          <input
            id={ids.price}
            inputMode="numeric"
            placeholder="R$ 0"
            value={draft.minPrice}
            onChange={(event) => update("minPrice", event.target.value)}
            className="min-h-11 w-full min-w-0 rounded-md border border-border bg-card px-3"
          />
        </label>
        <label htmlFor={ids.max} className="grid min-w-0 gap-1">
          <span className="font-medium">Aluguel máximo</span>
          <input
            id={ids.max}
            inputMode="numeric"
            placeholder="sem limite"
            value={draft.maxPrice}
            onChange={(event) => update("maxPrice", event.target.value)}
            className="min-h-11 w-full min-w-0 rounded-md border border-border bg-card px-3"
          />
        </label>
      </div>

      <label htmlFor={ids.bedrooms} className="grid gap-1">
        <span className="font-medium">Quartos</span>
        <select
          id={ids.bedrooms}
          value={draft.bedrooms}
          onChange={(event) => update("bedrooms", event.target.value)}
          className="min-h-11 rounded-md border border-border bg-card px-3"
        >
          {BEDROOM_OPTIONS.map((option) => (
            <option key={option || "any"} value={option}>
              {option === "" ? "Qualquer" : option === "4" ? "4 ou mais" : option}
            </option>
          ))}
        </select>
      </label>

      <details className="group rounded-md border border-border bg-card">
        <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between px-3 font-medium">
          Imobiliárias {draft.providers.length > 0 ? `(${draft.providers.length})` : ""}
          <span aria-hidden="true" className="text-muted-foreground group-open:rotate-180">▾</span>
        </summary>
        <div className="flex flex-wrap gap-2 border-t border-border p-3">
          {providers.map((provider) => {
            const selected = draft.providers.includes(provider.provider_name);
            return (
              <button
                key={provider.provider_name}
                type="button"
                aria-pressed={selected}
                onClick={() => toggleProvider(provider.provider_name)}
                className={
                  selected
                    ? "min-h-11 rounded-full border border-primary bg-primary px-4 text-primary-foreground"
                    : "min-h-11 rounded-full border border-border px-4 hover:bg-muted"
                }
              >
                {providerLabel(provider.provider_name)}
              </button>
            );
          })}
        </div>
      </details>

      <Button type="button" variant="outline" onClick={clearAll} className="min-h-11">
        Limpar filtros
      </Button>
    </div>
  );
}

function sameFilters(left: SearchFilters, right: SearchFilters): boolean {
  return (
    left.city === right.city &&
    left.minPrice === right.minPrice &&
    left.maxPrice === right.maxPrice &&
    left.bedrooms === right.bedrooms &&
    left.neighborhoods.join(",") === right.neighborhoods.join(",") &&
    left.providers.join(",") === right.providers.join(",")
  );
}

/** Adopt filters changed from outside (URL, "Limpar" elsewhere), but not our own echo. */
function useSyncWithOutside(
  applied: SearchFilters,
  lastEmitted: { current: SearchFilters },
  setDraft: (filters: SearchFilters) => void,
) {
  useEffect(() => {
    if (applied === lastEmitted.current) {
      return;
    }
    lastEmitted.current = applied;
    setDraft(applied);
  }, [applied, lastEmitted, setDraft]);
}

/** Emit the draft once it has been still for `delayMs` and differs from what was last emitted. */
function useDebouncedApply(
  draft: SearchFilters,
  lastEmitted: { current: SearchFilters },
  delayMs: number,
  emit: (filters: SearchFilters) => void,
) {
  useEffect(() => {
    if (sameFilters(draft, lastEmitted.current)) {
      return;
    }
    const timer = window.setTimeout(() => emit(draft), delayMs);
    return () => window.clearTimeout(timer);
    // Only a change of draft restarts the timer; re-renders must not postpone the search.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, delayMs]);
}
