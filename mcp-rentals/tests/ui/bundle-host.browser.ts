import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { createServer } from 'vite';
import { chromium, type Browser, type Page } from 'playwright';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const bundlePath = '/dist/ui/mcp-app.html';
const localHostnames = new Set(['127.0.0.1', 'localhost']);
const bundlePolicyPrefix = "default-src 'none'; script-src 'self' 'unsafe-eval'";

interface ReferenceHost {
  ready: Promise<void>;
  calls: Array<{ name: string; arguments: Record<string, unknown> }>;
  openedLinks: string[];
  initialized: boolean;
  sendToolInput: (arguments_: Record<string, unknown>) => Promise<void>;
  delayNextSearch: () => void;
  finishSearch: () => void;
  teardown: () => Promise<Record<string, unknown>>;
}

declare global {
  interface Window {
    referenceHost: ReferenceHost;
  }
}

async function openBundledApp(page: Page, baseUrl: string, browserErrors: string[]): Promise<void> {
  await page.goto(`${baseUrl}/tests/ui/reference-host.html`);
  await page.waitForFunction(() => window.referenceHost !== undefined, null, { timeout: 10_000 }).catch(() => {
    throw new Error(`Reference host did not load: ${browserErrors.join(' | ')}`);
  });
  await page.evaluate(() => window.referenceHost.ready);
  const iframe = page.frameLocator('#app-frame');
  await iframe.locator('[data-region="providers"] h2').first().waitFor({ state: 'attached', timeout: 5_000 }).catch(async () => {
    const status = await iframe.getByRole('status').textContent();
    const hostState = await page.evaluate(() => JSON.stringify({ calls: window.referenceHost.calls, initialized: window.referenceHost.initialized }));
    throw new Error(`Bundled app catalog did not render: ${status}; host: ${hostState}; browser errors: ${browserErrors.join(' | ')}`);
  });
}

function bundleContentSecurityPolicy(bundle: string): string {
  const scriptTagStart = bundle.indexOf('<script type="module" crossorigin>');
  const contentStart = bundle.indexOf('>', scriptTagStart) + 1;
  const contentEnd = bundle.indexOf('</script>', contentStart);
  assert.ok(scriptTagStart >= 0 && contentEnd > contentStart, 'The bundled MCP App must contain its inline application script.');
  const hash = createHash('sha256').update(bundle.slice(contentStart, contentEnd)).digest('base64');
  return `${bundlePolicyPrefix} 'sha256-${hash}'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'`;
}

async function startBrowser(): Promise<Browser> {
  return chromium.launch({ headless: true, args: ['--no-sandbox'] });
}

