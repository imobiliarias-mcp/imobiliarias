import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import { createMcpHandler, type McpServerFactory } from '@modelcontextprotocol/server';
import { hostHeaderValidation, toNodeHandler } from '@modelcontextprotocol/node';

const validate_host = hostHeaderValidation(['localhost', '127.0.0.1', '[::1]']);
/** Serve HTTP on loopback by default, using the SDK's modern/legacy factory handler. */
export async function start_local_http(factory: McpServerFactory, port: number, bind: '127.0.0.1' | '0.0.0.0' = '127.0.0.1', origin_port?: number) {
  const handler = createMcpHandler(factory, {legacy: 'stateless', maxRequestBodySize: 1024 * 1024});
  const node_handler = toNodeHandler(handler, {maxRequestBodySize: 1024 * 1024});
  const server = createServer((request, response) => {
    if (!validate_host(request, response) || !validate_origin(request, response, origin_port ?? port)) return;
    if (request.url === '/health' && request.method === 'GET') { response.end('ok\n'); return; }
    if (request.url !== '/mcp') { response.writeHead(404).end(); return; }
    void node_handler(request, response);
  });
  await new Promise<void>((resolve, reject) => { server.once('error', reject); server.listen(port, bind, resolve); });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Invalid listener address');
  return {url: `http://127.0.0.1:${address.port}`, close: async () => { await handler.close(); server.closeAllConnections(); await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve())); }};
}
function validate_origin(request: IncomingMessage, response: ServerResponse, port: number): boolean {
  const origin = request.headers.origin;
  if (origin === undefined) return true;
  const local_port = port || request.socket.localPort;
  const origins = [`http://localhost:${local_port}`, `http://127.0.0.1:${local_port}`, `http://[::1]:${local_port}`];
  if (origins.includes(origin)) return true;
  response.writeHead(403).end('Origin not allowed');
  return false;
}
