import { providerLabel } from "@/lib/format";
import type { ProviderOutcome } from "@/types";

interface ProviderStatusBannerProps {
  outcomes: ProviderOutcome[];
}

/** Warns which agencies could not be queried, so partial results are not mistaken for complete ones. */
export function ProviderStatusBanner({ outcomes }: ProviderStatusBannerProps) {
  const failed = outcomes.filter((outcome) => outcome.status !== "ok");
  if (failed.length === 0) {
    return null;
  }
  const names = failed.map((outcome) => providerLabel(outcome.provider)).join(", ");
  return (
    <div role="status" className="rounded-lg border border-border bg-muted px-4 py-3 text-sm">
      {failed.length} imobiliária(s) não responderam: {names}. Os resultados podem estar incompletos.
    </div>
  );
}
