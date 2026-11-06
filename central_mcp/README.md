# Central Rental Research MCP Server (Python)

Servidor Model Context Protocol (MCP) central para pesquisa federada e individual de aluguéis em 15 imobiliárias e portais do Vale do Aço (Timóteo, Coronel Fabriciano, Ipatinga) e nacionais.

Desenvolvido com o SDK oficial `mcp` (`mcp[cli]>=2.3.0`), seguindo rigorosamente os princípios de **Object Calisthenics**, **SOLID**, **Clean Code** e **TDD**.

---

## 1. Arquitetura

O servidor central é estruturado em camadas desacopladas:

* `central_mcp.domain`: Value Objects (`ProviderId`, `ListingPrice`, `PropertyCode`, `RoomCount`, `PageNumber`, `PublicUrl`), Entidades (`RentalListing`, `ProviderSpec`) e Coleções First-Class (`RentalListingCollection`, `ProviderCatalog`).
* `central_mcp.providers`:
  * `ProviderRegistry`: Gerenciamento e resolução dos 15 provedores.
  * `LocalVenvAdapter` e `central_mcp.worker`: Execução de ferramentas via subprocesso isolado com protocolo JSON stdin/stdout e kill de process group em caso de timeout.
  * `capabilities`: Matriz de capacidades por provedor (`supported_filters`, checagem de limites e validação antecipada de requisições).
* `central_mcp.limits`: Limitador de taxa Token Bucket por IP (`X-Forwarded-For` com proxies confiáveis), teto global de concorrência e throttle de concorrência 1 + intervalo mínimo por provedor.
* `central_mcp.application`: `RentalService` coordenando pesquisas unitárias, busca federada concorrente, detalhes e facetas com projeção compacta de listagens.
* `central_mcp.http_app`: Aplicação Starlette combinando transporte streamable HTTP (`/mcp`), Server-Sent Events (`/sse`, `/messages/`) e probe de saúde (`/healthz`).
* `central_mcp.server`: Instância `MCPServer` com as 5 ferramentas MCP expostas.
* `central_mcp.main`: Ponto de entrada CLI multi-transporte (`stdio`, `sse`, `streamable-http`, `http`).

---

## 2. Provedores Suportados (15 Agências)

1. `alecorretoramg` — Alê Corretora MG (WordPress + Crocoblock)
2. `arthusoimoveis` — Arthuso Imóveis (Kenlo / InGaia)
3. `cabralporto` — Cabral Porto Imóveis (Tecimob Headless REST API)
4. `casalinhares` — Casa Linhares (Imobzi API)
5. `epifanioimoveis` — Epifânio Imóveis (ImobiBrasil)
6. `helenaimoveis` — Helena Imóveis (ImobiBrasil)
7. `imobiliariaportalmg` — Portal Imóveis MG (Orangeimob)
8. `imobiliariavaleinvest` — Vale Invest (Grupo Union / BuscaImo)
9. `imovelweb` — Imovelweb (Navent RPLIS/RPFIC) *(Requer automação com navegador/Cloudflare; reportado como `unavailable` em ambiente distroless)*
10. `marcioimoveis` — Márcio Imóveis (WordPress + RealHomes)
11. `minascaixaimoveis` — Minas Caixa Imóveis (Kenlo / InGaia)
12. `niltoncorretordeimoveis` — Nilton Corretor (ImobiBrasil)
13. `novaimobiliaria` — Nova Imobiliária (Regional)
14. `veraimobiliaria` — Vera Imobiliária (Regional)
15. `vivareal` — Viva Real (Grupo OLX)

---

## 3. Instalação e Configuração

Requer Python >= 3.11 e `uv`:

