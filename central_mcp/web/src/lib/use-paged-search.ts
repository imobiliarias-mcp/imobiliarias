import { useCallback, useEffect, useRef, useState } from "react";
import { searchListings } from "@/lib/api";
import { readCachedResults, writeCachedResults } from "@/lib/storage";
import type { Listing, SearchResponse } from "@/types";

export interface PagedSearch {
  /** Latest server response: provider outcomes, paging figures and the hidden-count. */
  response: SearchResponse | null;
  /** Every listing loaded so far, in server order, without duplicates. */
  items: Listing[];
  /** First page in flight (nothing to show yet). */
  loading: boolean;
  /** A later page in flight. */
  loadingMore: boolean;
  error: string | null;
  loadMoreError: string | null;
  elapsedMs: number | null;
  loadMore: () => void;
  /** Re-run the first page asking the server for fresh provider data. */
  retry: () => void;
}

interface PagedState {
  response: SearchResponse | null;
  items: Listing[];
}

const EMPTY_STATE: PagedState = { response: null, items: [] };

/** First page of a query (cached per browser) plus on-demand later pages, for one filter and sort set. */
export function usePagedSearch(query: string, onFirstPage: () => void): PagedSearch {
  const [state, setState] = useState<PagedState>(EMPTY_STATE);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState<number | null>(null);
  const [retryToken, setRetryToken] = useState(0);

  const stateRef = useRef(state);
  const queryRef = useRef(query);
  const loadingRef = useRef(false);
  const loadingMoreRef = useRef(false);
  const generation = useRef(0);
  const pagingAbort = useRef<AbortController | null>(null);
  const refreshNext = useRef(false);
  const onFirstPageRef = useRef(onFirstPage);
  stateRef.current = state;
  queryRef.current = query;
  onFirstPageRef.current = onFirstPage;

  useEffect(() => {
    const controller = new AbortController();
    const current = ++generation.current;
    pagingAbort.current?.abort();
    const forceRefresh = refreshNext.current;
    refreshNext.current = false;
    const cached = forceRefresh ? null : readCachedResults<SearchResponse>(query);
    setState(cached && isPagedResponse(cached) ? { response: cached, items: cached.results } : EMPTY_STATE);
    setError(null);
    setLoadMoreError(null);
    setLoadingMore(false);
    loadingMoreRef.current = false;
    setLoading(true);
    loadingRef.current = true;
    const startedAt = performance.now();
    searchListings(query, 1, controller.signal, forceRefresh)
      .then((response) => {
        if (current !== generation.current) {
          return;
        }
        writeCachedResults(query, response);
        setState({ response, items: response.results });
        setElapsedMs(performance.now() - startedAt);
        onFirstPageRef.current();
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted && current === generation.current) {
          setError(describeError(cause, "Falha na busca. Tente novamente."));
        }
      })
      .finally(() => {
        if (current === generation.current) {
          loadingRef.current = false;
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [query, retryToken]);

  const loadMore = useCallback(() => {
    const snapshot = stateRef.current.response;
    if (!snapshot?.has_more || loadingRef.current || loadingMoreRef.current) {
      return;
    }
    const current = generation.current;
    const controller = new AbortController();
    pagingAbort.current = controller;
    loadingMoreRef.current = true;
    setLoadingMore(true);
    setLoadMoreError(null);
    searchListings(queryRef.current, snapshot.page + 1, controller.signal)
      .then((response) => {
        if (current !== generation.current) {
          return;
        }
        setState((previous) => ({ response, items: mergeListings(previous.items, response.results) }));
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted && current === generation.current) {
          setLoadMoreError(describeError(cause, "Não foi possível carregar mais imóveis."));
        }
      })
      .finally(() => {
        if (current === generation.current) {
          loadingMoreRef.current = false;
          setLoadingMore(false);
        }
      });
  }, []);

  const retry = useCallback(() => {
    refreshNext.current = true;
    setRetryToken((value) => value + 1);
  }, []);

  return {
    response: state.response,
    items: state.items,
    loading,
    loadingMore,
    error,
    loadMoreError,
    elapsedMs,
    loadMore,
    retry,
  };
}

/** Append a later page, skipping listings already shown (a refreshed server snapshot can overlap). */
export function mergeListings(existing: Listing[], incoming: Listing[]): Listing[] {
  const seen = new Set(existing.map(resultKey));
  const fresh = incoming.filter((listing) => !seen.has(resultKey(listing)));
  return [...existing, ...fresh];
}

export function resultKey(listing: Listing): string {
  return `${listing.provider}-${listing.code ?? listing.official_url ?? listing.title}`;
}

function isPagedResponse(value: SearchResponse): boolean {
  return typeof value.total === "number" && typeof value.has_more === "boolean" && typeof value.page === "number";
}

function describeError(cause: unknown, fallback: string): string {
  if (cause instanceof Error && cause.message) {
    return cause.message;
  }
  return fallback;
}
