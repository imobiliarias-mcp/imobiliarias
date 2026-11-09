# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A **modular real estate aggregator portal** for the Vale do Aço region (Timóteo, Coronel Fabriciano, Ipatinga) and national portals. One portal aggregates rentals from every agency. MCP is one of its interfaces, not the goal. See `docs/adr/0001-portal-agregador-modular.md`.

- `central_mcp/` is the core. It serves the web portal, an HTTP API and the MCP interface from the same services.
- Each agency directory is a provider module: a Python package (`src/`) that reverse-engineers the agency's site, plus an adapter (`scripts/mcp/tools.py`) that implements the provider contract the core consumes.
- `central_mcp/` and every provider module are git submodules.
- The provider list and each agency's platform are in `central_mcp/README.md` §2. Don't copy them here.

## Commands

### Core (`central_mcp/`)

```bash
cd central_mcp
.venv/bin/pytest                          # full suite
.venv/bin/pytest tests/<file>.py          # one file
.venv/bin/pytest tests/<file>.py -k <name>  # one test
.venv/bin/ruff check src tests            # lint (8 pre-existing I001 import-order findings in tests)

# Run the server (HTTP on port 8000; health check at /healthz)
.venv/bin/python -m central_mcp.main --transport http
.venv/bin/python -m central_mcp.main --help   # transports: stdio, sse, streamable-http, http

# Local dev stack in Docker (build context is the repo root)
docker compose -f central_mcp/compose.dev.yaml up -d
```

Main environment variables (`src/central_mcp/config.py`):

- `CENTRAL_MCP_REPO_ROOT`: where provider module directories are resolved (`providers/registry.py`).
- `CENTRAL_MCP_STATIC_DIR`: built UI to serve (`web/dist`).
- `CENTRAL_MCP_DATA_DIR`: writable data, e.g. the location catalog.
- `CENTRAL_MCP_TRUSTED_PROXIES`: proxies whose `X-Forwarded-For` the rate limiter trusts.
- `CENTRAL_MCP_WORKER_TIMEOUT`, `CENTRAL_MCP_MAX_CONCURRENT_WORKERS`: subprocess limits.
- `CENTRAL_MCP_*_CACHE_TTL`, `CENTRAL_MCP_ENRICH_CONCURRENCY`: cache TTLs and detail-enrichment fan-out.

### Frontend (`central_mcp/web/`)

```bash
cd central_mcp/web
npm ci              # lockfile is committed; the Dockerfile also uses `npm ci`
npm run dev         # Vite; proxies /api to the backend on :8000
npm run build       # runs `tsc -b` before `vite build`
npm run lint        # `tsc -b --noEmit`
```

### Provider modules

```bash
git clone --recurse-submodules <repo>     # or: git submodule update --init
cd <module>
uv venv && uv pip install -e ".[dev]"     # Python >= 3.11
.venv/bin/pytest
ruff check .
```

Modules that have `tests/test_live_integration.py` hit the real agency site. Run it on purpose; the unit suite must not depend on the network. Do not assume every module has CLI scripts. Check its `scripts/` and its README.

## Architecture: how a search flows

1. The web routes (`web/routes.py`, through `SearchFlow`) and the MCP server (`server.py`) both use `RentalService` (`application/service.py`).
2. `providers/capabilities.py` validates the request against the per-provider filter matrix. It also enforces `MAX_PROVIDERS_PER_REQUEST`. A provider marked `is_available=False` is not queried, which is why the UI lists 15 of 16 providers.
3. `ProviderRegistry` (`providers/registry.py`, `PROVIDER_MAP`) resolves the provider id to its adapter class.
4. `LocalVenvAdapter` (`providers/venv_adapter.py`) runs the call in a subprocess: `sys.executable -m central_mcp.worker`.
5. The worker (`worker.py`) imports the module's `scripts/mcp/tools.py`, which calls `src/<module>_research`.

Points to keep in mind:

- The subprocess uses the **core's interpreter**. `PYTHONPATH` points at the module directory. A module's `.venv` is only for its own tests.
- Everything crossing the worker is JSON (`json.dumps(result, default=str)`). Adapters must return plain types.
- The adapter contract is four methods: `search_rentals`, `get_property_detail`, `get_facets`, `get_provider_info`.
- A search listing carries `id`, `code` (the value `get_property_detail` accepts), `title`, `price`, `url`, `media_url`, `city`, `neighborhood`, `bedrooms`, `bathrooms`.
- A detail adds `description`, `photos`, `condo_fee`, `iptu`.
- `total_price` is computed in `domain/entities.py` from the rent plus extra fees. Providers may supply it directly.

Web layer (`central_mcp/src/central_mcp/web/`):

- `search_flow.py` (`SearchFlow`): fans out to providers and combines results.
- `search_cache.py` and `cache.py` (`TtlCache`): search-outcome and listing caches.
- `enrichment.py` (`ListingEnricher`): fetches detail for listings that lack a photo or description.
- `normalizer.py`: turns HTML descriptions into text.
- `location_catalog.py` and `catalog.py`: location catalog.
- `result_page.py`: paginates. `has_more` is computed here, not by the provider.
- `ordering.py`: sorting, including by total price (listings without a price go last).

### Docker image and release

- `central_mcp/Dockerfile` is built from the repo root. It copies only `scripts/` and `src/` (or the module's own package directory) of each module, by explicit list. **A new module needs its own `COPY` lines** or it won't exist in the image.
- A `v*` tag triggers `.github/workflows/release.yml`. It clones the submodules, audits the image for leaked secrets, pushes to ghcr, deploys to Dokploy and checks `/healthz`.

## Adding a provider module

Follow the checklist in `central_mcp/README.md` §1.1. In short: create the module with `src/`, `scripts/mcp/tools.py` and tests; register it in `PROVIDER_MAP`; add its capability entry in `capabilities.py`; add its `COPY` lines to the Dockerfile; add it as a submodule. Don't duplicate the checklist here.

## Conventions

- **Object Calisthenics** applies to `scripts/` (adapters) in every module:
  - one indent level per method; no `else` (use guard clauses or polymorphism)
  - wrap primitives in value objects (`ListingPrice`, `PropertyCode`, `RoomCount`)
  - first-class collections; one dot per line; no abbreviations
  - functions ≤ 15 lines, classes ≤ 100, modules < 200
  - ≤ 2 instance variables per class; no public getters/setters; tell, don't ask
- **Fixtures** in `tests/fixtures` are real pages or responses, sanitized. Don't invent them.
- **ADRs** live in `docs/adr/`. Record architectural decisions there.

## Gotchas

- `central_mcp/.venv` is an editable install pointing at the main checkout's `src/`. In a worktree, run with `PYTHONPATH=$PWD/src` or you'll test the wrong code.
- `git worktree remove` refuses a worktree containing a submodule. Remove the submodule directory first, after confirming it is clean and pushed.
- `imovelweb` is marked unavailable in `capabilities.py` (it needs a real browser), so the UI lists 15 of 16 providers.
- The New House search doesn't return condo fees. Its search-level `total_price` is therefore rent only.
- Submodules must be public for the release workflow to clone them.
