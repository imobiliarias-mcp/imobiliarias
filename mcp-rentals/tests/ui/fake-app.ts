export interface RecordedCall {
  name: string;
  arguments: Record<string, unknown>;
  timeout: number;
  signal?: AbortSignal;
}

type Listener = (params: unknown) => void;

export class FakeRentalApp {
  readonly calls: RecordedCall[] = [];
  readonly openedLinks: string[] = [];
  readonly listeners = new Map<string, Set<Listener>>();
  readonly responses = new Map<string, unknown[]>();
  teardown?: () => void;
  connectCount = 0;
  hostContext: Record<string, unknown> = {};

  subscribe(event: string, listener: Listener): () => void {
    const group = this.listeners.get(event) ?? new Set<Listener>();
    group.add(listener);
    this.listeners.set(event, group);
    return () => group.delete(listener);
  }

  async callServerTool(name: string, args: Record<string, unknown>, options: { timeout: number; signal?: AbortSignal }): Promise<unknown> {
    this.calls.push({ name, arguments: args, timeout: options.timeout, signal: options.signal });
    const response = this.responses.get(name)?.shift();
    return response instanceof Promise ? response : Promise.resolve(response);
  }

  async openLink(url: string): Promise<{ isError?: boolean }> {
    this.openedLinks.push(url);
    return {};
  }

  getHostContext(): Record<string, unknown> {
    return this.hostContext;
  }

  setTeardownHandler(handler: () => void): void {
    this.teardown = handler;
  }

  async connect(): Promise<void> {
    this.connectCount += 1;
  }

  queue(name: string, ...responses: unknown[]): void {
    this.responses.set(name, [...responses]);
  }

  notify(event: string, params: unknown): void {
    this.listeners.get(event)?.forEach((listener) => listener(params));
  }
}
