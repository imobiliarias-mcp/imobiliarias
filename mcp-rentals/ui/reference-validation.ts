import { isRecord } from './contracts.js';
import type { JsonSchema } from './schema-form.js';

export function supportsReference(value: unknown, schema: JsonSchema): boolean {
  if (hasSchemaConst(schema)) return Object.is(value, schema.const);
  if (schema.oneOf) return matchesOneOf(value, schema.oneOf);
  if (schema.type === 'string') return typeof value === 'string' && matchesStringSchema(value, schema);
  if (schema.type === 'object') return matchesObjectSchema(value, schema);
  if (schema.type === 'integer') return typeof value === 'number' && Number.isInteger(value) && matchesEnum(value, schema);
  if (schema.type === 'number') return typeof value === 'number' && Number.isFinite(value) && matchesEnum(value, schema);
  if (schema.type === 'boolean') return typeof value === 'boolean' && matchesEnum(value, schema);
  if (schema.type === 'array') return matchesArraySchema(value, schema);
  return matchesAlternatives(value, schema);
}

function matchesStringSchema(value: string, schema: JsonSchema): boolean {
  if (!matchesEnum(value, schema)) return false;
  if (schema.minLength !== undefined && value.length < schema.minLength) return false;
  if (schema.maxLength !== undefined && value.length > schema.maxLength) return false;
  return matchesPattern(value, schema.pattern);
}

function matchesObjectSchema(value: unknown, schema: JsonSchema): boolean {
  const properties = schema.properties;
  if (!isRecord(value) || !properties || schema.additionalProperties !== false) return false;
  if (!hasRequiredProperties(value, schema.required ?? [])) return false;
  return Object.entries(value).every(([key, entry]) => matchesObjectProperty(key, entry, properties));
}

function hasRequiredProperties(value: Record<string, unknown>, required: readonly string[]): boolean {
  return required.every((key) => Object.prototype.hasOwnProperty.call(value, key));
}

function matchesObjectProperty(key: string, value: unknown, properties: Readonly<Record<string, JsonSchema>>): boolean {
  const schema = properties[key];
  return schema !== undefined && supportsReference(value, schema);
}

function matchesArraySchema(value: unknown, schema: JsonSchema): boolean {
  return Array.isArray(value) && schema.items !== undefined && value.every((entry) => supportsReference(entry, schema.items!));
}

function matchesAlternatives(value: unknown, schema: JsonSchema): boolean {
  return schema.anyOf?.some((entry) => supportsReference(value, entry)) ?? false;
}

function matchesOneOf(value: unknown, alternatives: readonly JsonSchema[]): boolean {
  return alternatives.filter((entry) => supportsReference(value, entry)).length === 1;
}

function hasSchemaConst(schema: JsonSchema): boolean {
  return Object.prototype.hasOwnProperty.call(schema, 'const');
}

function matchesEnum(value: unknown, schema: JsonSchema): boolean {
  return !schema.enum || schema.enum.some((entry) => Object.is(entry, value));
}

function matchesPattern(value: string, pattern?: string): boolean {
  if (!pattern) return true;
  try {
    return new RegExp(pattern).test(value);
  } catch {
    return false;
  }
}

export function serializeReference(value: unknown): string | undefined {
  try {
    return JSON.stringify(value);
  } catch {
    return undefined;
  }
}

export function parseReference(value?: string): unknown {
  if (!value) return undefined;
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return undefined;
  }
}
