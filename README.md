# Portal agregador de imobiliárias — Vale do Aço

Portal que agrega aluguéis de imobiliárias e portais da região de Timóteo, Coronel Fabriciano e Ipatinga, com busca única, preço total, fotos e descrição. Cada imobiliária é um módulo independente, com seu próprio pacote Python, adaptador e testes.

## Arquitetura modular

- **Núcleo** ([`central_mcp/`](central_mcp/)): agrega, normaliza, limita taxa e serve o portal. Não conhece os sites das imobiliárias.
- **Módulos de provedor** (`<imobiliaria>/`): pacote `src/` com coleta e parsing, mais `scripts/mcp/tools.py` com o adaptador que cumpre o contrato fixo consumido pelo núcleo. Trocar ou adicionar um módulo não exige mudar o núcleo.
- **Interfaces**: portal web (`/`), API HTTP (`/api/*`) e MCP para agentes (`/mcp`). As três consomem o mesmo núcleo.

A decisão está registrada em [`docs/adr/0001-portal-agregador-modular.md`](docs/adr/0001-portal-agregador-modular.md).

## Núcleo do portal (`central_mcp`, Python)

O núcleo está em Python em [`central_mcp/`](central_mcp/), com o SDK oficial `mcp` (MCPServer / FastMCP) para a interface de agentes.

Ele segue rigorosamente os padrões de **Object Calisthenics**, **SOLID**, **Clean Code** e **TDD**, suportando múltiplos transportes (`stdio`, `sse` e `streamable-http`) e orquestrando as 16 agências com isolamento de dependências via ambientes virtuais dedicados (`.venv`).

Para iniciar o servidor:
```bash
cd central_mcp
# Modo STDIO (Claude Desktop / Cursor / Clientes locais)
.venv/bin/python -m central_mcp.main --transport stdio

# Modo SSE (HTTP com Server-Sent Events)
.venv/bin/python -m central_mcp.main --transport sse --host 127.0.0.1 --port 8000

# Modo Streamable HTTP
.venv/bin/python -m central_mcp.main --transport streamable-http --host 127.0.0.1 --port 8000
```

> **Nota:** A implementação anterior em TypeScript/Node.js foi arquivada e preservada na branch legada `legacy/mcp-rentals-ts`.

## Fontes locais

Os IDs públicos correspondem aos diretórios: `alecorretoramg`,
`arthusoimoveis`, `cabralporto`, `casalinhares`, `epifanioimoveis`,
`helenaimoveis`, `imobiliariaportalmg`, `imobiliariavaleinvest`, `imovelweb`,
`marcioimoveis`, `minascaixaimoveis`, `newhouseimobiliaria`, `niltoncorretordeimoveis`,
`novaimobiliaria`, `veraimobiliaria` e `vivareal`.

O checkout atual combina gitlinks e fontes locais não rastreadas.
Um clone limpo não garante a presença de todas as fontes. Especificações de
cada origem continuam nos seus próprios diretórios `docs/`.

