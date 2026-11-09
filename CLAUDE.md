# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Monorepo of a **modular real estate aggregator portal** for the Vale do Aço region (Timóteo, Coronel Fabriciano, and Ipatinga) and national portals. The goal is one portal that aggregates rentals from every agency. MCP is one of its interfaces, not the goal. See `docs/adr/0001-portal-agregador-modular.md`.

Each agency directory is an independent module: a Python package (`src/`) that reverse-engineers the agency's site, paired with an Object Calisthenics provider adapter (`scripts/mcp/tools.py`) that implements the fixed provider contract consumed by the core (`central_mcp/`). The core serves the web portal, an HTTP API and the MCP interface from the same services.

## Commands

### Environment Setup

Each subdirectory manages its own virtual environment using `uv` with Python >= 3.11 (typically Python 3.13 or 3.14):

```bash
cd <agency_directory>
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Running Tests

Execute tests from within the respective agency directory:

```bash
# Run all tests in a subproject
cd <agency_directory> && .venv/bin/pytest

# Run tests in verbose mode
cd <agency_directory> && .venv/bin/pytest -v

# Run a single test file
cd <agency_directory> && .venv/bin/pytest tests/test_domain.py

# Run a specific test function
cd <agency_directory> && .venv/bin/pytest tests/test_domain.py -k test_price_range_validation

# Run standalone zero-dependency test runner (no pytest required)
cd <agency_directory> && .venv/bin/python scripts/run_tests.py

# Run tests across all agency subprojects from repo root
for dir in */ ; do [ -d "$dir/tests" ] && echo "=== $dir ===" && (cd "$dir" && .venv/bin/pytest); done
```

### Linting & Code Quality

```bash
# Lint current subproject or entire repository
ruff check .

# Automatically apply safe lint fixes
ruff check --fix .
```

### Live Research & CLI Verification

Each agency provides standalone CLI utilities in `scripts/`:

```bash
# Run live API verification suite
cd <agency_directory> && .venv/bin/python scripts/verify_research.py

# Query listings via CLI
cd <agency_directory> && .venv/bin/python scripts/run_search.py --city <city> --bedrooms <n>

# Fetch full property specifications and photo gallery by ID or reference code
cd <agency_directory> && .venv/bin/python scripts/run_property_detail.py <id_or_code>

