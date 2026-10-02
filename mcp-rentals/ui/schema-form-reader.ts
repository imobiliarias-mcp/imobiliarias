import type { JsonSchema } from './schema-form.js';

export function readSchemaForm(form: HTMLFormElement, schema: JsonSchema): Record<string, unknown> {
  const values: Record<string, unknown> = {};
  const controls = Array.from(form.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-schema-path]'));
  const activeSchema = selectedSchema(form, schema);
  if (activeSchema) readProperties(values, controls, activeSchema, '');
  return values;
}

function selectedSchema(form: HTMLFormElement, schema: JsonSchema): JsonSchema | undefined {
  if (!schema.oneOf) return schema;
  const control = form.querySelector<HTMLSelectElement>('[data-schema-variant]');
  if (!control?.value) return undefined;
  return schema.oneOf.find((variant) => String(variant.properties?.[control.name]?.const) === control.value);
}

function readProperties(values: Record<string, unknown>, controls: (HTMLInputElement | HTMLSelectElement)[], schema: JsonSchema, path: string): void {
  for (const [key, property] of Object.entries(schema.properties ?? {})) {
    const fieldPath = path ? `${path}.${key}` : key;
    if (property.type === 'object' && property.properties) readNested(values, controls, key, property, fieldPath);
    if (property.type !== 'object') readControl(values, controls, key, property, fieldPath);
  }
}

function readNested(values: Record<string, unknown>, controls: (HTMLInputElement | HTMLSelectElement)[], key: string, schema: JsonSchema, path: string): void {
  const nested: Record<string, unknown> = {};
  readProperties(nested, controls, schema, path);
  if (Object.keys(nested).length > 0) values[key] = nested;
}

function readControl(values: Record<string, unknown>, controls: (HTMLInputElement | HTMLSelectElement)[], key: string, schema: JsonSchema, path: string): void {
  const control = controls.find((candidate) => candidate.dataset.schemaPath === path);
  if (!control) return;
  const value = readControlValue(control, schema);
  if (value !== undefined) values[key] = value;
}

function readControlValue(control: HTMLInputElement | HTMLSelectElement, schema: JsonSchema): unknown {
  if (Object.prototype.hasOwnProperty.call(schema, 'const')) return schema.const;
  if (schema.type === 'array') return readArrayValue(control, schema.items);
  if (control.tagName === 'SELECT' && (control as HTMLSelectElement).multiple) return undefined;
  const value = control.value.trim();
  if (!value) return undefined;
  return parseValue(value, schema);
}

function readArrayValue(control: HTMLInputElement | HTMLSelectElement, itemSchema?: JsonSchema): unknown[] | undefined {
  const isMultiSelect = control.tagName === 'SELECT' && (control as HTMLSelectElement).multiple;
  const rawValues = isMultiSelect
    ? Array.from((control as HTMLSelectElement).selectedOptions, (option) => option.value)
    : control.value.split(',').map((value) => value.trim()).filter(Boolean);
  const values = rawValues.map((value) => parseValue(value, itemSchema ?? {}));
  return values.length && values.every((value) => value !== undefined) ? values : undefined;
}

function parseValue(value: string, schema: JsonSchema): unknown {
  if (schema.type === 'boolean' || schema.enum?.some((entry) => typeof entry === 'boolean')) return value === 'true';
  if (schema.type === 'number' || schema.type === 'integer' || schema.enum?.some((entry) => typeof entry === 'number')) return parseNumber(value, schema.type === 'integer');
  return value;
}

function parseNumber(value: string, integer: boolean): number | undefined {
  const number = Number(value);
  if (!Number.isFinite(number) || integer && !Number.isInteger(number)) return undefined;
  return number;
}
