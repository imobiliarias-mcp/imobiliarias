import type { ToolResponse } from './types.js';

export type HostEvent = 'toolinput' | 'toolresult' | 'toolcancelled' | 'hostcontextchanged';

export interface HostContextView {
  theme?: string;
  styles?: { variables?: Record<string, string> };
}

export interface RentalAppPort {
  callServerTool(name: string, arguments_: Record<string, unknown>, options: { timeout: number; signal: AbortSignal }): Promise<ToolResponse>;
  openLink(url: string): Promise<{ isError?: boolean }>;
  subscribe(event: HostEvent, listener: (params: unknown) => void): () => void;
  getHostContext(): HostContextView | undefined;
  setTeardownHandler(listener: () => void): void;
}
