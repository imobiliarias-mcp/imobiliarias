import { useId, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { providerLabel } from "@/lib/format";
import type { ProviderInfo, SearchFilters } from "@/types";

const BEDROOM_OPTIONS = ["", "1", "2", "3", "4"] as const;

interface SearchFormProps {
  filters: SearchFilters;
  providers: ProviderInfo[];
  busy: boolean;
  onChange: (next: SearchFilters) => void;
  onSubmit: () => void;
}

/** Filter bar: city, price range, bedrooms and which agencies to query. */
export function SearchForm({ filters, providers, busy, onChange, onSubmit }: SearchFormProps) {
  const ids = { city: useId(), min: useId(), max: useId(), bedrooms: useId() };

  function update<K extends keyof SearchFilters>(key: K, value: SearchFilters[K]) {
    onChange({ ...filters, [key]: value });
  }

  function toggleProvider(name: string) {
    const selected = filters.providers.includes(name)
      ? filters.providers.filter((item) => item !== name)
      : [...filters.providers, name];
    update("providers", selected);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-4 rounded-xl border border-border bg-card p-4 md:grid-cols-4">
      <label htmlFor={ids.city} className="grid gap-1 text-sm font-medium md:col-span-2">
        Cidade
        <Input
          id={ids.city}
          placeholder="Ex.: Timóteo"
          value={filters.city}
          onChange={(event) => update("city", event.target.value)}
        />
      </label>
      <div className="grid grid-cols-2 gap-3 md:col-span-2">
        <label htmlFor={ids.min} className="grid gap-1 text-sm font-medium">
          Preço mínimo (R$)
          <Input
            id={ids.min}
            inputMode="numeric"
            placeholder="0"
            value={filters.minPrice}
            onChange={(event) => update("minPrice", event.target.value)}
          />
        </label>
        <label htmlFor={ids.max} className="grid gap-1 text-sm font-medium">
          Preço máximo (R$)
          <Input
            id={ids.max}
            inputMode="numeric"
            placeholder="sem limite"
            value={filters.maxPrice}
            onChange={(event) => update("maxPrice", event.target.value)}
          />
        </label>
      </div>
      <label htmlFor={ids.bedrooms} className="grid gap-1 text-sm font-medium">
        Quartos
        <select
          id={ids.bedrooms}
          value={filters.bedrooms}
          onChange={(event) => update("bedrooms", event.target.value)}
          className="h-9 rounded-md border border-border bg-card px-3 text-sm"
        >
          {BEDROOM_OPTIONS.map((option) => (
            <option key={option || "any"} value={option}>
              {option === "" ? "Qualquer" : option === "4" ? "4 ou mais" : option}
            </option>
          ))}
        </select>
      </label>
      <fieldset className="grid gap-2 text-sm md:col-span-3">
        <legend className="mb-1 font-medium">Imobiliárias (vazio = todas)</legend>
        <div className="flex flex-wrap gap-2">
          {providers.map((provider) => {
            const selected = filters.providers.includes(provider.provider_name);
            return (
              <button
                key={provider.provider_name}
                type="button"
                aria-pressed={selected}
                onClick={() => toggleProvider(provider.provider_name)}
                className={
                  selected
                    ? "rounded-full border border-primary bg-primary px-3 py-1 text-xs text-primary-foreground"
                    : "rounded-full border border-border px-3 py-1 text-xs hover:bg-muted"
                }
              >
                {providerLabel(provider.provider_name)}
              </button>
            );
          })}
        </div>
      </fieldset>
      <div className="flex items-end">
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Buscando…" : "Buscar"}
        </Button>
      </div>
    </form>
  );
}
