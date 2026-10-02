import { errorFrom, errorMessage } from './messages.js';
import { readNativePage, type NativePage } from './pagination.js';
import type { DisplayItem, RentalProvider, SearchResponse } from './types.js';
import { isRecord } from './contracts.js';
import { serializeReference, supportsReference } from './reference-validation.js';

export function renderSearchResults(container: HTMLElement, response: SearchResponse, providers: RentalProvider[]): void {
  const providerById = new Map(providers.map((provider) => [provider.id, provider]));
  container.replaceChildren();
  response.providers.forEach((result) => {
    const provider = providerById.get(result.provider);
    if (provider) container.append(renderProviderResults(container.ownerDocument, provider, result));
  });
}

function renderProviderResults(document: Document, provider: RentalProvider, result: SearchResponse['providers'][number]): HTMLElement {
  const section = document.createElement('section');
  section.className = 'provider-results';
  section.dataset.providerResults = provider.id;
  appendHeading(document, section, provider.label);
  if (result.status === 'error') appendError(document, section, errorMessage(result.error.code));
  if (result.status === 'ok') appendListings(document, section, provider, result.display);
  if (result.status === 'ok') appendPagination(document, section, provider, result.native);
  return section;
}

function appendHeading(document: Document, section: HTMLElement, label: string): void {
  const heading = document.createElement('h2');
  heading.textContent = label;
  section.append(heading);
}

function appendError(document: Document, section: HTMLElement, message: string): void {
  const error = document.createElement('p');
  error.setAttribute('role', 'alert');
  error.textContent = message;
  section.append(error);
}

function appendListings(document: Document, section: HTMLElement, provider: RentalProvider, items: DisplayItem[]): void {
  if (items.length === 0) {
    appendEmptyMessage(document, section);
    return;
  }
  items.forEach((item) => section.append(renderListing(document, provider, item)));
}

function appendEmptyMessage(document: Document, section: HTMLElement): void {
  const message = document.createElement('p');
  message.textContent = 'Nenhum imóvel encontrado para este provedor.';
  section.append(message);
}

function renderListing(document: Document, provider: RentalProvider, item: DisplayItem): HTMLElement {
  const article = document.createElement('article');
  article.className = 'listing-card';
  appendItemText(document, article, item.title, 'h3');
  appendItemText(document, article, item.location, 'p', 'Localização');
  appendItemText(document, article, item.price, 'p', 'Preço');
  const listingUrl = safeProviderUrl(item.url, provider);
  if (listingUrl) article.append(createActionButton(document, 'open-link', 'Abrir anúncio', listingUrl, provider.id));
  if (provider.capabilities.detail && supportsReference(item.reference, provider.reference)) {
    article.append(createActionButton(document, 'detail', 'Ver detalhes', item.reference!, provider.id));
  }
  return article;
}

function appendItemText(document: Document, article: HTMLElement, value: unknown, tag: 'h3' | 'p', label?: string): void {
  if (value === undefined || value === null || value === '') return;
  const element = document.createElement(tag);
  const text = displayText(value);
  element.textContent = label ? `${label}: ${text}` : text;
  article.append(element);
}

function displayText(value: unknown): string {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value) ?? '';
  } catch {
    return 'Informação indisponível';
  }
}

function createActionButton(document: Document, action: string, label: string, value: unknown, providerId?: string): HTMLButtonElement {
  const button = document.createElement('button');
  button.type = 'button';
  button.dataset.action = action;
  if (providerId) button.dataset.providerId = providerId;
  if (action === 'detail') button.dataset.reference = serializeReference(value) ?? '';
  if (action === 'open-link') button.dataset.url = safeHttpUrl(value) ?? '';
  button.textContent = label;
  return button;
}

export function safeHttpUrl(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  try {
    const url = new URL(value);
    if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || !isPublicHost(url.hostname)) return undefined;
    return url.href;
  } catch {
    return undefined;
  }
}