# Discover taxonomy facets (cities, neighborhoods, property types)
cd <agency_directory> && .venv/bin/python scripts/run_facets.py
```

---

## High-Level Architecture & Structure

### Monorepo Agency & Engine Map

| Directory | Agency / Portal | Underlying SaaS Platform / Engine | Primary Focus |
| :--- | :--- | :--- | :--- |
| `alecorretoramg` | Alê Corretora MG | WordPress + Crocoblock JetEngine (`jet-engine/todos`) & JetSmartFilters | Timóteo & Vale do Aço |
| `arthusoimoveis` | Arthuso Imóveis | InGaia / Kenlo SaaS platform | Vale do Aço |
| `cabralporto` | Cabral Porto Imóveis | Tecimob headless REST API (`x-domain: cabralportoimoveis.com.br`) | Timóteo & Vale do Aço |
| `casalinhares` | Casa Linhares | Imobzi SaaS API (`api.imobzi.app`) | Vale do Aço |
| `epifanioimoveis` | Epifânio Imóveis | ImobiBrasil SaaS platform (`s0/funcoes_busca.php`, template `t27`) | Timóteo & Vale do Aço |
| `helenaimoveis` | Helena Imóveis | ImobiBrasil SaaS platform | Timóteo & Vale do Aço |
| `imobiliariaportalmg` | Portal Imóveis MG | Orangeimob SaaS platform (`orangeimob.com.br`, template `tema_2`) | Timóteo regional |
| `imobiliariavaleinvest` | Imobiliária Vale Invest | Grupo Union / USO (Union Softwares / BuscaImo / Praedium) | Vale do Aço |
| `imovelweb` | Imovelweb | Navent / Imovelweb API (`RPLIS` listing engine, `RPFIC` detail engine) | National portal |
| `marcioimoveis` | Márcio Imóveis | WordPress 6.x + RealHomes Theme + Easy Real Estate (ERE) plugin | Timóteo & Vale do Aço |
| `minascaixaimoveis` | Minas Caixa Imóveis | InGaia / Kenlo SaaS platform | Vale do Aço |
| `newhouseimobiliaria` | New House Imobiliária | Praedium (Laravel, `cdn3.praedium.com.br`) | Timóteo & Coronel Fabriciano |
| `niltoncorretordeimoveis`| Nilton Corretor | ImobiBrasil SaaS platform | Vale do Aço |
| `novaimobiliaria` | Nova Imobiliária | Regional portal platform | Vale do Aço |
| `veraimobiliaria` | Vera Imobiliária | Regional portal platform | Vale do Aço |
| `vivareal` | Viva Real | Grupo OLX / VivaReal internal API | National portal |

### Dual-Layer Subproject Architecture

Every agency directory maintains two strictly decoupled layers sharing domain concepts:

```
<agency_directory>/
├── pyproject.toml              # Build metadata (Hatchling) & dependencies (httpx, beautifulsoup4, pytest)
├── src/<agency>_research/      # Layer 1: Core installable Python package
│   ├── client.py               # Facade coordinating network transport and parser suite
│   ├── collaborators.py        # Gateway and parser suite abstractions
│   ├── domain/                 # Models, criteria, value objects
│   ├── infrastructure/         # HTTP client (httpx) and query/URL builders
│   └── parsers/                # Search result, detail, and facet parsers
├── scripts/                    # Layer 2: MCP Provider & Object Calisthenics Adapter
│   ├── interfaces/provider.py  # Protocols: RentalSearchCapability, RentalDetailCapability, RentalProviderProtocol
│   ├── domain/                 # Calisthenics domain: value_objects, criteria, entities, collections, exceptions
│   ├── client/                 # Calisthenics client: configuration, http_transport, query_builder, parsers
│   ├── providers/              # Provider implementation conforming to RentalProviderProtocol
│   ├── mcp/tools.py            # FastMCP tool adapter (<agency>_search_rentals, <agency>_get_property_detail, etc.)
│   ├── run_search.py           # CLI: execute rental search
│   ├── run_property_detail.py  # CLI: inspect property details
│   ├── run_facets.py           # CLI: inspect search taxonomy/facets
│   ├── run_tests.py            # Standalone zero-dependency test runner
│   └── verify_research.py      # Live endpoint integration verifier
├── tests/                      # Unit and live integration test suites
│   ├── test_client.py
│   ├── test_domain.py
│   ├── test_parsers.py
│   ├── test_query_builder.py (or test_url_builder.py)
│   └── test_live_integration.py
├── docs/                       # Reverse-engineering documentation & specifications
│   ├── api-research.md         # Full reverse-engineered endpoint and parameter matrix
│   ├── api_reference.md        # cURL recipes and payload samples
│   ├── sot/                    # Single Source of Truth API specifications
│   └── adr/                    # Architecture Decision Records (e.g. 0001-rental-search-mcp-module-design.md)
└── tmp/                        # Offline sample HTML fixtures, API responses, and reverse-engineered JS
```

### Object Calisthenics & Coding Standards (`scripts/`)

Code in `scripts/` must strictly comply with Object Calisthenics:
1. **One indent level per method**: Extract nested logic into private helper methods.
2. **No `else` keyword**: Use guard clauses, early returns, or polymorphism exclusively.
3. **Wrap domain primitives**: Wrap strings, numbers, and identifiers in Value Objects (`ListingPrice`, `PropertyCode`, `RoomCount`, `PageOffset`, `PriceRange`).
4. **First-class collections**: Classes wrapping collections (`RentalListingCollection`, `FacetCollection`, `RentalSearchResult`) contain no other state.
5. **One dot per line**: Follow Law of Demeter; assign intermediate values.
6. **No abbreviations**: Use full descriptive names (`maximum_price`, not `max_p`; `neighborhood`, not `nh`).
7. **Keep entities small**: Functions ≤ 15 lines, Classes ≤ 100 lines, Modules < 200 lines.
8. **≤ 2 instance variables per class**: Decompose classes with multiple fields into focused collaborator objects.
9. **No public getters/setters**: Expose behavior, serializers (`to_dict()`), or protocols instead of raw state.

### Documentation Pointers

- **Subproject Architecture & Calisthenics**: `<agency_directory>/scripts/ARCHITECTURE.md`
- **CLI & MCP Usage**: `<agency_directory>/scripts/USAGE.md`
- **API Specs (Single Source of Truth)**: `<agency_directory>/docs/sot/`
- **Endpoint Research & Parameter Matrices**: `<agency_directory>/docs/api-research.md`
