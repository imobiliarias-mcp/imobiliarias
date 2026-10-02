import { validate_search, validate_detail, validate_facets, type SearchRequest } from '../contracts/index.js';
import { type ProviderId, specifications } from '../contracts/specifications.js';
import { worker_response, type WorkerResponse, type ProviderEntry } from '../contracts/responses.js';
import { validate_public_url } from '../contracts/urls.js';
import { normalize_error } from './errors.js';
import { invalid_result } from './results.js';
import { budgeted_search_result, budgeted_single_result } from './budget.js';

export type WorkerRunner = (provider: ProviderId, operation: string, arguments_: Record<string, unknown>, signal: AbortSignal) => Promise<WorkerResponse>;
export type ProgressReporter = (provider: string, completed: number, total: number) => Promise<void>;
/** Validate full calls before launching providers and preserve per-source semantics. */
export class RentalService {
  constructor(private runner: WorkerRunner, private limits = {deadline: 180000, aggregate: 8 * 1024 * 1024}) {}
  async search(value: unknown, parent: AbortSignal, progress?: ProgressReporter) {
    let request;
    try { request = validate_search(value); } catch { return invalid_result(); }
    const deadline = AbortSignal.timeout(this.limits.deadline);
    const signal = AbortSignal.any([parent, deadline]);
    const entries = await this.execute_search(request.requests, signal, progress);
    if (signal.aborted) throw new Error(parent.aborted ? 'cancelled' : 'timeout');
    return budgeted_search_result(entries, this.limits.aggregate);
  }
  async detail(value: unknown, parent: AbortSignal) {
    let request;
    try { request = validate_detail(value); } catch { return invalid_result(); }
    const signal = this.call_signal(parent);
    const entry = await this.execute(request.provider, 'detail', {reference: request.reference}, signal);
    if (signal.aborted) throw new Error(parent.aborted ? 'cancelled' : 'timeout');
    return budgeted_single_result(entry, this.limits.aggregate);
  }
  async facets(value: unknown, parent: AbortSignal) {
    let request;
    try { request = validate_facets(value); }
    catch (error) { return invalid_result(error instanceof Error && error.message === 'unsupported_capability' ? 'unsupported_capability' : 'invalid_input'); }
    const signal = this.call_signal(parent);
    const entry = await this.execute(request.provider, 'facets', request.request, signal);
    if (signal.aborted) throw new Error(parent.aborted ? 'cancelled' : 'timeout');
    return budgeted_single_result(entry, this.limits.aggregate, request.provider === 'vivareal' ? 'location_suggestions' : 'catalog');
  }
  private execute_search(requests: SearchRequest[], signal: AbortSignal, progress?: ProgressReporter): Promise<ProviderEntry[]> {
    const budget = {bytes: 0, completed: 0};
    return Promise.all(requests.map(async item => {
      const entry = await this.execute(item.provider, 'search', item.filters, signal);
      budget.completed++;
      if (progress && !signal.aborted) await progress(item.provider, budget.completed, requests.length);
      return this.bound_entry(entry, budget);
    }));
  }
  private call_signal(parent: AbortSignal): AbortSignal {
    return AbortSignal.any([parent, AbortSignal.timeout(this.limits.deadline)]);
  }
  private async execute(provider: ProviderId, operation: string, arguments_: Record<string, unknown>, signal: AbortSignal): Promise<ProviderEntry> {
    try {
      const response = worker_response.parse(await this.runner(provider, operation, arguments_, signal));
      if (response.status === 'error') return {provider, status: 'error', error: response.error};
      this.validate_links(provider, response.display);
      return {provider, status: 'ok', native: response.native, display: response.display};
    } catch (error) { return {provider, status: 'error', error: normalize_error(error)}; }
  }
  private validate_links(provider: ProviderId, display: {url?: string}[]): void {
    const specification = specifications().find(item => item.id === provider)!;
    for (const item of display) if (item.url) validate_public_url(item.url, specification);
  }
  private bound_entry(entry: ProviderEntry, budget: {bytes: number}): ProviderEntry {
    budget.bytes += Buffer.byteLength(JSON.stringify(entry));
    if (budget.bytes > this.limits.aggregate) return {provider: entry.provider, status: 'error', error: normalize_error(new Error('output_limit'))};
    return entry;
  }
}
