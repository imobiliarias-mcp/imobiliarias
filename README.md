# Pesquisa de aluguéis — Vale do Aço

Monorepo de clientes e pesquisas de APIs públicas de 16 imobiliárias e portais.
Cada diretório mantém seu próprio pacote Python, documentação e testes.

## Servidor MCP Central (Python)

O servidor central está implementado em Python em [`central_mcp/`](file:///home/samuelcaldas/repos/imobiliarias/central_mcp), utilizando o SDK oficial `mcp` (MCPServer / FastMCP).

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

