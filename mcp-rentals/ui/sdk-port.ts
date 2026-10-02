import type { App, AppEventMap } from '@modelcontextprotocol/ext-apps';
import type { HostContextView, HostEvent, RentalAppPort } from './app-port.js';
import type { ToolResponse } from './types.js';

type HostListener = (params: unknown) => void;

export function createSdkPort(app: App): RentalAppPort {
  return {
    callServerTool: (name, arguments_, options) => callTool(app, name, arguments_, options),
    openLink: (url) => app.openLink({ url }),
    subscribe: (event, listener) => subscribe(app, event, listener),
    getHostContext: () => hostContext(app),
    setTeardownHandler: (listener) => setTeardown(app, listener),
  };
}

async function callTool(app: App, name: string, arguments_: Record<string, unknown>, options: { timeout: number; signal: AbortSignal }): Promise<ToolResponse> {
  return app.callServerTool({ name, arguments: arguments_ }, options);
}

function subscribe(app: App, event: HostEvent, listener: HostListener): () => void {
  if (event === 'toolinput') return subscribeAppEvent(app, event, listener);
  if (event === 'toolresult') return subscribeAppEvent(app, event, listener);
  if (event === 'toolcancelled') return subscribeAppEvent(app, event, listener);
  return subscribeAppEvent(app, event, listener);
}

function subscribeAppEvent<Event extends keyof AppEventMap>(app: App, event: Event, listener: HostListener): () => void {
  const handler = listener as (params: AppEventMap[Event]) => void;
  app.addEventListener(event, handler);
  return () => app.removeEventListener(event, handler);
}

function hostContext(app: App): HostContextView | undefined {
  const context = app.getHostContext();
  if (!context) return undefined;
  return { theme: context.theme, styles: hostStyles(context.styles?.variables) };
}

function hostStyles(variables?: Record<string, string | undefined>): HostContextView['styles'] {
  if (!variables) return undefined;
  const entries = Object.entries(variables).filter((entry): entry is [string, string] => typeof entry[1] === 'string');
  return { variables: Object.fromEntries(entries) };
}

function setTeardown(app: App, listener: () => void): void {
  app.onteardown = () => {
    listener();
    return {};
  };
}
