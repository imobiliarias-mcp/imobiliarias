# Central MCP (Python) for Gemini Spark — harden and extend `central_mcp`

## Context

The request: no TypeScript; use the official Python MCP SDK (`modelcontextprotocol/python-sdk`, published on PyPI as `mcp`); integrate every rental submodule into one central MCP; make rental search usable directly from Google's Gemini Spark.

`central_mcp/` already exists (tracked on this branch) and wires all 15 providers through five tools (`list_rental_providers`, `search_rentals`, `federated_search_rentals`, `get_rental_detail`, `get_rental_facets`). It uses `mcp[cli]>=2.3.0` (`MCPServer`) with stdio/SSE/streamable-http. The older TypeScript plan (`docs/plans/partitioned-drifting-tide.md`) is superseded for implementation language and transport; its per-provider findings (filter gaps, URL rules, Imovelweb/Márcio/Vale Invest caveats) are still the best reference.

Decisions already made with the user:

| Topic | Decision |
|---|---|
| Existing package | Harden and extend `central_mcp`; no rebuild |
| Runtime | Docker **distroless**, exposing stdio + SSE + streamable-http, newest SDK, **no auth** |
| Abuse protection | In-server rate limiting (no auth) |
| Production deploy | **Out of scope now** (no docker-vm/NPM work; no public URL) |
| MCP App / UI | **None**. `mcp-apps:create-mcp-app` is not applied. SDK 2.3.0 ships `mcp.server.apps` if a UI is wanted later |

What Spark needs (Google help page + search; not verified live): a remote MCP URL added under Gemini → Settings → Connected Apps → custom app. Stdio cannot work for Spark; it is for local clients and `docker run -i`. Spark is documented for US, English, personal Google accounts. This is a manual acceptance step for later, since the public URL is deferred.

## Findings that shape the plan

1. **Per-call venv subprocess will not work in distroless.** `providers/venv_adapter.py` runs `<agency>/.venv/bin/python -c "<script built from f-strings>"`. Host `.venv`s are not in the image, and distroless has no shell. The script embeds JSON and the method name into code.
2. **Silent failures.** The adapter returns `{"error": ...}` dicts instead of raising. `RentalService._safe_search` catches only `RuntimeError/OSError/ValueError/KeyError`, and `_aggregate_results` drops per-provider errors, so a failed provider looks like "zero listings".
3. **Fake filter semantics.** Defaults `city="Timóteo"`, `0` meaning "unset", and one uniform filter set for 15 providers whose real builders differ. Known gaps from the earlier plan (re-verify by test, do not trust): Imovelweb rejects price; Minas Caixa ignores neighborhood/type; Vale Invest wrapper limits price combinations.
4. **Import isolation is still required.** Subprojects all use top-level `scripts.*`; one process per call (as today) keeps them apart. Dependencies don't conflict (httpx, bs4, lxml, requests), so one shared environment can serve all workers.
5. **Sources in the image.** All 15 agency dirs are gitlinks with no `.gitmodules`; four were untracked. The build must copy from the working tree by allowlist, not rely on submodule checkout.
6. **Imovelweb needs a browser** (Patchright + Cloudflare). It cannot run in distroless. It will report `unavailable` with a reason. No challenge evasion.
7. `README.md` tool names are out of date.

## Design

### A. Worker isolation (replaces `LocalVenvAdapter` internals)
- New fixed module `central_mcp/worker.py`: reads one JSON request from stdin (`{provider, method, kwargs}`), method checked against an allowlist (`search_rentals`, `get_property_detail`, `get_facets`, `get_provider_info`), imports `scripts.mcp.tools.<Class>` for the registered class, writes one JSON result to stdout, logs to stderr. No code is built from strings.
- Adapter launches `sys.executable -m central_mcp.worker` with `cwd=<agency dir>`, `PYTHONPATH=<agency dir>:<central site-packages>`, minimal environment, `start_new_session=True`. On timeout or cancel it kills the process group. Stdout and stderr are capped; excess is an explicit error.
- Adapter **raises** `ProviderError(provider, code, message)` with codes `timeout|unavailable|invalid_output|upstream_error|output_too_large|unsupported_filter`. No error-dicts.
- Providers whose import fails are marked `unavailable` with a reason. Probe once at startup and surface it in the catalog and in federated results.

