import { useState } from "react";

/** Default aspect ratio for every listing cover (cards, rows and carousel slides). */
export const COVER_ASPECT = "aspect-[4/3]";

interface CoverImageProps {
  src: string | null;
  alt: string;
  /** When false, nothing is downloaded: a blank block keeps the slot until the photo is needed. */
  deferred?: boolean;
}

/** Photo with a neutral placeholder when there is no URL or the image fails to load. */
export function CoverImage({ src, alt, deferred = false }: CoverImageProps) {
  const [failed, setFailed] = useState(false);
  if (deferred) {
    return <span aria-hidden="true" className="block h-full w-full bg-muted" />;
  }
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
