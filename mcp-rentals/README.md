# Central Rental MCP

The central server exposes rental-search providers through MCP over `stdio` by
default. It reuses existing provider sources through separate Python 3.14
environments. Optional MCP Apps HTTP mode is bound to the local machine for
development.

## Source availability

The build expects these 15 provider directories beside `mcp-rentals`:

- `alecorretoramg`, `arthusoimoveis`, `cabralporto`, `casalinhares`
- `epifanioimoveis`, `helenaimoveis`, `imobiliariaportalmg`
- `imobiliariavaleinvest`, `imovelweb`, `marcioimoveis`
- `minascaixaimoveis`, `niltoncorretordeimoveis`, `novaimobiliaria`
- `veraimobiliaria`, `vivareal`

Some directories are local repositories or gitlinks and are not guaranteed to
be present in a clean clone. Do not initialize, add, or rewrite provider
repositories to prepare a build. Obtain the provider sources separately, or
pass their common parent with `--source-root` to the staging script. The
builder validates all 15 source directories and their local Git revisions
before replacing `.staging`.

## Build and run with Docker

Docker operations and build tests use the `docker-dev` context. From this
directory:

```sh
cp .env.example .env
python3 scripts/stage-build.py
# Generate Python 3.14/Linux locks in Docker; see docs/development.md.
docker --context docker-dev compose -f compose.dev.yaml build rentals
```

To configure an MCP host, use `docker` as the command and the following
arguments, with the Compose file path made absolute:

```sh
docker --context docker-dev compose \
  -f /path/to/mcp-rentals/compose.dev.yaml \
  run --rm -T rentals
```

This starts the MCP server over standard input/output. Do not print diagnostics
to its stdout or attach a terminal. Staging and image builds do not contact
agency websites. Websites are queried only when a client calls a supported
provider tool. See [MCP usage](docs/mcp-usage.md) for tool contracts and
examples.

For optional local MCP Apps HTTP mode:

```sh
docker --context docker-dev compose -f compose.dev.yaml \
  --profile http up --build rentals-http
```

The published port binds to `127.0.0.1` only. Set `MCP_HTTP_PORT` in `.env` to
change the host port. HTTP mode is for local development and verification; no
public ingress or image publishing is configured.

See [development and packaging](docs/development.md) for staging, lock
generation, tests, environment variables, and build details.
