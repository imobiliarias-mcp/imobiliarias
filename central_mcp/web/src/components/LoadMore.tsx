import { useCallback, useEffect, useRef } from "react";

interface LoadMoreProps {
  hasMore: boolean;
  loading: boolean;
  error: string | null;
  onLoadMore: () => void;
}

/** Infinite scroll sentinel plus a "Carregar mais" button; the button is the fallback when scrolling is not enough. */
export function LoadMore({ hasMore, loading, error, onLoadMore }: LoadMoreProps) {
  const sentinelRef = useRef<HTMLDivElement>(null);
  const visibleRef = useRef(false);
  const latest = useRef({ hasMore, loading, error, onLoadMore });
  latest.current = { hasMore, loading, error, onLoadMore };

  const requestWhileVisible = useCallback(() => {
    const current = latest.current;
    if (visibleRef.current && current.hasMore && !current.loading && current.error === null) {
      current.onLoadMore();
    }
  }, []);

  useEffect(() => {
    const node = sentinelRef.current;
    if (node === null) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        visibleRef.current = entries.some((entry) => entry.isIntersecting);
        requestWhileVisible();
      },
      { rootMargin: "600px 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [requestWhileVisible]);

  useEffect(() => {
    requestWhileVisible();
  }, [hasMore, loading, requestWhileVisible]);

  return (
    <div className="grid justify-items-center gap-2 py-2">
      <div ref={sentinelRef} aria-hidden="true" className="h-px w-full" />
      {hasMore && (
        <>
          {loading && (
            <p className="text-sm text-muted-foreground" aria-live="polite">
              Carregando mais imóveis…
            </p>
          )}
          {error !== null && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <button
            type="button"
            onClick={onLoadMore}
            disabled={loading}
            className="min-h-11 rounded-md border border-border px-4 hover:bg-muted disabled:opacity-50"
          >
            {error !== null ? "Tentar de novo" : "Carregar mais"}
          </button>
        </>
      )}
    </div>
  );
}