test('runs the bundled app in the reference MCP Apps host with offline fixtures', { timeout: 120_000 }, async (context) => {
  const builtBundle = await readFile(resolve(projectRoot, 'dist/ui/mcp-app.html'), 'utf8');
  const contentSecurityPolicy = bundleContentSecurityPolicy(builtBundle);
  const server = await createServer({
    configFile: false,
    root: projectRoot,
    appType: 'mpa',
    logLevel: 'error',
    plugins: [{
      name: 'serve-built-mcp-app-verbatim',
      configureServer(viteServer) {
        viteServer.middlewares.use((request, response, next) => {
          if (request.url?.split('?')[0] !== bundlePath) return next();
          response.statusCode = 200;
          response.setHeader('Content-Type', 'text/html; charset=utf-8');
          response.setHeader('Content-Security-Policy', contentSecurityPolicy);
          response.setHeader('Cache-Control', 'no-store');
          response.end(builtBundle);
        });
      },
    }],
    server: {
      host: '127.0.0.1',
      port: 0,
      strictPort: false,
      hmr: false,
      headers: { 'Content-Security-Policy': contentSecurityPolicy },
    },
  });
  await server.listen();
  const address = server.httpServer?.address();
  assert.ok(address && typeof address === 'object');
  const baseUrl = `http://127.0.0.1:${address.port}`;
  let browser: Browser | undefined;
  await context.after(async () => {
    await browser?.close();
    await server.close();
  });
  browser = await startBrowser();
  const page = await browser.newPage();
  const externalRequests: string[] = [];
  const browserErrors: string[] = [];
  page.on('pageerror', (error) => browserErrors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  let bundlePolicy = '';
  page.on('response', async (response) => {
    if (new URL(response.url()).pathname === bundlePath) {
      bundlePolicy = (await response.allHeaders())['content-security-policy'] ?? '';
    }
  });
  await page.addInitScript(() => {
    window.addEventListener('securitypolicyviolation', (event) => {
      const trackedWindow = window as Window & { __bundleHostCspViolations?: string[] };
      trackedWindow.__bundleHostCspViolations ??= [];
      trackedWindow.__bundleHostCspViolations.push(`${event.violatedDirective}: ${event.blockedURI}`);
    });
  });
  await page.route('**/*', async (route) => {
    const requestUrl = new URL(route.request().url());
    if (!localHostnames.has(requestUrl.hostname)) {
      externalRequests.push(requestUrl.href);
      await route.abort();
      return;
    }
    await route.continue();
  });

  await openBundledApp(page, baseUrl, browserErrors);

  const iframe = page.frameLocator('#app-frame');
  const applicationScripts = await iframe.locator('script[type="module"]').evaluateAll((scripts) => scripts.map((script) => ({
    source: script.getAttribute('src'),
    inlineScript: script.textContent ?? '',
  })));
  const scriptTagStart = builtBundle.indexOf('<script type="module" crossorigin>');
  const scriptStart = builtBundle.indexOf('>', scriptTagStart) + 1;
  const scriptEnd = builtBundle.indexOf('</script>', scriptStart);
  assert.ok(scriptTagStart >= 0 && scriptEnd > scriptStart, 'Built app must include an inline application script.');
  assert.deepEqual(applicationScripts, [{ source: null, inlineScript: builtBundle.slice(scriptStart, scriptEnd) }]);
  const hostState = await page.evaluate(() => ({
    initialized: window.referenceHost.initialized,
    calls: window.referenceHost.calls.map(({ name }) => name),
  }));
  assert.equal(hostState.initialized, true);
  assert.deepEqual(hostState.calls, ['list_rental_providers']);
  assert.equal(await iframe.locator('[data-provider-id="alfa"] h2').textContent(), 'Imobiliária Alfa');

  await page.evaluate(() => window.referenceHost.sendToolInput({
    requests: [{ provider: 'alfa', filters: { city: 'Timóteo', bedrooms: 2 } }],
  }));
  assert.equal(await iframe.locator('[data-provider-id="alfa"] [data-provider-selection]').isChecked(), true);
  assert.equal(await iframe.locator('[data-provider-id="alfa"] input[name="city"]').inputValue(), 'Timóteo');
  assert.equal(await iframe.locator('[data-provider-id="alfa"] input[name="bedrooms"]').inputValue(), '2');

  await page.evaluate(() => window.referenceHost.delayNextSearch());
  await iframe.getByRole('button', { name: 'Pesquisar imóveis' }).press('Enter');
  await iframe.getByRole('status').filter({ hasText: 'Pesquisando imóveis' }).waitFor();
  await page.waitForFunction(() => window.referenceHost.calls.some(({ name }) => name === 'search_rentals'));
  const searchCall = await page.evaluate(() => window.referenceHost.calls.find(({ name }) => name === 'search_rentals'));
  assert.deepEqual(searchCall?.arguments, { requests: [{ provider: 'alfa', filters: { city: 'Timóteo', bedrooms: 2 } }] });
  await page.evaluate(() => window.referenceHost.finishSearch());
  await iframe.getByRole('heading', { name: /<img src=/ }).waitFor();
  assert.equal(await iframe.locator('img').count(), 0);
  assert.equal(await iframe.locator('body script').count(), 0);
  assert.equal(await iframe.locator('html').evaluate((root) => (root.ownerDocument.defaultView as (Window & { __bundleHostXss?: number }) | null)?.__bundleHostXss), undefined);
  assert.equal(await iframe.locator('[data-action="next-page"]').count(), 1);

  await iframe.getByRole('button', { name: 'Ver detalhes' }).click();
  await page.waitForFunction(() => window.referenceHost.calls.some(({ name }) => name === 'get_rental_detail'));
  const detailCall = await page.evaluate(() => window.referenceHost.calls.find(({ name }) => name === 'get_rental_detail'));
  assert.deepEqual(detailCall?.arguments, { provider: 'alfa', reference: 'A-31' });
  const detailText = iframe.locator('.detail-view pre').first();
  await detailText.waitFor({ state: 'attached', timeout: 5_000 });
  const renderedDetail = await detailText.innerText();
  assert.ok(renderedDetail.includes('<img src=x onerror='), renderedDetail);
  assert.ok(renderedDetail.includes('window.__bundleHostXss=1'), renderedDetail);
  assert.equal(await iframe.locator('img').count(), 0);
  assert.equal(await iframe.locator('body script').count(), 0);
  assert.equal(await iframe.locator('html').evaluate((root) => (root.ownerDocument.defaultView as (Window & { __bundleHostXss?: number }) | null)?.__bundleHostXss), undefined);

  await iframe.getByRole('button', { name: 'Abrir anúncio' }).click();
  await page.waitForFunction(() => window.referenceHost.openedLinks.length === 1);
  const openedLinks = await page.evaluate(() => window.referenceHost.openedLinks);
  assert.deepEqual(openedLinks, ['https://imoveis.example/a-31']);

  await iframe.locator('[data-provider-id="beta"] [data-provider-selection]').check();
  await iframe.getByRole('button', { name: 'Pesquisar imóveis' }).click();
  await iframe.getByRole('alert').filter({ hasText: 'tempo limite' }).waitFor();
  assert.doesNotMatch(await iframe.locator('[data-region="results"]').innerText(), /private\/path|secret-token/);
  assert.deepEqual(externalRequests, []);
  assert.match(bundlePolicy, /connect-src 'self'/);
  assert.match(bundlePolicy, /script-src 'self' 'unsafe-eval' 'sha256-/);
  const cspViolations = await page.evaluate(() => {
    const hostWindow = window as Window & { __bundleHostCspViolations?: string[] };
    const appWindow = document.querySelector<HTMLIFrameElement>('#app-frame')?.contentWindow as (Window & { __bundleHostCspViolations?: string[] }) | undefined;
    return { host: hostWindow.__bundleHostCspViolations ?? [], app: appWindow?.__bundleHostCspViolations ?? [] };
  });
  assert.deepEqual(cspViolations, { host: [], app: [] });
  assert.equal(await iframe.locator('html').evaluate((root) => (root.ownerDocument.defaultView as (Window & { __bundleHostXss?: number }) | null)?.__bundleHostXss), undefined);

  await page.evaluate(() => window.referenceHost.teardown());
  await iframe.getByRole('status').filter({ hasText: 'Painel encerrado.' }).waitFor();
});
