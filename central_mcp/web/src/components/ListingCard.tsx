import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { formatBrl, locationLabel, providerLabel } from "@/lib/format";
import type { Listing } from "@/types";

interface ListingCardProps {
  listing: Listing;
  onOpen: (listing: Listing) => void;
}

/** One listing: cover photo, total monthly cost, key facts and the official link. */
export function ListingCard({ listing, onOpen }: ListingCardProps) {
  return (
    <Card className="flex flex-col overflow-hidden">
      <button
        type="button"
        onClick={() => onOpen(listing)}
        className="group relative aspect-[4/3] w-full bg-muted text-left"
        aria-label={`Ver detalhes: ${listing.title ?? "imóvel"}`}
      >
        <CoverImage src={listing.cover_photo} alt={listing.title ?? "Foto do imóvel"} />
        <Badge className="absolute left-2 top-2 bg-card/90">{providerLabel(listing.provider)}</Badge>
      </button>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <p className="text-xs text-muted-foreground">{locationLabel(listing)}</p>
        <h3 className="line-clamp-2 text-sm font-medium">{listing.title ?? "Imóvel sem título"}</h3>
        <div>
          <p className="text-xl font-semibold">{formatBrl(listing.total_price)}</p>
          <p className="text-xs text-muted-foreground">
            aluguel {formatBrl(listing.rent_price)}
            {listing.condo_fee ? ` · condomínio ${formatBrl(listing.condo_fee)}` : ""}
            {listing.iptu ? ` · IPTU ${formatBrl(listing.iptu)}` : ""}
          </p>
        </div>
        <div className="mt-auto flex items-center justify-between gap-2 pt-2">
          <span className="text-xs text-muted-foreground">
            {listing.bedrooms !== null ? `${listing.bedrooms} quarto(s)` : ""}
          </span>
          <OfficialLink url={listing.official_url} />
        </div>
      </div>
    </Card>
  );
}

interface CoverImageProps {
  src: string | null;
  alt: string;
}

/** Photo with a neutral placeholder when there is no URL or the image fails to load. */
export function CoverImage({ src, alt }: CoverImageProps) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <span className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
        Sem foto
      </span>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className="h-full w-full object-cover transition group-hover:scale-105"
    />
  );
}

interface OfficialLinkProps {
  url: string | null;
}

/** Link to the agency's own listing page; disabled when the provider gave no valid URL. */
export function OfficialLink({ url }: OfficialLinkProps) {
  if (!url) {
    return <span className="text-xs text-muted-foreground">Link indisponível</span>;
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-sm font-medium text-primary underline-offset-4 hover:underline"
    >
      Ver no site oficial ↗
    </a>
  );
}
