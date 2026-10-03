# Central Rental Research MCP Server (Python)

Servidor Model Context Protocol (MCP) central para pesquisa federada e individual de aluguéis em 15 imobiliárias e portais do Vale do Aço (Timóteo, Coronel Fabriciano, Ipatinga) e nacionais.

Desenvolvido com o SDK oficial `mcp` (MCPServer / FastMCP), seguindo rigorosamente os princípios de **Object Calisthenics**, **SOLID**, **Clean Code** e **TDD**.

---

## 1. Arquitetura

O servidor central é estruturado em camadas desacopladas:

* `central_mcp.domain`: Value Objects (`ProviderId`, `ListingPrice`, `PropertyCode`, `RoomCount`, `PageNumber`, `PublicUrl`), Entidades (`RentalListing`, `ProviderSpec`) e Coleções First-Class (`RentalListingCollection`, `ProviderCatalog`).
* `central_mcp.providers`: `ProviderRegistry` gerenciando os 15 provedores, e `LocalVenvAdapter` executando ferramentas dentro do ambiente virtual isolado (`.venv`) de cada agência via IPC JSON, garantindo isolamento de dependências e resiliência contra falhas.
* `central_mcp.application`: `RentalService` coordenando pesquisas unitárias, busca federada concorrente com controle de concorrência (`asyncio.Semaphore`), consulta de detalhes e facetas.
* `central_mcp.server`: Instância `MCPServer` com as ferramentas MCP expostas.
* `central_mcp.main`: Ponto de entrada CLI multi-transporte (`stdio`, `sse`, `streamable-http`).

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
9. `imovelweb` — Imovelweb (Navent RPLIS/RPFIC)
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

---

## 4. Execução Multi-Transporte

### 4.1 Stdio (Padrão para Clientes Locais / Claude Desktop / Cursor)

```bash
cd central_mcp
.venv/bin/python -m central_mcp.main --transport stdio
```

Exemplo de configuração para `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "rentals": {
      "command": "/home/samuelcaldas/repos/imobiliarias/central_mcp/.venv/bin/python",
      "args": ["-m", "central_mcp.main", "--transport", "stdio"],
      "cwd": "/home/samuelcaldas/repos/imobiliarias/central_mcp"
    }
  }
}
```

### 4.2 Server-Sent Events (SSE)

Inicia o servidor HTTP com transporte SSE na porta configurada:

```bash
cd central_mcp
.venv/bin/python -m central_mcp.main --transport sse --host 127.0.0.1 --port 8000
```

### 4.3 Streamable HTTP

Inicia o servidor MCP com protocolo HTTP streamable moderno:

```bash
cd central_mcp
.venv/bin/python -m central_mcp.main --transport streamable-http --host 127.0.0.1 --port 8000
```

---

## 5. Ferramentas MCP Expostas

| Ferramenta | Descrição |
| :--- | :--- |
| `list_providers` | Lista os 15 provedores disponíveis, regiões atendidas e operações suportadas. |
| `search_rentals` | Pesquisa de imóveis para locação em uma agência específica ou federada em múltiplos provedores simultaneamente. |
| `get_property_detail` | Obtém os detalhes completos, especificações e fotos de um imóvel por agência e código. |
| `get_facets` | Retorna as facetas de busca (cidades, bairros, tipos de imóvel) da agência indicada. |

---

## 6. Testes Automatizados

O projeto conta com 100% de testes unitários e de integração cobrindo domínio, registro, serviço e servidor MCP:

```bash
cd central_mcp
.venv/bin/pytest -v
```

Verificação estática e conformidade com formatação:

```bash
cd central_mcp
.venv/bin/ruff check .
```
