interface Job {provider: string; signal: AbortSignal; start: () => void; reject: (error: Error) => void; cancel: () => void}
/** Shares global and per-origin concurrency across all MCP calls and factories. */
export class WorkerLimiter {
  private state = {active: new Set<string>(), queue: [] as Job[], closed: false};
  constructor(private maximum: number) {
    if (!Number.isSafeInteger(maximum) || maximum < 1) throw new Error('invalid_input');
  }
  run<T>(provider: string, signal: AbortSignal, operation: () => Promise<T>): Promise<T> {
    if (this.state.closed) return Promise.reject(new Error('shutdown'));
    if (signal.aborted) return Promise.reject(new Error('cancelled'));
    return new Promise<T>((resolve, reject) => {
      const job: Job = {provider, signal, reject, cancel: () => this.cancel(job), start: () => this.start(job, operation, resolve, reject)};
      signal.addEventListener('abort', job.cancel, {once: true});
      this.state.queue.push(job);
      this.drain();
    });
  }
  close(): void {
    this.state.closed = true;
    for (const job of this.state.queue.splice(0)) this.remove(job, 'shutdown');
  }
  private start<T>(job: Job, operation: () => Promise<T>, resolve: (value: T) => void, reject: (error: unknown) => void): void {
    job.signal.removeEventListener('abort', job.cancel);
    this.state.active.add(job.provider);
    void Promise.resolve().then(operation).then(resolve, reject).finally(() => {
      this.state.active.delete(job.provider);
      this.drain();
    });
  }
  private drain(): void {
    if (this.state.closed || this.state.active.size >= this.maximum) return;
    const index = this.state.queue.findIndex(job => !this.state.active.has(job.provider));
    if (index < 0) return;
    const [job] = this.state.queue.splice(index, 1);
    job!.start();
    this.drain();
  }
  private cancel(job: Job): void {
    const index = this.state.queue.indexOf(job);
    if (index < 0) return;
    this.state.queue.splice(index, 1);
    this.remove(job, 'cancelled');
    this.drain();
  }
  private remove(job: Job, code: string): void {
    job.signal.removeEventListener('abort', job.cancel);
    job.reject(new Error(code));
  }
}
