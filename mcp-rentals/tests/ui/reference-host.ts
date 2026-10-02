import { AppBridge, PostMessageTransport } from '@modelcontextprotocol/ext-apps/app-bridge';

interface RecordedCall {
  name: string;
  arguments: Record<string, unknown>;
}

interface ReferenceHostApi {
  ready: Promise<void>;
  calls: RecordedCall[];
  openedLinks: string[];
  initialized: boolean;
  sendToolInput: (arguments_: Record<string, unknown>) => Promise<void>;
  delayNextSearch: () => void;
  finishSearch: () => void;
  teardown: () => Promise<Record<string, unknown>>;
}

const providerCatalog = {
  providers: [
    {
      id: 'alfa',
      label: 'Imobiliária Alfa',
      filters: { type: 'object', properties: {
        city: { type: 'string', title: 'Cidade' },
        bedrooms: { type: 'integer', title: 'Quartos', minimum: 1 },
        page_number: { type: 'integer', title: 'Página', minimum: 1 },
      } },
      reference: { type: 'string', pattern: '^A-[0-9]+$' },
      facets: { type: 'object', properties: { selector: { type: 'string', enum: ['cities', 'neighborhoods'] } } },
      capabilities: { search: true, detail: true, facets: true },
      limitations: ['Somente aluguel.'],
      installation: { available: true },
      public_hosts: ['imoveis.example'],
      detail_path_pattern: '^/a-[0-9]+$',
    },
    {
      id: 'beta',
      label: 'Imobiliária Beta',
      filters: { type: 'object', properties: { city: { type: 'string', title: 'Cidade' } } },
      reference: { type: 'string' },
      facets: null,
      capabilities: { search: true, detail: true, facets: false },
      limitations: [],
      installation: { available: true },
      public_hosts: ['beta.example'],
      detail_path_pattern: '^/.*$',
    },
  ],
};

declare global {
  interface Window {
    referenceHost: ReferenceHostApi;
  }
}

const appFrame = document.querySelector<HTMLIFrameElement>('#app-frame');
if (!appFrame?.contentWindow) throw new Error('Reference host app iframe is missing.');

const calls: RecordedCall[] = [];
const openedLinks: string[] = [];
let initialized = false;
const bridge = new AppBridge(
  null,
  { name: 'Local MCP Apps reference host', version: '1.0.0' },
  { openLinks: {}, serverTools: {} },
  { hostContext: { theme: 'light' } },
);
bridge.addEventListener('initialized', () => { initialized = true; });
const transport = new PostMessageTransport(appFrame.contentWindow, appFrame.contentWindow);
const ready = bridge.connect(transport).then(() => {
  appFrame.src = '/dist/ui/mcp-app.html';
});
let delaySearch = false;
let resolveDelayedSearch: (() => void) | undefined;
let delayedSearch: Promise<void> | undefined;

bridge.oncalltool = async ({ name, arguments: arguments_ }) => {
  const recordedArguments = arguments_ ?? {};
  calls.push({ name, arguments: recordedArguments });
  if (name === 'list_rental_providers') return success(providerCatalog);
  if (name === 'search_rentals') return search(recordedArguments);
  if (name === 'get_rental_detail') return detail();
  if (name === 'get_rental_facets') return facets();
  return failure('unknown_tool', 'Offline fixture does not recognize this tool.');
};

bridge.onopenlink = async ({ url }) => {
  openedLinks.push(url);
  return {};
};

window.referenceHost = {
  ready,
  calls,
  openedLinks,
  get initialized() { return initialized; },
  sendToolInput: (arguments_) => bridge.sendToolInput({ arguments: arguments_ }),
  delayNextSearch: () => {
    delaySearch = true;
    delayedSearch = new Promise((resolve) => { resolveDelayedSearch = resolve; });
  },
  finishSearch: () => resolveDelayedSearch?.(),
  teardown: () => bridge.teardownResource({}),
};

async function search(arguments_: Record<string, unknown>): Promise<ReturnType<typeof success>> {
  if (delaySearch) {
    delaySearch = false;
    await delayedSearch;
    delayedSearch = undefined;
    resolveDelayedSearch = undefined;
  }
  const requests = Array.isArray(arguments_.requests) ? arguments_.requests : [];
  const providers = requests.flatMap(searchProvider);
  const status = providers.some((provider) => provider.status === 'error') ? 'partial' : 'ok';
  return success({ status, providers });
}

function searchProvider(value: unknown): Array<Record<string, unknown>> {
  if (!isRecord(value) || typeof value.provider !== 'string') return [];
  if (value.provider === 'beta') {
    return [{ provider: value.provider, status: 'error', error: { code: 'timeout', message: '/private/path secret-token' } }];
  }
  if (value.provider !== 'alfa') return [{ provider: value.provider, status: 'ok', native: {}, display: [] }];
  return [{
    provider: value.provider,
    status: 'ok',
    native: { current_page: 1, max_pages: 2 },
    display: [{
      reference: 'A-31',
      title: '<img src="https://attacker.example/pixel" onerror="window.__bundleHostXss=1">',
      location: 'Centro, Timóteo',
      price: 1450,
      url: 'https://imoveis.example/a-31',
    }],
  }];
}

function detail(): ReturnType<typeof success> {
  return success({
    status: 'ok',
    display: { title: '<img src=x onerror="window.__bundleHostXss=1"> detalhe' },
  });
}

function facets(): ReturnType<typeof success> {
  return success({ status: 'ok', kind: 'catalog', display: { cities: ['Timóteo', 'Ipatinga'] } });
}

function success(structuredContent: Record<string, unknown>): { content: Array<{ type: 'text'; text: string }>; structuredContent: Record<string, unknown> } {
  return { content: [], structuredContent };
}

function failure(code: string, message: string): { content: Array<{ type: 'text'; text: string }>; isError: true; structuredContent: { code: string; message: string } } {
  return { content: [{ type: 'text', text: message }], isError: true, structuredContent: { code, message } };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
