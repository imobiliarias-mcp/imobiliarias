import { test } from 'node:test';
import assert from 'node:assert/strict';
import { load_configuration } from '../../src/configuration.js';

test('invalid local source settings fail before registration without network', () => {
  for (const environment of [{SOURCES_ROOT: '/'}, {SOURCES_ROOT: 'relative'}, {RENTAL_WORKERS: '0'}, {RENTAL_WORKERS: ' '}, {RENTAL_WORKER_TIMEOUT_MS: 'NaN'}, {RENTAL_HTTP_PORT: '80'}]) assert.throws(() => load_configuration(environment));
  assert.equal(load_configuration({SOURCES_ROOT: process.cwd()}).workers, 3);
});
