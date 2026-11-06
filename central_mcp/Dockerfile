# Multi-stage Dockerfile for Central MCP using Distroless Python 3.13

FROM python:3.13-slim AS builder

WORKDIR /build

COPY central_mcp/pyproject.toml central_mcp/README.md ./
COPY central_mcp/src ./src
RUN pip install --no-cache-dir --target /install .
# Writable data directory for the location catalog; owned by the distroless nonroot uid.
RUN mkdir -p /data && chown 65532:65532 /data

FROM node:24-slim AS web-builder

WORKDIR /web

COPY central_mcp/web/package.json central_mcp/web/package-lock.json ./
RUN npm ci

COPY central_mcp/web/index.html central_mcp/web/vite.config.ts central_mcp/web/tsconfig.json central_mcp/web/tsconfig.app.json ./
COPY central_mcp/web/src ./src
RUN npm run build

FROM gcr.io/distroless/python3-debian13:nonroot

WORKDIR /app

ARG GIT_SHA=unknown
LABEL org.opencontainers.image.source="https://github.com/imobiliarias-mcp/imobiliarias"
LABEL org.opencontainers.image.revision="${GIT_SHA}"

ENV TZ=America/Sao_Paulo
ENV GENERIC_TIMEZONE=America/Sao_Paulo
ENV CENTRAL_MCP_HOST=0.0.0.0
ENV CENTRAL_MCP_PORT=8000
ENV CENTRAL_MCP_REPO_ROOT=/app
ENV PYTHONPATH=/app/site-packages:/app/central_mcp/src
ENV CENTRAL_MCP_STATIC_DIR=/app/central_mcp/web/dist
ENV CENTRAL_MCP_DATA_DIR=/data

# Copy installed site-packages
COPY --from=builder /install /app/site-packages
COPY --from=builder --chown=65532:65532 /data /data

# Copy central_mcp package (explicit paths keep local .venv and node_modules out of the image)
COPY central_mcp/src /app/central_mcp/src
COPY --from=web-builder /web/dist /app/central_mcp/web/dist

# Copy agency runtime code by allowlist (only existing folders)
COPY alecorretoramg/scripts /app/alecorretoramg/scripts
COPY alecorretoramg/src /app/alecorretoramg/src

COPY arthusoimoveis/scripts /app/arthusoimoveis/scripts

COPY cabralporto/scripts /app/cabralporto/scripts
COPY cabralporto/src /app/cabralporto/src

COPY casalinhares/scripts /app/casalinhares/scripts

COPY epifanioimoveis/scripts /app/epifanioimoveis/scripts
COPY epifanioimoveis/src /app/epifanioimoveis/src

COPY helenaimoveis/scripts /app/helenaimoveis/scripts
COPY helenaimoveis/src /app/helenaimoveis/src

COPY imobiliariaportalmg/scripts /app/imobiliariaportalmg/scripts
COPY imobiliariaportalmg/src /app/imobiliariaportalmg/src

COPY imobiliariavaleinvest/scripts /app/imobiliariavaleinvest/scripts
COPY imobiliariavaleinvest/src /app/imobiliariavaleinvest/src

COPY imovelweb/scripts /app/imovelweb/scripts

COPY marcioimoveis/scripts /app/marcioimoveis/scripts
COPY marcioimoveis/src /app/marcioimoveis/src

COPY minascaixaimoveis/scripts /app/minascaixaimoveis/scripts

COPY niltoncorretordeimoveis/scripts /app/niltoncorretordeimoveis/scripts
COPY niltoncorretordeimoveis/src /app/niltoncorretordeimoveis/src

COPY novaimobiliaria/scripts /app/novaimobiliaria/scripts
COPY novaimobiliaria/src /app/novaimobiliaria/src

COPY veraimobiliaria/scripts /app/veraimobiliaria/scripts
COPY veraimobiliaria/src /app/veraimobiliaria/src

COPY vivareal/scripts /app/vivareal/scripts
COPY vivareal/src /app/vivareal/src

USER nonroot

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD ["/usr/bin/python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"]

ENTRYPOINT ["/usr/bin/python3", "-m", "central_mcp.main"]
CMD ["--transport", "http"]
