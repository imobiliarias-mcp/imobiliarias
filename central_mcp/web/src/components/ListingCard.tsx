import { Badge } from "@/components/ui/badge";
import { PhotoCarousel } from "@/components/PhotoCarousel";
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
      <PhotoCarousel
        photos={listing.photos}
        fallback={listing.cover_photo}
        title={listing.title ?? "Imóvel"}
        onOpen={() => onOpen(listing)}
        overlay={<Badge className="pointer-events-none absolute left-2 top-2 bg-card/90">{providerLabel(listing.provider)}</Badge>}
      />
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
