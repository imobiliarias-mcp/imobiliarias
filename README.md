# Pesquisa de aluguéis — Vale do Aço

Monorepo de clientes e pesquisas de APIs públicas de 15 imobiliárias e portais.
Cada diretório mantém seu próprio pacote Python, documentação e testes.

## Servidor MCP central

A implementação anterior do servidor MCP em TypeScript/Node.js foi preservada e movida para a branch legada `legacy/mcp-rentals-ts`.

Uma nova implementação do servidor central em outra linguagem está em fase de planejamento/desenvolvimento.

## Fontes locais

Os IDs públicos correspondem aos diretórios: `alecorretoramg`,
`arthusoimoveis`, `cabralporto`, `casalinhares`, `epifanioimoveis`,
`helenaimoveis`, `imobiliariaportalmg`, `imobiliariavaleinvest`, `imovelweb`,
`marcioimoveis`, `minascaixaimoveis`, `niltoncorretordeimoveis`,
`novaimobiliaria`, `veraimobiliaria` e `vivareal`.

O checkout atual combina gitlinks e fontes locais não rastreadas.
Um clone limpo não garante a presença de todas as fontes. Especificações de
cada origem continuam nos seus próprios diretórios `docs/`.

