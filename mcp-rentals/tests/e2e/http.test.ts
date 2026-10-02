import { test } from 'node:test';
import assert from 'node:assert/strict';
import { McpServer } from '@modelcontextprotocol/server';
import { request } from 'node:http';
import { start_local_http } from '../../src/http.js';

test('trusted published origin port can differ from the local container listener', async () => {
  const http = await start_local_http(() => new McpServer({name: 'offline', version: '1'}), 0, '127.0.0.1', 3000);
  try {
    const allowed = await fetch(`${http.url}/health`, {headers: {Origin: 'http://localhost:3000'}});
    assert.equal(allowed.status, 200);
    const wrong = await fetch(`${http.url}/health`, {headers: {Origin: 'http://localhost:3002'}});
    assert.equal(wrong.status, 403);
    assert.equal(allowed.headers.get('access-control-allow-origin'), null);
  } finally { await http.close(); }
});

test('local HTTP guards reject hostile Host and Origin before SDK handling', async () => {
  const http = await start_local_http(() => new McpServer({name: 'offline', version: '1'}), 0);
  try {
    const health = await fetch(`${http.url}/health`);
    assert.equal(health.status, 200);
    const host = await new Promise<number>(resolve => {
      const connection = request(`${http.url}/mcp`, {method: 'POST', headers: {Host: 'attacker.example', 'Content-Type': 'application/json'}}, response => { response.resume(); response.on('end', () => resolve(response.statusCode!)); });
      connection.end('{}');
    });
    assert.equal(host, 403);
    const origin = await fetch(`${http.url}/mcp`, {method: 'POST', headers: {Origin: 'https://attacker.example', 'Content-Type': 'application/json'}, body: '{}'});
    assert.equal(origin.status, 403);
    const nul = await fetch(`${http.url}/mcp`, {method: 'POST', headers: {Origin: 'null', 'Content-Type': 'application/json'}, body: '{}'});
    assert.equal(nul.status, 403);
    assert.equal(origin.headers.get('access-control-allow-origin'), null);
  } finally { await http.close(); }
});
