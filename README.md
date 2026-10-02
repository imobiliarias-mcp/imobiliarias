# Pesquisa de aluguéis — Vale do Aço

Monorepo de clientes e pesquisas de APIs públicas de 15 imobiliárias e portais.
Cada diretório mantém seu próprio pacote Python, documentação e testes.

## Servidor MCP central

[`mcp-rentals/`](mcp-rentals/README.md) reúne as fontes existentes sem modificar
os clientes: catálogo de capacidades, busca por origem ou federada, detalhes
e catálogos realmente suportados, com fallback textual e uma interface
MCP Apps em português.

O transporte padrão é `stdio`. O modo HTTP é opcional e restrito ao
desenvolvimento local. Não há autenticação pública, banco de dados ou
dependência de um modelo de linguagem. Consultas são somente de leitura;
bloqueios de sites são informados, não contornados.

Os filtros e a paginação continuam específicos de cada origem.
Consulte `list_rental_providers` antes de pesquisar.

## Fontes locais

Os IDs públicos correspondem aos diretórios: `alecorretoramg`,
`arthusoimoveis`, `cabralporto`, `casalinhares`, `epifanioimoveis`,
`helenaimoveis`, `imobiliariaportalmg`, `imobiliariavaleinvest`, `imovelweb`,
`marcioimoveis`, `minascaixaimoveis`, `niltoncorretordeimoveis`,
`novaimobiliaria`, `veraimobiliaria` e `vivareal`.

O checkout atual combina gitlinks e fontes locais não rastreadas.
Um clone limpo não garante a presença de todas as fontes; o build central
verifica os 15 diretórios e registra seus digests. O projeto central não
cadastra submódulos nem altera essa topologia.

Instruções de build, configuração de hosts, instalação isolada e testes
offline estão no [README central](mcp-rentals/README.md). Especificações de
cada origem continuam nos seus próprios diretórios `docs/`.

Os resultados dos testes e os limites de disponibilidade estão no
[registro de verificação](mcp-rentals/docs/verification.md).
