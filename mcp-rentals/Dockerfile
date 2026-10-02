# syntax=docker/dockerfile:1

FROM node:24-trixie-slim AS node-build
WORKDIR /workspace
COPY package.json package-lock.json ./
RUN npm ci
COPY provider-specs ./provider-specs
COPY src ./src
COPY ui ./ui
COPY scripts/export-contracts.ts ./scripts/export-contracts.ts
COPY tsconfig.json tsconfig.server.json vite.config.ts ./
RUN npm run build

FROM node-build AS node-production
RUN npm prune --omit=dev

FROM python:3.14-slim AS python-base

FROM python-base AS python-dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /opt/build
COPY python/locks ./locks
RUN python - <<'PY'
from pathlib import Path
import subprocess
import venv

provider_ids = (
    "alecorretoramg", "arthusoimoveis", "cabralporto", "casalinhares", "epifanioimoveis",
    "helenaimoveis", "imobiliariaportalmg", "imobiliariavaleinvest", "imovelweb",
    "marcioimoveis", "minascaixaimoveis", "niltoncorretordeimoveis", "novaimobiliaria",
    "veraimobiliaria", "vivareal",
)
for provider_id in provider_ids:
    lock_path = Path("locks", f"{provider_id}.requirements.txt")
    if not lock_path.is_file():
        raise RuntimeError(f"missing lock for {provider_id}")
    environment_path = Path("/opt/environments", provider_id)
    venv.create(environment_path, with_pip=True)
    python = environment_path / "bin" / "python"
    subprocess.run(
        [str(python), "-m", "pip", "install", "--require-hashes", "--no-cache-dir", "-r", str(lock_path)],
        check=True,
    )
PY

FROM python-dependencies AS python-environments
COPY build-manifest.json ./build-manifest.json
COPY python/rental_bridge /opt/mcp-rentals/python/rental_bridge
COPY --from=node-build /workspace/dist/contracts/providers.json ./contracts/providers.json
COPY sources ./sources
RUN python - <<'PY'
import json
import os
from pathlib import Path
import subprocess

expected_ids = (
    "alecorretoramg", "arthusoimoveis", "cabralporto", "casalinhares", "epifanioimoveis",
    "helenaimoveis", "imobiliariaportalmg", "imobiliariavaleinvest", "imovelweb",
    "marcioimoveis", "minascaixaimoveis", "niltoncorretordeimoveis", "novaimobiliaria",
    "veraimobiliaria", "vivareal",
)
providers = json.loads(Path("build-manifest.json").read_text())["providers"]
provider_ids = [provider["id"] for provider in providers]
if provider_ids != list(expected_ids):
    raise RuntimeError("provider manifest does not match the fixed registry")
for provider in providers:
    provider_id = provider["id"]
    provider_root = Path("/opt/build/sources", provider_id)
    python_path = ["/opt/mcp-rentals/python", *(str(provider_root / path) for path in ("src", "arthuso", "minascaixa")), str(provider_root)]
    environment = {
        **os.environ,
        "PYTHONPATH": ":".join(python_path),
        "RENTAL_CONTRACTS": "/opt/build/contracts/providers.json",
    }
    smoke_code = """import importlib, sys
from jsonschema import Draft202012Validator
from rental_bridge.contracts import load_contracts
from rental_bridge.worker import REGISTRY
provider_id = sys.argv[1]
contracts = load_contracts()
assert [item['id'] for item in contracts['providers']] == list(REGISTRY)
Draft202012Validator.check_schema(contracts['worker_response'])
provider = next(item for item in contracts['providers'] if item['id'] == provider_id)
for key in ('filters', 'reference', 'facets'):
    if provider.get(key) is not None:
        Draft202012Validator.check_schema(provider[key])
importlib.import_module(REGISTRY[provider_id])
"""
    subprocess.run([str(Path("/opt/environments", provider_id, "bin/python")), "-c", smoke_code, provider_id], cwd=provider_root, env=environment, check=True)
PY

FROM python-environments AS provider-tests
RUN python -m venv /opt/test-environments/bridge \
    && /opt/test-environments/bridge/bin/python -m pip install --require-hashes --no-cache-dir -r locks/dev-requirements.txt

FROM python-base AS runtime
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates libstdc++6 passwd tini \
    && groupadd --gid 1000 mcp-rentals \
    && useradd --uid 1000 --gid 1000 --no-create-home --home-dir /nonexistent \
       --shell /usr/sbin/nologin mcp-rentals \
    && rm -rf /var/lib/apt/lists/*
COPY --from=node-build /usr/local/bin/node /usr/local/bin/node
ENV NODE_ENV=production \
    TZ=America/Sao_Paulo \
    SOURCES_ROOT=/opt/sources \
    PYTHON_ENVIRONMENTS_ROOT=/opt/environments \
    PYTHONPATH=/opt/mcp-rentals/python \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/usr/local/bin:${PATH}
WORKDIR /opt/mcp-rentals
COPY --from=python-dependencies /opt/environments /opt/environments
COPY --from=python-environments /opt/build/sources /opt/sources
COPY --from=python-environments /opt/build/build-manifest.json ./build-manifest.json
COPY --from=python-environments /opt/mcp-rentals/python/rental_bridge ./python/rental_bridge
COPY --from=node-build /workspace/dist /opt/mcp-rentals/dist
COPY --from=node-production /workspace/node_modules ./node_modules
COPY package.json ./package.json
COPY provider-specs ./provider-specs
USER 1000:1000
EXPOSE 3001
HEALTHCHECK --interval=30s --timeout=15s --start-period=30s --retries=3 \
    CMD ["sh", "-c", "node dist/server/src/main.js --health >/dev/null && for provider in alecorretoramg arthusoimoveis cabralporto casalinhares epifanioimoveis helenaimoveis imobiliariaportalmg imobiliariavaleinvest imovelweb marcioimoveis minascaixaimoveis niltoncorretordeimoveis novaimobiliaria veraimobiliaria vivareal; do PYTHONPATH=/opt/mcp-rentals/python /opt/environments/$provider/bin/python -c 'import importlib,sys; from pathlib import Path; root=Path(\"/opt/sources\")/sys.argv[1]; sys.path[:0]=[str(root/part) for part in (\"src\",\"arthuso\",\"minascaixa\")]+[str(root)]; from jsonschema import Draft202012Validator; from rental_bridge.contracts import load_contracts; from rental_bridge.worker import REGISTRY; contracts=load_contracts(); assert [item[\"id\"] for item in contracts[\"providers\"]]==list(REGISTRY); provider=next(item for item in contracts[\"providers\"] if item[\"id\"]==sys.argv[1]); [Draft202012Validator.check_schema(schema) for schema in [contracts[\"worker_response\"],*(provider.get(key) for key in (\"filters\",\"reference\",\"facets\"))] if schema is not None]; importlib.import_module(REGISTRY[sys.argv[1]])' $provider || exit 1; done"]
ENTRYPOINT ["/usr/bin/tini", "-s", "--", "node", "dist/server/src/main.js"]