### B. Service and tool contract (`application/service.py`, `server.py`)
- Validate the whole request before launching any worker: unknown or duplicate provider IDs, unsupported filters, bounds (`page ≥ 1`, price ≥ 0, `min ≤ max`, string lengths, ≤ 15 providers). Failures raise `ToolError` and start zero workers.
- Filters become `Optional` with no silent defaults (`city=None`, not `"Timóteo"`). A provider **capability matrix** (data in `providers/capabilities.py`) lists the filters each provider truly applies. A filter a provider ignores is rejected for that provider. Matrix values are established by RED→GREEN tests against each real query builder, starting from the known gaps above.
- Federated search returns `{status: ok|partial|error, providers: [{provider, status, count, error_code, error}], results: [...]}`, with no pretend global total or global ranking and no cross-provider dedupe. Single-provider failure and all-providers-failed set `isError`. Partial success does not.
- Compact projection per listing (`provider, code, title, location, price, bedrooms, url`, null when unknown) plus `include_raw: bool = False` for the native payload; `limit` (default 20) caps response size for Spark. `url` uses whatever the provider returns (`url`/`detail_url`); never fabricated.
- Every tool returns a text `content` summary plus structured output (typed return models, so the SDK produces output schemas). Tool descriptions in English (Spark is English-only); data stays Portuguese.
- Keep the five existing tool names; update README to match.

### C. Transports and abuse protection (`main.py`, new `http_app.py`, `limits.py`)
- `stdio`: unchanged entry (`docker run -i`).
- `http` mode: one Starlette app combining `server.streamable_http_app(...)` (`/mcp`) and `server.sse_app(...)` (`/sse`, `/messages/`), the streamable app's lifespan, and `/healthz` via the SDK's custom-route hook. Defaults: `stateless_http=True` (tools are pure; friendlier behind proxies/hosted clients), configurable by env.
- Pass an explicit `TransportSecuritySettings` (allowed hosts/origins from env; no wildcard default when bound to `0.0.0.0`) and `max_request_body_size`.
- ASGI rate-limit middleware, dependency-free:
  - token bucket per client IP (`X-Forwarded-For` only from `CENTRAL_MCP_TRUSTED_PROXIES`), HTTP 429 + `Retry-After`;
  - global in-flight request cap;
  - per-provider upstream throttle (concurrency 1 plus minimum interval) so the server never hammers one site, including via federated calls;
  - per-call deadline, worker timeout, global worker concurrency.
- All limits come from env with safe defaults. **Fail fast at startup** on invalid config (missing provider dirs, bad numbers, unusable Python), before serving. No secrets exist in this design; `.env.example` holds only limits and hosts.
- `main.py` keeps `--transport stdio|sse|streamable-http` and adds `http` (both on one port); `--host/--port` flow into the app/security settings, not just `server.run`.

