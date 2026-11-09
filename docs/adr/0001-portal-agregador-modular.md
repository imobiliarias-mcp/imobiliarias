# 0001 — Portal agregador modular, com MCP como uma das interfaces

**Status:** aceito

## Contexto

O projeto começou como um servidor MCP central para pesquisa de aluguéis em imobiliárias do Vale do Aço. O MCP era o objetivo principal: a entrega era uma ferramenta para agentes consultarem os provedores.

A necessidade real é outra: uma busca única de aluguéis para pessoas, com preço total, fotos, descrição e link para o site oficial. Essa experiência é um portal. O MCP continua útil, mas como interface para agentes.

## Decisão

O produto é um **portal agregador de imobiliárias**, altamente modular:

- **Núcleo** (`central_mcp/`): agrega resultados, normaliza, aplica limites e serve as interfaces. Não contém lógica de site de imobiliária.
- **Módulos de provedor** (um diretório ou submódulo por imobiliária): coleta e parsing em `src/`, adaptador em `scripts/mcp/tools.py`. O adaptador cumpre um contrato fixo de métodos e dicionários JSON simples. Cada chamada a um módulo roda em um subprocesso separado (`LocalVenvAdapter`), com o `PYTHONPATH` apontando para o diretório do módulo.
- **Interfaces** sobre o mesmo núcleo: portal web (`/`), API HTTP (`/api/*`) e MCP (`/mcp`, `/sse`).

## Consequências

- Adicionar ou trocar uma imobiliária é uma mudança em um módulo mais o registro descrito em `central_mcp/README.md` (seção 1.1). O núcleo não muda.
- O contrato do adaptador passa a ser o ponto de estabilidade. Mudanças nele exigem atualizar todos os módulos.
- Nomes técnicos (`central_mcp`, `*McpAdapter`, `scripts/mcp/`) foram mantidos. Renomear pacotes e submódulos quebraria o deploy, os submódulos e os ambientes existentes. O enquadramento é de portal, mesmo com esses nomes.
- Métricas de sucesso são de produto: busca única, resultados completos (fotos, preço total) e cobertura das imobiliárias. A quantidade de ferramentas MCP não é uma métrica.