export function safeProviderUrl(value: unknown, provider: RentalProvider): string | undefined {
  const safeUrl = safeHttpUrl(value);
  if (!safeUrl) return undefined;
  const url = new URL(safeUrl);
  if (url.hash || !hasSupportedHost(url.hostname, provider.public_hosts)) return undefined;
  return matchesDetailPath(url, provider.detail_path_pattern) ? safeUrl : undefined;
}

function hasSupportedHost(hostname: string, publicHosts: string[]): boolean {
  return publicHosts.some((host) => host.toLowerCase() === hostname.toLowerCase());
}

function matchesDetailPath(url: URL, pattern: string): boolean {
  try {
    return new RegExp(`^(?:${pattern})$`).test(`${url.pathname}${url.search}`);
  } catch {
    return false;
  }
}

function isPublicHost(hostname: string): boolean {
  const host = hostname.toLowerCase().replace(/^\[|\]$/g, '');
  if (isPrivateAddress(host) || !host.includes('.')) return false;
  return !['.localhost', '.local', '.internal', '.test', '.invalid'].some((suffix) => host.endsWith(suffix));
}

function isPrivateAddress(host: string): boolean {
  if (host === '::' || host === '::1' || host.startsWith('fc') || host.startsWith('fd') || host.startsWith('fe80:')) return true;
  const octets = host.split('.').map(Number);
  if (octets.length !== 4 || octets.some((octet) => !Number.isInteger(octet) || octet < 0 || octet > 255)) return false;
  const first = octets.at(0);
  const second = octets.at(1);
  if (first === undefined || second === undefined) return false;
  return first === 0 || first === 10 || first === 127 || first >= 224
    || first === 169 && second === 254
    || first === 172 && second >= 16 && second <= 31
    || first === 192 && second === 168
    || first === 100 && second >= 64 && second <= 127
    || first === 198 && (second === 18 || second === 19);
}

function appendPagination(document: Document, section: HTMLElement, provider: RentalProvider, native: unknown): void {
  const page = readNativePage(provider.filters, native);
  if (page) section.append(createPagination(document, provider.id, page));
}

function createPagination(document: Document, providerId: string, page: NativePage): HTMLElement {
  const nav = document.createElement('nav');
  nav.className = 'pagination-controls';
  nav.setAttribute('aria-label', `Paginação de ${providerId}`);
  nav.append(createPageButton(document, 'previous-page', 'Página anterior', providerId, page.current - 1, page.current <= 1));
  const label = document.createElement('span');
  label.textContent = page.maximum ? `Página ${page.current} de ${page.maximum}` : `Página ${page.current}`;
  nav.append(label);
  if (page.hasNext) nav.append(createPageButton(document, 'next-page', 'Próxima página', providerId, page.current + 1, false));
  return nav;
}

function createPageButton(document: Document, action: string, label: string, providerId: string, page: number, disabled: boolean): HTMLButtonElement {
  const button = document.createElement('button');
  button.type = 'button';
  button.dataset.action = action;
  button.dataset.providerId = providerId;
  button.dataset.page = String(page);
  button.textContent = label;
  button.disabled = disabled;
  return button;
}

export function renderFacetResult(container: HTMLElement, provider: RentalProvider, value: Record<string, unknown>): void {
  const section = container.ownerDocument.createElement('section');
  section.className = 'facet-results';
  section.dataset.facetResults = provider.id;
  const heading = container.ownerDocument.createElement('h3');
  heading.textContent = value.kind === 'location_suggestions' ? 'Sugestões de localização' : 'Catálogo de facetas';
  section.append(heading);
  if (value.status === 'error') appendError(container.ownerDocument, section, errorFrom(value.error));
  if (value.status === 'ok') appendFacetData(container.ownerDocument, section, value);
  container.append(section);
}

function appendFacetData(document: Document, section: HTMLElement, value: Record<string, unknown>): void {
  const content = value.display ?? value.native;
  if (content === undefined) return;
  const output = document.createElement('pre');
  output.textContent = displayText(content);
  section.append(output);
}