### D. Distroless image (`central_mcp/Dockerfile`, `.dockerignore`)
- Multi-stage: builder installs pinned dependencies with `pip install --target` (no venv, since a venv's `python` symlink breaks in distroless) from a lock. Final stage is `gcr.io/distroless/python3` on Debian 13 (Python 3.13 to match the builder; verify the tag/ABI at build time), non-root, read-only filesystem friendly.
- Copy `central_mcp/src` plus an **allowlist** of each agency's runtime code (`src/`, `scripts/`, and metadata the imports need). Exclude `.git`, `.venv`, `tmp`, `tests`, `docs`, `.env`. Stage from the working tree; do not use `git submodule` metadata.
- Install the union of provider dependencies (httpx, beautifulsoup4, lxml, requests; plus the packages Imovelweb needs for import, but no browser binaries).
- `ENV TZ=America/Sao_Paulo`, `EXPOSE 8000`, exec-form `HEALTHCHECK` using `python -c` against `/healthz` (no shell or curl in distroless). Entrypoint `python -m central_mcp.main`; transport by args/env.
- Build and test through `docker --context docker-dev`. Add a small compose file for dev. Production wiring is not part of this plan.

## Files

Modify: `central_mcp/src/central_mcp/{server.py,main.py,application/service.py,providers/{registry.py,venv_adapter.py,protocol.py}}`, `central_mcp/pyproject.toml` (pin `mcp>=2.3,<3`, add lock; add `requests`/`lxml`/`beautifulsoup4` via the worker extra), `central_mcp/README.md`, existing tests.
Create: `central_mcp/src/central_mcp/{worker.py,errors.py,limits.py,http_app.py,config.py,providers/capabilities.py}`, `central_mcp/Dockerfile`, `central_mcp/.dockerignore`, `central_mcp/compose.dev.yaml`, `central_mcp/.env.example`, new tests below.
Reuse: `ProviderRegistry`/`PROVIDER_MAP`, `RentalService` (semaphore + `asyncio.to_thread`), domain value objects (`ProviderId`, `ListingPrice`, `PageNumber`, `PublicUrl`) for validation, SDK `TransportSecuritySettings`, `custom_route`, `streamable_http_app`, `sse_app`. Do not modify the 15 submodules.

Code standards: SOLID, Object Calisthenics limits (functions ≤ 15 lines, modules < 200 lines), no hardcoded selectors/limits (config), docstrings on public items.

## Implementation order (TDD, RED→GREEN each step)

### Task 1: Config and Errors

- Files: `central_mcp/src/central_mcp/config.py`, `central_mcp/src/central_mcp/errors.py`, `central_mcp/tests/test_config.py`
- Step 1: Write failing tests in `tests/test_config.py` verifying `AppConfig` parsing, environment overrides, validation of positive limits, trusted proxy splitting, and `ProviderError` domain error hierarchy with codes `timeout|unavailable|invalid_output|upstream_error|output_too_large|unsupported_filter`.
- Step 2: Run `pytest tests/test_config.py` and verify RED.
- Step 3: Implement `config.py` and `errors.py` satisfying Object Calisthenics (small functions, typed values, fail fast).
- Step 4: Run `pytest tests/test_config.py` and verify GREEN.

### Task 2: Worker and Subprocess Adapter

- Files: `central_mcp/src/central_mcp/worker.py`, `central_mcp/src/central_mcp/providers/venv_adapter.py`, `central_mcp/tests/test_worker.py`, `central_mcp/tests/test_venv_adapter.py`
- Step 1: Write failing tests in `tests/test_worker.py` and `tests/test_venv_adapter.py` testing JSON stdin/stdout protocol, allowed methods, process group cleanup, timeout, oversized output, and parallel execution across fake provider directories without import pollution.
- Step 2: Run `pytest tests/test_worker.py tests/test_venv_adapter.py` and verify RED.
- Step 3: Implement `worker.py` (strict JSON reader/writer, method allowlist, safe import of `scripts.mcp.tools`) and refactor `LocalVenvAdapter` to launch `sys.executable -m central_mcp.worker` raising `ProviderError`.
- Step 4: Run `pytest tests/test_worker.py tests/test_venv_adapter.py` and verify GREEN.

### Task 3: Capability Matrix and Request Validation

- Files: `central_mcp/src/central_mcp/providers/capabilities.py`, `central_mcp/tests/test_capabilities.py`
- Step 1: Write failing tests in `tests/test_capabilities.py` testing each agency's supported filters against actual query builders (offline), verifying rejection of unsupported filters and bounds checking.
- Step 2: Run `pytest tests/test_capabilities.py` and verify RED.
- Step 3: Implement `capabilities.py` with matrix, validation logic, and startup availability probe (marking Imovelweb unavailable due to browser requirement).
- Step 4: Run `pytest tests/test_capabilities.py` and verify GREEN.

### Task 4: Service and Federation Contract

- Files: `central_mcp/src/central_mcp/application/service.py`, `central_mcp/tests/test_service.py`
- Step 1: Write failing tests in `tests/test_service.py` verifying federated contract: `{status: ok|partial|error, providers: [...], results: [...]}`, compact listing projection, `limit` parameter, `include_raw` toggle, and error code propagation.
- Step 2: Run `pytest tests/test_service.py` and verify RED.
- Step 3: Update `RentalService` to use `ProviderError`, capabilities validation, projection, and new federated response structure.
- Step 4: Run `pytest tests/test_service.py` and verify GREEN.

### Task 5: Rate Limiting and Upstream Throttling

- Files: `central_mcp/src/central_mcp/limits.py`, `central_mcp/tests/test_limits.py`
- Step 1: Write failing tests in `tests/test_limits.py` verifying token bucket per client IP, 429 Retry-After calculation, global in-flight request limiter, and per-provider concurrency 1 + interval throttle.
- Step 2: Run `pytest tests/test_limits.py` and verify RED.
- Step 3: Implement `limits.py` with TokenBucket, InFlightLimiter, and ProviderThrottle.
- Step 4: Run `pytest tests/test_limits.py` and verify GREEN.

### Task 6: Starlette HTTP Application and Transports

- Files: `central_mcp/src/central_mcp/http_app.py`, `central_mcp/src/central_mcp/server.py`, `central_mcp/src/central_mcp/main.py`, `central_mcp/tests/test_http_app.py`, `central_mcp/tests/test_server.py`
- Step 1: Write failing tests in `tests/test_http_app.py` and `tests/test_server.py` checking `/healthz`, `/mcp` streamable HTTP, `/sse`, rate limit middleware, and TransportSecuritySettings.
- Step 2: Run `pytest tests/test_http_app.py tests/test_server.py` and verify RED.
- Step 3: Implement `http_app.py`, wire Starlette middleware, and update `server.py` and `main.py` to support `http` transport.
- Step 4: Run `pytest tests/test_http_app.py tests/test_server.py` and verify GREEN.

### Task 7: Dockerfile, Compose, and Packaging

- Files: `central_mcp/Dockerfile`, `central_mcp/.dockerignore`, `central_mcp/compose.dev.yaml`, `central_mcp/.env.example`, `central_mcp/pyproject.toml`
- Step 1: Update `pyproject.toml` dependencies, create `.dockerignore`, `.env.example`, and `compose.dev.yaml`.
- Step 2: Implement multi-stage distroless `Dockerfile` targeting `gcr.io/distroless/python3-debian13` with non-root user and healthcheck.
- Step 3: Test local build or dry-run validation.

### Task 8: Documentation and Verification Suite

- Files: `central_mcp/README.md`, full test run, ruff check.
- Step 1: Update `central_mcp/README.md` with accurate tool names, parameters, HTTP and Docker usage instructions.
- Step 2: Run full test suite `pytest` and `ruff check .` across `central_mcp`.
- Step 3: Verify clean working state.

## Verification

- `cd central_mcp && .venv/bin/pytest` and `ruff check .` (offline; live tests excluded).
- Per-agency suites untouched; run them in separate processes if any adapter code under them changes (it should not).
- Real MCP client against the app: streamable-http at `/mcp` and SSE at `/sse` do `initialize`, `tools/list`, `tools/call` (verify output schema and `content` fallback); stdio via `docker run -i` handshake.
- Rate limit: burst past the bucket returns 429 with `Retry-After`; one provider is never queried concurrently by two calls.
- Container: `docker --context docker-dev build`, run as non-root with read-only rootfs and `TZ` set, `HEALTHCHECK` goes healthy, `list_rental_providers` shows 14 available and Imovelweb `unavailable` (reason: browser required), a federated search with fixtures returns `partial` with per-provider errors.
- Manual, later: add the public `/mcp` URL in Gemini → Connected Apps (US, English, personal account) and run a rental search. Not possible until a public URL exists.
- No live public searches during development; no challenge bypass.

## Risks and notes

- **No auth on a public endpoint** (user's choice): anyone with the URL can drive scrapes through your IP. Rate limits reduce but do not remove this. Revisit before the production deploy, using a static bearer token or OAuth via the SDK's auth support.
- Imovelweb is unavailable in distroless by design; running it needs a non-distroless image with Chromium.
- Process-per-call adds startup latency per request; acceptable now, and persistent per-provider workers are a later optimization.
- Spark behavior (transport, size limits, `ui://` rendering) is documented thinly; plan for compact outputs, and re-check against Spark once a URL exists.
- The `mcp` package from PyPI is the official release of the repo you named. If you want the git source instead, pin a tag via `[tool.uv.sources]`.
- Git: work on a worktree/branch per your rules; sync with `origin` only if a remote exists (earlier notes say the root had none); merge directly, no PR.
