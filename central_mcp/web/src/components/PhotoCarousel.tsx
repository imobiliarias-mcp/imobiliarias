import { useRef, useState, type ReactNode } from "react";
import { CoverImage, COVER_ASPECT } from "@/components/CoverImage";
import { cn } from "@/lib/utils";

interface PhotoCarouselProps {
  photos: string[];
  fallback: string | null;
  title: string;
  onOpen: () => void;
  overlay?: ReactNode;
}

/** Swipeable 4:3 photo strip for a listing card; arrows and dots for mouse users. */
export function PhotoCarousel({ photos, fallback, title, onOpen, overlay }: PhotoCarouselProps) {
  const slides: Array<string | null> = photos.length > 0 ? photos : [fallback];
  const trackRef = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);

  function handleScroll() {
    const track = trackRef.current;
    if (!track || track.clientWidth === 0) {
      return;
    }
    setIndex(Math.round(track.scrollLeft / track.clientWidth));
  }

  function step(direction: -1 | 1) {
    trackRef.current?.scrollBy({ left: direction * (trackRef.current.clientWidth), behavior: "smooth" });
  }

  return (
    <div className={cn("group relative overflow-hidden bg-muted", COVER_ASPECT)}>
      <div
        ref={trackRef}
        onScroll={handleScroll}
        className="flex h-full snap-x snap-mandatory overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {slides.map((src, position) => (
          <button
            key={src ?? `empty-${position}`}
            type="button"
            onClick={onOpen}
            aria-label={`Ver detalhes: ${title}`}
            className="relative h-full w-full shrink-0 snap-start"
          >
            <CoverImage src={src} alt={title} />
          </button>
        ))}
      </div>
      {slides.length > 1 && (
        <>
          <button
            type="button"
            onClick={() => step(-1)}
            disabled={index === 0}
            aria-label="Foto anterior"
            className="absolute left-1 top-1/2 flex size-11 -translate-y-1/2 items-center justify-center rounded-full bg-card/90 text-lg opacity-100 shadow disabled:opacity-0 md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100"
          >
            ‹
          </button>
          <button
            type="button"
            onClick={() => step(1)}
            disabled={index >= slides.length - 1}
            aria-label="Próxima foto"
            className="absolute right-1 top-1/2 flex size-11 -translate-y-1/2 items-center justify-center rounded-full bg-card/90 text-lg opacity-100 shadow disabled:opacity-0 md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100"
          >
            ›
          </button>
          <div className="pointer-events-none absolute inset-x-0 bottom-2 flex justify-center gap-1" aria-hidden="true">
            {slides.map((_, position) => (
              <span
                key={position}
                className={cn("size-1.5 rounded-full", position === index ? "bg-white" : "bg-white/50")}
              />
            ))}
          </div>
        </>
      )}
      {overlay}
    </div>
  );
}
