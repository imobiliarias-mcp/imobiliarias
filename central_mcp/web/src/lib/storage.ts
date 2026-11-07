/** Per-browser conveniences only: a failing or blocked storage must never break the page. */

const LAST_SEARCH_KEY = "central-mcp:last-search";
const RESULTS_PREFIX = "central-mcp:results-v2:";
const RESULTS_INDEX_KEY = "central-mcp:results-index-v2";
const RESULTS_TTL_MS = 15 * 60 * 1000;
const RESULTS_MAX_ENTRIES = 12;

export function loadLastSearch(): string | null {
  try {
    return window.localStorage.getItem(LAST_SEARCH_KEY);
  } catch {
    return null;
  }
}

export function saveLastSearch(search: string): void {
  safely(() => window.localStorage.setItem(LAST_SEARCH_KEY, search));
}

export function readCachedResults<T>(query: string, now: number = Date.now()): T | null {
  try {
    const raw = window.localStorage.getItem(RESULTS_PREFIX + query);
    if (raw === null) {
      return null;
    }
    const entry = JSON.parse(raw) as { savedAt: number; value: T };
    return now - entry.savedAt <= RESULTS_TTL_MS ? entry.value : null;
  } catch {
    return null;
  }
}

export function writeCachedResults<T>(query: string, value: T, now: number = Date.now()): void {
  safely(() => {
    window.localStorage.setItem(RESULTS_PREFIX + query, JSON.stringify({ savedAt: now, value }));
    rememberKey(query);
  });
}

function rememberKey(query: string): void {
  const index = readIndex().filter((key) => key !== query);
  index.push(query);
  while (index.length > RESULTS_MAX_ENTRIES) {
    const oldest = index.shift();
    if (oldest !== undefined) {
      window.localStorage.removeItem(RESULTS_PREFIX + oldest);
    }
  }
  window.localStorage.setItem(RESULTS_INDEX_KEY, JSON.stringify(index));
}

function readIndex(): string[] {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(RESULTS_INDEX_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function safely(action: () => void): void {
  try {
    action();
  } catch {
    // Storage full or blocked: the page works without it.
  }
}
