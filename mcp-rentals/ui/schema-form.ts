import { appendSchemaVariant } from './schema-form-variants.js';

export interface JsonSchema {
  readonly type?: string;
  readonly title?: string;
  readonly description?: string;
  readonly unit?: string;
  readonly 'x-unit'?: string;
  readonly enum?: readonly unknown[];
  readonly const?: unknown;
  readonly enumTitles?: readonly string[];
  readonly default?: unknown;
  readonly minimum?: number;
  readonly maximum?: number;
  readonly minLength?: number;
  readonly maxLength?: number;
  readonly pattern?: string;
  readonly required?: readonly string[];
  readonly properties?: Readonly<Record<string, JsonSchema>>;
  readonly items?: JsonSchema;
  readonly anyOf?: readonly JsonSchema[];
  readonly oneOf?: readonly JsonSchema[];
  readonly additionalProperties?: boolean;
}

export function createSchemaForm(document: Document, schema: JsonSchema, prefix: string): HTMLFormElement {
  const form = document.createElement('form');
  form.className = 'schema-form';
  form.id = prefix;
  if (schema.oneOf) {
    appendSchemaVariant(document, form, schema.oneOf, prefix, appendSchemaFields);
    return form;
  }
  appendSchemaFields(document, form, schema, prefix, '');
  return form;
}

function appendSchemaFields(document: Document, parent: HTMLElement, schema: JsonSchema, prefix: string, path: string, excludedProperty = ''): void {
  for (const [key, property] of Object.entries(schema.properties ?? {})) {
    if (key === excludedProperty) continue;
    const fieldPath = path ? `${path}.${key}` : key;
    parent.append(createField(document, key, property, prefix, fieldPath, schema.required?.includes(key) ?? false));
  }
}

function createField(document: Document, key: string, schema: JsonSchema, prefix: string, path: string, required: boolean): HTMLElement {
  if (schema.type === 'object' && schema.properties) return createObjectField(document, key, schema, prefix, path);
  const wrapper = document.createElement('div');
  wrapper.className = 'form-field';
  const control = createControl(document, schema, prefix, path, required);
  const label = document.createElement('label');
  label.htmlFor = control.id;
  label.textContent = labelText(key, schema);
  wrapper.append(label, control);
  appendDescription(document, wrapper, schema.description);
  return wrapper;
}

function createObjectField(document: Document, key: string, schema: JsonSchema, prefix: string, path: string): HTMLElement {
  const group = document.createElement('fieldset');
  const legend = document.createElement('legend');
  legend.textContent = labelText(key, schema);
  group.append(legend);
  appendSchemaFields(document, group, schema, prefix, path);
  return group;
}

function createControl(document: Document, schema: JsonSchema, prefix: string, path: string, required: boolean): HTMLInputElement | HTMLSelectElement {
  if (hasSchemaConst(schema)) return createConstControl(document, schema, prefix, path);
  if (schema.enum || schema.type === 'boolean' || schema.type === 'array' && schema.items?.enum) return createSelect(document, schema, prefix, path, required);
  const input = document.createElement('input');
  input.id = `${prefix}-${path}`;
  input.name = path;
  input.dataset.schemaType = schema.type ?? 'string';
  input.dataset.schemaPath = path;
  input.required = required;
  input.type = schema.type === 'integer' || schema.type === 'number' ? 'number' : 'text';
  if (schema.type === 'array') input.placeholder = 'Separe os valores por vírgula';
  setInputDefaults(input, schema);
  setInputConstraints(input, schema);
  return input;
}

function createConstControl(document: Document, schema: JsonSchema, prefix: string, path: string): HTMLSelectElement {
  const select = document.createElement('select');
  select.id = `${prefix}-${path}`;
  select.name = path;
  select.dataset.schemaType = schema.type ?? 'string';
  select.dataset.schemaPath = path;
  const value = String(schema.const);
  appendOption(document, select, value, value);
  select.disabled = true;
  return select;
}

function hasSchemaConst(schema: JsonSchema): boolean {
  return Object.prototype.hasOwnProperty.call(schema, 'const');
}

function createSelect(document: Document, schema: JsonSchema, prefix: string, path: string, required: boolean): HTMLSelectElement {
  const select = document.createElement('select');
  select.id = `${prefix}-${path}`;
  select.name = path;
  select.dataset.schemaType = schema.type ?? 'string';
  select.dataset.schemaPath = path;
  select.multiple = schema.type === 'array';
  appendOption(document, select, '', schema.type === 'boolean' && !required ? 'Não filtrar' : 'Selecione');
  const values = schema.enum ?? (schema.type === 'boolean' ? [true, false] : schema.items?.enum ?? []);
  values.forEach((value, index) => appendOption(document, select, String(value), optionTitle(value, schema, index)));
  select.required = required;
  setSelectDefault(select, schema.default);
  return select;
}

function appendOption(document: Document, select: HTMLSelectElement, value: string, label: string): void {
  const option = document.createElement('option');
  option.value = value;
  option.textContent = label;
  select.append(option);
}

function optionTitle(value: unknown, schema: JsonSchema, index: number): string {
  return schema.enumTitles?.[index] ?? String(value);
}

function labelText(key: string, schema: JsonSchema): string {
  const label = schema.title ?? key.replaceAll('_', ' ');
  const unit = schema.unit ?? schema['x-unit'];
  return unit ? `${label} (${unit})` : label;
}

function appendDescription(document: Document, wrapper: HTMLElement, description?: string): void {
  if (!description) return;
  const note = document.createElement('small');
  note.textContent = description;
  wrapper.append(note);
}

function setInputDefaults(input: HTMLInputElement, schema: JsonSchema): void {
  if (schema.default !== undefined) input.value = String(schema.default);
}

function setSelectDefault(select: HTMLSelectElement, value: unknown): void {
  if (value === undefined) return;
  const desired = new Set(Array.isArray(value) ? value.map(String) : [String(value)]);
  Array.from(select.options).forEach((option) => { option.selected = desired.has(option.value); });
}

function setInputConstraints(input: HTMLInputElement, schema: JsonSchema): void {
  if (schema.type === 'integer') input.step = '1';
  if (schema.minimum !== undefined) input.min = String(schema.minimum);
  if (schema.maximum !== undefined) input.max = String(schema.maximum);
  if (schema.minLength !== undefined) input.minLength = schema.minLength;
  if (schema.maxLength !== undefined) input.maxLength = schema.maxLength;
  if (schema.pattern) input.pattern = schema.pattern;
}

export { readSchemaForm } from './schema-form-reader.js';
