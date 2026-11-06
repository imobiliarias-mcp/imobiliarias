import { useEffect, useRef, useState, type MouseEvent } from "react";
import { CoverImage, OfficialLink } from "@/components/ListingCard";
import { formatBrl, providerLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Listing } from "@/types";

interface ListingDialogProps {
  listing: Listing | null;
  onClose: () => void;
}

/** Modal with the full photo gallery, description and price breakdown of one listing. */
export function ListingDialog({ listing, onClose }: ListingDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }
    if (listing && !dialog.open) {
      dialog.showModal();
    }
    if (!listing && dialog.open) {
      dialog.close();
    }
  }, [listing]);

  function handleBackdropClick(event: MouseEvent<HTMLDialogElement>) {
    if (event.target === dialogRef.current) {
      dialogRef.current?.close();
    }
  }

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      onClick={handleBackdropClick}
      className="m-auto max-h-[90vh] w-[min(56rem,calc(100vw-2rem))] rounded-xl border border-border bg-card p-0 text-card-foreground backdrop:bg-black/60"
    >
      {listing && <ListingDetails listing={listing} onClose={() => dialogRef.current?.close()} />}
    </dialog>
  );
}

interface ListingDetailsProps {
  listing: Listing;
  onClose: () => void;
}

function ListingDetails({ listing, onClose }: ListingDetailsProps) {
  const [index, setIndex] = useState(0);
  const photos = listing.photos.length > 0 ? listing.photos : [listing.cover_photo].filter((p): p is string => !!p);
  const current = photos[index] ?? null;

  return (
    <div className="flex max-h-[90vh] flex-col overflow-y-auto">
      <div className="flex items-start justify-between gap-4 border-b border-border p-4">
        <div>
          <p className="text-xs text-muted-foreground">
            {providerLabel(listing.provider)} · {listing.location ?? "Localização não informada"}
          </p>
          <h2 className="text-lg font-semibold">{listing.title ?? "Imóvel sem título"}</h2>
        </div>
        <button type="button" onClick={onClose} className="rounded-md px-3 py-1 text-sm hover:bg-muted">
          Fechar
        </button>
      </div>

      <div className="grid gap-4 p-4 md:grid-cols-[3fr_2fr]">
        <div className="grid gap-2">
          <div className="aspect-[4/3] overflow-hidden rounded-lg bg-muted">
            <CoverImage key={current ?? "none"} src={current} alt={listing.title ?? "Foto do imóvel"} />
          </div>
          {photos.length > 1 && (
            <div className="flex gap-2 overflow-x-auto pb-1" role="group" aria-label="Galeria de fotos">
              {photos.map((url, position) => (
                <button
                  key={url}
                  type="button"
                  onClick={() => setIndex(position)}
                  aria-label={`Foto ${position + 1} de ${photos.length}`}
                  aria-current={position === index}
                  className={cn(
                    "h-16 w-24 shrink-0 overflow-hidden rounded-md border-2",
                    position === index ? "border-primary" : "border-transparent",
                  )}
                >
                  <img src={url} alt="" loading="lazy" referrerPolicy="no-referrer" className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="grid content-start gap-3">
          <div>
            <p className="text-2xl font-semibold">{formatBrl(listing.total_price)}</p>
            <p className="text-xs text-muted-foreground">total mensal estimado</p>
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted-foreground">Aluguel</dt>
            <dd>{formatBrl(listing.rent_price)}</dd>
            <dt className="text-muted-foreground">Condomínio</dt>
            <dd>{formatBrl(listing.condo_fee)}</dd>
            <dt className="text-muted-foreground">IPTU</dt>
            <dd>{formatBrl(listing.iptu)}</dd>
            <dt className="text-muted-foreground">Quartos</dt>
            <dd>{listing.bedrooms ?? "—"}</dd>
          </dl>
          <OfficialLink url={listing.official_url} />
        </div>
      </div>

      {listing.description && (
        <div className="border-t border-border p-4">
          <h3 className="mb-2 text-sm font-medium">Descrição</h3>
          <p className="whitespace-pre-line text-sm leading-relaxed">{listing.description}</p>
        </div>
      )}
    </div>
  );
}
