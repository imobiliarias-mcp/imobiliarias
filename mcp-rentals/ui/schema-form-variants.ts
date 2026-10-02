import type { JsonSchema } from './schema-form.js';

type AppendSchemaFields = (document: Document, parent: HTMLElement, schema: JsonSchema, prefix: string, path: string, excludedProperty?: string) => void;

export function appendSchemaVariant(document: Document, form: HTMLFormElement, variants: readonly JsonSchema[], prefix: string, appendFields: AppendSchemaFields): void {
  const property = variantProperty(variants);
  if (!property) return;
  const control = createVariantControl(document, variants, property, prefix);
  const fields = document.createElement('div');
  fields.dataset.schemaVariantFields = '';
  control.addEventListener('change', () => renderVariantFields(document, fields, variants, prefix, property, control.value, appendFields));
  form.append(createVariantLabel(document, control, property), control, fields);
}

function createVariantControl(document: Document, variants: readonly JsonSchema[], property: string, prefix: string): HTMLSelectElement {
  const control = document.createElement('select');
  control.id = `${prefix}-${property}`;
  control.name = property;
  control.required = true;
  control.dataset.schemaPath = property;
  control.dataset.schemaType = 'string';
  control.dataset.schemaVariant = '';
  appendOption(document, control, '', 'Selecione');
  variants.forEach((variant) => appendVariantOption(document, control, variant, property));
  return control;
}

function appendVariantOption(document: Document, control: HTMLSelectElement, variant: JsonSchema, property: string): void {
  const schema = variant.properties?.[property];
  if (!schema || !Object.prototype.hasOwnProperty.call(schema, 'const')) return;
  appendOption(document, control, String(schema.const), schema.title ?? String(schema.const));
}

function createVariantLabel(document: Document, control: HTMLSelectElement, property: string): HTMLLabelElement {
  const label = document.createElement('label');
  label.htmlFor = control.id;
  label.textContent = property.replaceAll('_', ' ');
  return label;
}

function variantProperty(variants: readonly JsonSchema[]): string | undefined {
  const properties = Object.keys(variants[0]?.properties ?? {});
  return properties.find((key) => variants.every((variant) => hasConstProperty(variant, key)));
}

function hasConstProperty(variant: JsonSchema, property: string): boolean {
  const schema = variant.properties?.[property];
  return schema !== undefined && Object.prototype.hasOwnProperty.call(schema, 'const');
}

function renderVariantFields(document: Document, container: HTMLElement, variants: readonly JsonSchema[], prefix: string, property: string, value: string, appendFields: AppendSchemaFields): void {
  const variant = variants.find((candidate) => String(candidate.properties?.[property]?.const) === value);
  container.replaceChildren();
  if (variant) appendFields(document, container, variant, prefix, '', property);
}

function appendOption(document: Document, select: HTMLSelectElement, value: string, label: string): void {
  const option = document.createElement('option');
  option.value = value;
  option.textContent = label;
  select.append(option);
}
