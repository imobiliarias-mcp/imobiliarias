import { useId, useState } from "react";
import type { Neighborhood } from "@/types";

interface NeighborhoodPickerProps {
  neighborhoods: Neighborhood[];
  selectedKeys: string[];
  onChange: (keys: string[]) => void;
}

/** Multi-select of neighborhoods inside a disclosure, with a search box and removable chips. */
export function NeighborhoodPicker({ neighborhoods, selectedKeys, onChange }: NeighborhoodPickerProps) {
  const [query, setQuery] = useState("");
  const inputId = useId();
  const visible = neighborhoods.filter((item) => matches(item.name, query));
  const selectedNames = neighborhoods.filter((item) => selectedKeys.includes(item.key));

  function toggle(key: string) {
    const next = selectedKeys.includes(key) ? selectedKeys.filter((item) => item !== key) : [...selectedKeys, key];
    onChange(next);
  }

  if (neighborhoods.length === 0) {
    return <p className="text-xs text-muted-foreground">Nenhum bairro conhecido nesta cidade ainda.</p>;
  }

  return (
    <div className="grid gap-2">
      <details className="group rounded-md border border-border bg-card">
        <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between px-3 text-sm">
          Bairros {selectedKeys.length > 0 ? `(${selectedKeys.length})` : "(todos)"}
          <span aria-hidden="true" className="text-muted-foreground group-open:rotate-180">▾</span>
        </summary>
        <div className="grid gap-2 border-t border-border p-3">
          <label htmlFor={inputId} className="sr-only">
            Buscar bairro
          </label>
          <input
            id={inputId}
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar bairro"
            className="min-h-11 rounded-md border border-border bg-background px-3 text-sm"
          />
          <ul className="grid max-h-60 gap-1 overflow-y-auto">
            {visible.map((item) => (
              <li key={item.key}>
                <label className="flex min-h-11 items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedKeys.includes(item.key)}
                    onChange={() => toggle(item.key)}
                    className="size-4"
                  />
                  {item.name}
                </label>
              </li>
            ))}
            {visible.length === 0 && <li className="text-xs text-muted-foreground">Nenhum bairro encontrado.</li>}
          </ul>
        </div>
      </details>
      {selectedNames.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Bairros selecionados">
          {selectedNames.map((item) => (
            <li key={item.key}>
              <button
                type="button"
                onClick={() => toggle(item.key)}
                className="min-h-8 rounded-full border border-primary bg-primary/10 px-3 text-xs"
              >
                {item.name} <span aria-hidden="true">×</span>
                <span className="sr-only">remover {item.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function matches(name: string, query: string): boolean {
  const needle = query.trim().toLocaleLowerCase("pt-BR");
  return needle === "" || name.toLocaleLowerCase("pt-BR").includes(needle);
}