```bash
cd central_mcp
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Variáveis de ambiente disponíveis (veja `.env.example`):
* `CENTRAL_MCP_HOST`: Endereço de bind (padrão: `0.0.0.0`)
* `CENTRAL_MCP_PORT`: Porta do servidor (padrão: `8000`)
* `CENTRAL_MCP_WORKER_TIMEOUT`: Timeout em segundos por subprocesso (padrão: `30.0`)
* `CENTRAL_MCP_MAX_CONCURRENT_WORKERS`: Limite de requisições simultâneas (padrão: `10`)
* `CENTRAL_MCP_RATE_LIMIT_PER_MINUTE`: Limite de requisições por minuto por IP (padrão: `60`)
* `CENTRAL_MCP_RATE_LIMIT_BURST`: Burst do token bucket (padrão: `10`)
* `CENTRAL_MCP_TRUSTED_PROXIES`: Lista de IPs de proxies reversos para inspeção de `X-Forwarded-For`
* `CENTRAL_MCP_STATELESS_HTTP`: Habilita modo stateless para Streamable HTTP (padrão: `true`)

---

## 4. Execução Multi-Transporte

### 4.1 Stdio (Local / Claude Desktop / Cursor)

```bash
cd central_mcp
.venv/bin/python -m central_mcp.main --transport stdio
```

Configuração em `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "rentals": {
      "command": "/path/to/imobiliarias/central_mcp/.venv/bin/python",
      "args": ["-m", "central_mcp.main", "--transport", "stdio"],
      "cwd": "/path/to/imobiliarias/central_mcp"
    }
  }
}
```

### 4.2 HTTP Combinado (Streamable HTTP + SSE + Healthcheck)

Inicia o servidor Starlette completo expondo `/mcp` (Streamable HTTP), `/sse` (Server-Sent Events) e `/healthz`:

```bash
cd central_mcp
.venv/bin/python -m central_mcp.main --transport http --host 0.0.0.0 --port 8000
```

### 4.3 SSE ou Streamable HTTP isolados

```bash
.venv/bin/python -m central_mcp.main --transport sse --host 0.0.0.0 --port 8000
.venv/bin/python -m central_mcp.main --transport streamable-http --host 0.0.0.0 --port 8000
```

---

## 5. Docker Distroless

O projeto inclui imagem de produção multi-stage baseada em **Google Distroless Python 3.13** (`gcr.io/distroless/python3-debian13:nonroot`):

### 5.1 Construção da Imagem

```bash
docker --context docker-dev build -f central_mcp/Dockerfile -t central-mcp:latest .
```

### 5.2 Execução via Docker Compose

```bash
docker compose -f central_mcp/compose.dev.yaml up -d
```

Verifique a integridade do serviço com o probe de saúde:
```bash
curl -i http://127.0.0.1:8000/healthz
```

---

### 5.3 Produção em g-vps

Endpoint: `https://imobiliarias.g-vps.duckdns.org/mcp`; saúde: `/healthz`.
O arquivo `compose.prod.yaml` utiliza a rede externa `traefik_proxy`, TLS do
Traefik e imagem pré-construída em `docker-dev`, sem publicar portas no host.
A stack remota fica em `/opt/imobiliarias`, projeto Compose `imobiliarias`.

O serviço é público, sem autenticação: não envie informações confidenciais.
Limites: 256 MiB, 0,5 CPU, dois workers simultâneos e 30 requisições por minuto
por cliente. O proxy confiável é o Traefik em `172.18.0.2`; confira seu IP se
recriar a rede ou o proxy. Ambos os ambientes usam `America/Sao_Paulo`.

O procedimento de release, validação e rollback está no repositório
`~/repos/g-cloud/vps/docs/10-imobiliarias-mcp.md`.
`Dockerfile.dockerignore` exclui credenciais e ambientes locais do build.

## 6. Ferramentas MCP Expostas

| Ferramenta | Descrição | Parâmetros Principais |
| :--- | :--- | :--- |
| `list_rental_providers` | Lista as 15 imobiliárias e portais integrados, regiões atendidas e capacidades. | Nenhum |
| `search_rentals` | Pesquisa imóveis em uma imobiliária específica com filtros validados. | `provider` (obrigatório), `city`, `min_price`, `max_price`, `bedrooms`, `property_type`, `page`, `limit`, `include_raw` |
| `federated_search_rentals` | Pesquisa simultânea e federada em múltiplas imobiliárias (ou em todas). Retorna `status` (`ok`, `partial`, `error`), resumo por provedor e resultados consolidados. | `providers` (opcional), `city`, `min_price`, `max_price`, `bedrooms`, `property_type`, `page`, `limit`, `include_raw` |
| `get_rental_detail` | Obtém detalhes completos, especificações e galeria de fotos de um imóvel. | `provider` (obrigatório), `property_code` (obrigatório) |
| `get_rental_facets` | Retorna as facetas de busca (cidades, bairros, tipos de imóvel) da agência indicada. | `provider` (obrigatório) |

---

## 7. Testes e Qualidade

Executar suíte completa de testes:

```bash
cd central_mcp
.venv/bin/pytest -v
```

Verificação de qualidade de código e conformidade com formatação:

```bash
cd central_mcp
.venv/bin/ruff check .
```
