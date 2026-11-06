const CURRENCY = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

/** Format a monthly amount in Brazilian reais, or a dash when the value is unknown. */
export function formatBrl(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  return CURRENCY.format(value);
}

/** Capitalize a provider key for display (`vivareal` -> `Vivareal`). */
export function providerLabel(provider: string): string {
  return provider.replace(/^./, (first) => first.toUpperCase());
}
