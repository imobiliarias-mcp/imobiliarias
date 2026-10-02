import type { RentalAppPort } from './app-port.js';
import { cancelHostRequest, applyHostToolInput, applyHostToolResult } from './host-events.js';
import { createUiState, runCatalog, runSearch, setStatus, type RentalUiState } from './operations.js';
import { openListingLink, runDetail, runFacets } from './provider-actions.js';
import { parseReference } from './reference-validation.js';

export interface RentalAppLifecycle {
  ready: Promise<void>;
  destroy: () => void;
}

type ConnectHost = () => Promise<void>;

export function setupRentalApp(root: HTMLElement, app: RentalAppPort, connect: ConnectHost): RentalAppLifecycle {
  renderShell(root);
  const state = createUiState();
  const AbortControllerConstructor = root.ownerDocument.defaultView?.AbortController ?? AbortController;
  const lifetime = new AbortControllerConstructor();
  const unsubscribe = registerHostHandlers(root, app, state);
  registerDomHandlers(root, app, state, lifetime.signal);
  app.setTeardownHandler(() => dispose(root, state, lifetime, unsubscribe));
  const ready = connectAndLoad(root, app, state, lifetime.signal, connect);
  return { ready, destroy: () => dispose(root, state, lifetime, unsubscribe) };
}

function renderShell(root: HTMLElement): void {
  const document = root.ownerDocument;
  const catalog = createRegion(document, 'providers', 'Imobiliárias');
  const results = createRegion(document, 'results', 'Resultados');
  root.replaceChildren(createHeading(document), createIntroduction(document), createStatusElement(document), catalog, createSearchButton(document), results);
}

function createHeading(document: Document): HTMLElement {
  const heading = document.createElement('h1');
  heading.textContent = 'Pesquisa de imóveis para aluguel';
  return heading;
}

function createIntroduction(document: Document): HTMLElement {
  const introduction = document.createElement('p');
  introduction.textContent = 'Escolha as imobiliárias e os filtros que cada provedor disponibiliza.';
  return introduction;
}

function createStatusElement(document: Document): HTMLElement {
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  status.setAttribute('aria-atomic', 'true');
  status.tabIndex = -1;
  return status;
}

function createSearchButton(document: Document): HTMLButtonElement {
  const search = document.createElement('button');
  search.type = 'button';
  search.dataset.action = 'search';
  search.textContent = 'Pesquisar imóveis';
  search.accessKey = 'p';
  search.setAttribute('aria-keyshortcuts', 'Alt+P');
  return search;
}

function createRegion(document: Document, name: string, title: string): HTMLElement {
  const region = document.createElement('section');
  region.dataset.region = name;
  region.setAttribute('aria-label', title);
  return region;
}

function registerHostHandlers(root: HTMLElement, app: RentalAppPort, state: RentalUiState): Array<() => void> {
  return [
    app.subscribe('hostcontextchanged', (params) => applyHostContext(root, params)),
    app.subscribe('toolinput', (params) => applyHostToolInput(root, state, params)),
    app.subscribe('toolresult', (params) => applyHostToolResult(root, state, params)),
    app.subscribe('toolcancelled', () => cancelHostRequest(root, state)),
  ];
}

function applyHostContext(root: HTMLElement, value: unknown): void {
  if (!isRecord(value)) return;
  applyTheme(root.ownerDocument.documentElement, value.theme);
  applyHostVariables(root.ownerDocument.documentElement, value.styles);
}

function applyTheme(root: HTMLElement, theme: unknown): void {
  if (theme !== 'light' && theme !== 'dark') return;
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
}

function applyHostVariables(root: HTMLElement, value: unknown): void {
  if (!isRecord(value) || !isRecord(value.variables)) return;
  Object.entries(value.variables).forEach(([name, content]) => {
    if (name.startsWith('--') && typeof content === 'string') root.style.setProperty(name, content);
  });
}

function registerDomHandlers(root: HTMLElement, app: RentalAppPort, state: RentalUiState, signal: AbortSignal): void {
  root.addEventListener('click', (event) => handleClick(root, app, state, event), { signal });
  root.addEventListener('submit', (event) => {
    event.preventDefault();
    void runSearch(root, app, state);
  }, { signal });
}

function handleClick(root: HTMLElement, app: RentalAppPort, state: RentalUiState, event: Event): void {
  const button = (event.target as Element | null)?.closest<HTMLButtonElement>('button[data-action]');
  if (!button || !root.contains(button)) return;
  const providerId = button.dataset.providerId;
  if (button.dataset.action === 'search') void runSearch(root, app, state);
  if (button.dataset.action === 'detail' && providerId) void runDetail(root, app, state, providerId, parseReference(button.dataset.reference));
  if (button.dataset.action === 'open-link' && providerId) void openListingLink(root, app, state, providerId, button.dataset.url);
  if (button.dataset.action === 'facets' && providerId) requestFacets(root, app, state, providerId);
  if (isPageAction(button.dataset.action) && providerId) requestPage(root, app, state, providerId, Number(button.dataset.page));
}

function requestFacets(root: HTMLElement, app: RentalAppPort, state: RentalUiState, providerId: string): void {
  const provider = state.providers.find((item) => item.id === providerId);
  if (provider) void runFacets(root, app, state, provider);
}

function requestPage(root: HTMLElement, app: RentalAppPort, state: RentalUiState, providerId: string, page: number): void {
  if (!Number.isInteger(page) || page < 1 || !state.pageFilters.has(providerId)) return;
  void runSearch(root, app, state, [providerId], { providerId, page });
}

function isPageAction(action?: string): boolean {
  return action === 'next-page' || action === 'previous-page';
}

async function connectAndLoad(root: HTMLElement, app: RentalAppPort, state: RentalUiState, signal: AbortSignal, connect: ConnectHost): Promise<void> {
  try {
    await connect();
    if (signal.aborted || state.disposed) return;
    applyHostContext(root, app.getHostContext());
    await runCatalog(root, app, state, signal);
  } catch {
    if (!signal.aborted && !state.disposed) setStatus(root, 'Não foi possível conectar ao host MCP. Recarregue este painel.', true);
  }
}

function dispose(root: HTMLElement, state: RentalUiState, lifetime: AbortController, unsubscribe: Array<() => void>): void {
  if (state.disposed) return;
  state.disposed = true;
  state.controllers.forEach((controller) => controller.abort());
  state.controllers.clear();
  lifetime.abort();
  unsubscribe.forEach((remove) => remove());
  setStatus(root, 'Painel encerrado.');
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
