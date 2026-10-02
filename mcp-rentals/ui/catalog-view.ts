import { createSchemaForm } from './schema-form.js';
import type { RentalProvider } from './types.js';

export function renderProviderCatalog(container: HTMLElement, providers: RentalProvider[]): void {
  container.replaceChildren();
  providers.forEach((provider) => container.append(createProviderPanel(container.ownerDocument, provider)));
}

function createProviderPanel(document: Document, provider: RentalProvider): HTMLElement {
  const panel = document.createElement('section');
  panel.className = 'provider-card';
  panel.dataset.providerId = provider.id;
  appendProviderHeading(document, panel, provider);
  appendAvailability(document, panel, provider);
  appendSearchFilters(document, panel, provider);
  appendFacetForm(document, panel, provider);
  appendLimitations(document, panel, provider.limitations);
  return panel;
}

function appendProviderHeading(document: Document, panel: HTMLElement, provider: RentalProvider): void {
  const heading = document.createElement('h2');
  heading.textContent = provider.label;
  const selectLabel = document.createElement('label');
  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.value = provider.id;
  checkbox.dataset.providerSelection = provider.id;
  checkbox.setAttribute('aria-label', `Selecionar ${provider.label}`);
  selectLabel.append(checkbox, document.createTextNode(' Incluir na pesquisa'));
  panel.append(heading, selectLabel);
}

function appendAvailability(document: Document, panel: HTMLElement, provider: RentalProvider): void {
  const checkbox = panel.querySelector<HTMLInputElement>('[data-provider-selection]');
  const available = provider.installation.available && provider.capabilities.search;
  if (checkbox) checkbox.disabled = !available;
  if (available) return;
  const status = document.createElement('p');
  status.className = 'provider-unavailable';
  status.textContent = 'Este provedor não está disponível para pesquisa neste ambiente.';
  panel.append(status);
}

function appendSearchFilters(document: Document, panel: HTMLElement, provider: RentalProvider): void {
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Filtros da pesquisa';
  details.append(summary, createSchemaForm(document, provider.filters, `filters-${provider.id}`));
  const form = details.querySelector('form');
  form?.setAttribute('data-search-filters', provider.id);
  panel.append(details);
}

function appendFacetForm(document: Document, panel: HTMLElement, provider: RentalProvider): void {
  if (!provider.capabilities.facets || !provider.facets) return;
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Catálogos e sugestões de localidade';
  const form = createSchemaForm(document, provider.facets, `facets-${provider.id}`);
  form.dataset.facetForm = provider.id;
  details.append(summary, form, createFacetButton(document, provider));
  panel.append(details);
}

function createFacetButton(document: Document, provider: RentalProvider): HTMLButtonElement {
  const button = document.createElement('button');
  button.type = 'button';
  button.dataset.action = 'facets';
  button.dataset.providerId = provider.id;
  button.textContent = 'Consultar facetas';
  return button;
}

function appendLimitations(document: Document, panel: HTMLElement, limitations: string[]): void {
  if (limitations.length === 0) return;
  const list = document.createElement('ul');
  list.className = 'provider-limitations';
  limitations.forEach((limitation) => {
    const item = document.createElement('li');
    item.textContent = limitation;
    list.append(item);
  });
  panel.append(list);
}
