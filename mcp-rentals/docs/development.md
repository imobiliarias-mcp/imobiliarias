# Development and packaging

## Boundaries

The server is read-only and uses a fixed provider registry. MCP `stdio` is the
default transport; optional HTTP/MCP Apps mode is for local development. Builds
do not query agency websites, run provider searches, install browser binaries,
publish images, alter Git topology, or modify provider source files.

A checkout must have all 15 source directories beside `mcp-rentals`, or use
`--source-root` to select their common parent. Clean clones might not contain
the local repositories or gitlinks. Do not add submodules or copy source
`.venv` directories as part of packaging.

## Deterministic staging

Run from `mcp-rentals` after provider sources are available:

```sh
python3 scripts/stage-build.py
# An alternate parent is supported:
python3 scripts/stage-build.py --source-root /path/to/provider-parent
```

Staging validates every required provider directory, source layout, and local
Git revision before constructing `.staging`. The Docker context contains the
central build inputs and allowlisted provider source, metadata, and data files,
plus `build-manifest.json`. It omits `.git`, untracked Git state, `.env*`,
keys/credentials, `.venv`, caches, tests, temporary directories, and unrelated
checkout content. The manifest records local Git revisions and SHA-256
digests of staged provider files. Staging reads provider sources without
changing their Git metadata or worktrees.

The Docker context is `.staging`, not the monorepo root. Review that directory
and its manifest to audit source selection. `.staging` is ignored by Git.

## Hash-pinned Python environments

The central bridge dependencies are combined with runtime dependencies from
each source `pyproject.toml` or `requirements.txt`. Casalinhares has no package
metadata, so the generator declares its existing `httpx` runtime dependency.
Imovelweb retains its `lxml` and `patchright` imports; Minas Caixa retains
`requests`. Development and test dependencies are excluded from provider
runtime locks.

Generate Python 3.14/Linux locks with pinned pip-tools inside `docker-dev`:

```sh
docker --context docker-dev run --rm \
  -v "$(dirname "$PWD"):/workspace" \
  -w "/workspace/$(basename "$PWD")" python:3.14-slim sh -c \
  'python -m pip install --disable-pip-version-check \
  pip==25.3 pip-tools==7.5.2 && python scripts/generate-locks.py'
```

This writes one `python/locks/{provider}.requirements.txt` per provider and a
separate `python/locks/dev-requirements.txt`. Runtime locks include hashes and
install with pip's `--require-hashes`. Each provider has its own environment
under `/opt/environments/{provider}`. Do not reuse or copy source `.venv`
folders. Regenerate locks after changing runtime dependency metadata and review
the lock diff. The generator does not install packages in the host environment.

## Build and test in Docker

The multi-stage build uses Node 24 for the server and UI, then Python 3.14 for
15 hash-locked provider environments. Pip installs are in a dependency-only
stage keyed by lock files, so source, schema, and UI edits reuse that layer.
Runtime includes Node, Python, bridge sources, schemas, staged providers, and
the revision/digest manifest, without development dependencies or source Git
data.

Build and run stdio from `mcp-rentals`:

```sh
python3 scripts/stage-build.py
docker --context docker-dev compose -f compose.dev.yaml \
  run --build --rm -T rentals
```

Build the isolated test target, then run both packaging and provider tests
offline with its pinned pytest environment and a read-only checkout:

```sh
docker --context docker-dev build --target provider-tests \
  -t mcp-rentals:provider-tests .staging
docker --context docker-dev run --rm --network none \
  -v "$(dirname "$PWD"):/workspace:ro" \
  -w "/workspace/$(basename "$PWD")" \
  mcp-rentals:provider-tests \
  /opt/test-environments/bridge/bin/python -m pytest \
  -q -p no:cacheprovider tests/build
docker --context docker-dev run --rm --network none \
  -v "$(dirname "$PWD"):/workspace:ro" \
  -w "/workspace/$(basename "$PWD")" \
  mcp-rentals:provider-tests python tests/build/run_provider_suites.py
```

Stage tests use temporary fixtures and mock Git revision lookup; they do not
touch provider repositories. Provider suites run separately with their own
source paths and dependencies.

The runner executes shared bridge tests once, then each provider suite in its
own process with that provider's source paths and dependencies. Do not collect
all `test_{provider}.py` modules in one pytest process: their `scripts.*`
imports collide. Run central Node tests and builds in a Node 24 container. Avoid
live integration suites during packaging checks.

## Runtime safety and configuration

Provider HTTP responses are bounded to 8 MiB per response. Requests advertise
`Accept-Encoding: identity`; compressed responses are rejected as
`invalid_content` before decompression. This prevents oversized or compressed
bodies from being buffered by provider parsers.

Workers run in detached process groups and inherit a unique per-request
lifetime marker. Timeout and cancellation cleanup also checks Linux `/proc` for
marked descendants, including children that start new sessions. The image runs
`tini -s` as a subreaper; Compose `init: true` adds container process cleanup.

The development `.env` is optional and ignored. `TZ` defaults to
`America/Sao_Paulo`; worker paths are fixed to `/opt/sources`,
`/opt/environments`, and `/opt/mcp-rentals/python`. Do not put credentials in
`.env.example`, source control, build arguments, or the staging manifest.

The image health check validates local configuration, provider registration,
imports, and schemas without contacting provider sites. Healthy status does not
mean an agency website is available.

## Optional local HTTP mode

HTTP mode is disabled for the default stdio service. The `http` profile binds
the server to the container interface and publishes only on host loopback:

```sh
docker --context docker-dev compose -f compose.dev.yaml \
  --profile http up --build rentals-http
```

The default host port is `127.0.0.1:3000` and forwards to container port 3001.
Set `MCP_HTTP_PORT` in `.env` to choose another host port. Compose also sets
`RENTAL_HTTP_ORIGIN_PORT` to that port so local browser origins such as
`http://localhost:3000` or `http://127.0.0.1:3000` are validated explicitly.
Origin validation is not replaced with wildcard CORS. Do not expose this
service publicly or add an unrestricted bind. No Nginx, OAuth, or automatic
image publishing is configured.
