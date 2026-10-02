import type { JsonSchema } from './schema-form.js';
import { isRecord } from './contracts.js';

export interface NativePage {
  field: string;
  current: number;
  maximum?: number;
  hasNext: boolean;
}

const pageFields = ['page_number', 'pageNumber', 'page', 'offset'] as const;
const currentFields = ['current_page', 'currentPage', 'page'] as const;
const maximumFields = ['max_pages', 'maxPages', 'total_pages', 'totalPages'] as const;

export function readNativePage(schema: JsonSchema, native: unknown): NativePage | undefined {
  const field = supportedPageField(schema);
  const metadata = pageMetadata(native);
  if (!field || !metadata) return undefined;
  const current = firstPositiveInteger(metadata, currentFields);
  if (!current) return undefined;
  const maximum = firstPositiveInteger(metadata, maximumFields);
  const validMaximum = maximum !== undefined && maximum >= current ? maximum : undefined;
  const hasNext = validMaximum !== undefined ? current < validMaximum : hasNativeNextPage(metadata);
  if (current <= 1 && !hasNext) return undefined;
  return { field, current, maximum: validMaximum, hasNext };
}

function supportedPageField(schema: JsonSchema): string | undefined {
  for (const field of pageFields) {
    const property = schema.properties?.[field];
    if (property?.type === 'integer' || property?.type === 'number') return field;
  }
  return undefined;
}

function pageMetadata(native: unknown): Record<string, unknown> | undefined {
  if (!isRecord(native)) return undefined;
  if (isRecord(native.pagination)) return native.pagination;
  if (isRecord(native.meta) && isRecord(native.meta.pagination)) return native.meta.pagination;
  return native;
}

function hasNativeNextPage(metadata: Record<string, unknown>): boolean {
  return metadata.has_next_page === true || metadata.hasNextPage === true;
}

function firstPositiveInteger(record: Record<string, unknown>, fields: readonly string[]): number | undefined {
  for (const field of fields) {
    const value = record[field];
    if (typeof value === 'number' && Number.isInteger(value) && value > 0) return value;
  }
  return undefined;
}
