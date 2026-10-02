# Ferramentas e configuração MCP

## Host com transporte stdio

Instale as dependências e execute o build antes de iniciar o host. O comando
MCP deve executar `node` diretamente, sem `npm`, `tsx`, comandos de build ou
mensagens no stdout. Exemplo de configuração manual para um host local:

```json
{
  "mcpServers": {
    "aluguéis": {
      "command": "/caminho/absoluto/para/node",
      "args": [
        "/caminho/absoluto/mcp-rentals/dist/server/src/main.js"
      ],
      "env": {
        "SOURCES_ROOT": "/caminho/absoluto/fontes",
        "PYTHON_ENVIRONMENTS_ROOT": "/caminho/absoluto/ambientes"
      }
    }
  }
}
```

Use Node 24 e ambientes Python 3.14 separados em
`ambientes/{provider}/bin/python`, preparados com o lock daquele provedor.
O bridge usa as fontes locais em `fontes/{provider}` sem copiá-las para um
mesmo ambiente Python. Não copie `.venv` entre provedores. Sem
`PYTHON_ENVIRONMENTS_ROOT`, o registro verifica `.venv/bin/python` em cada
origem. Dependências ausentes retornam `not_installed`, não resultados vazios.

Não alteramos configurações de hosts automaticamente. O SDK negocia a revisão
moderna `2026-07-28` ou a inicialização legada conforme o cliente. Hosts sem
MCP Apps recebem texto útil e `structuredContent` validado; não precisam de
browser, HTTP ou modelo de linguagem.

## Catálogo antes da pesquisa

`list_rental_providers({})` informa os 15 IDs, os esquemas de filtros,
referências de detalhe, seletores de facetas, limitações e disponibilidade
local. Não consulta os sites nem afirma disponibilidade ao vivo.

Os filtros são específicos de cada origem. Nomes, IDs, slugs, valores de enum
e unidades não são intercambiáveis. Consulte os esquemas retornados em vez de
inventar um filtro universal. Toda pesquisa fixa a transação em aluguel.

Exemplo de busca federada com duas origens:

```json
{
  "requests": [
    {
      "provider": "alecorretoramg",
      "filters": {"bedrooms": 2, "max_price": 2000, "page": 1}
    },
    {
      "provider": "veraimobiliaria",
      "filters": {"city_id": 1, "bedrooms": 2, "max_price": 2000}
    }
  ]
}
```

Envie esse objeto a `search_rentals`. A lista aceita 1–15 origens diferentes.
ID desconhecido, duplicação, filtro extra, enum inválido ou combinação inválida
rejeita a chamada inteira antes de iniciar qualquer consulta.

O resultado preserva a ordem das requisições e o payload nativo em `native`.
A projeção `display` contém somente dados realmente conhecidos e links
públicos validados. Não há total global, deduplicação entre fontes, comparação
de preços heterogêneos ou paginação global. Campos e contagens de paginação
continuam específicos do provedor; desconhecido não vira zero.

## Detalhes e facetas

`get_rental_detail({provider, reference})` usa a referência descrita no catálogo.
Arthuso distingue explicitamente ID e slug:

```json
{
  "provider": "arthusoimoveis",
  "reference": {"kind": "slug", "value": "slug-real-do-card"}
}
```

Márcio, Vale Invest e Viva Real exigem a URL pública validada de um imóvel.
URLs de API, pesquisa, imagem, rede interna, portas, credenciais embutidas e
travessia de caminho são rejeitadas. Selecionar origens ou pesquisar não faz
consultas adicionais de detalhe apenas para descobrir links.

`get_rental_facets({provider, request})` exige o seletor real do catálogo:

```json
{
  "provider": "veraimobiliaria",
  "request": {"selector": "neighborhoods", "city_id": 1}
}
```

Minas Caixa também exige cidade para bairros. Arthuso oferece cidades,
bairros e tipos. Viva Real oferece sugestões, não um catálogo de facetas:

```json
{
  "provider": "vivareal",
  "request": {
    "selector": "location_suggestions", "query": "Timóteo", "size": 5
  }
}
```

Helena não oferece facetas: a chamada retorna `unsupported_capability`.
Outras origens usam `all` ou `locations`, conforme seu método real. Catálogos
compostos são atômicos: falha de um grupo invalida a operação completa.

## Falhas, cancelamento e limites

Sucesso de todas as origens tem `status: ok`. Algumas falhas produzem
`status: partial` e `isError: false`, com cada falha explícita no texto e nos
dados. Todas as falhas produzem `status: error` e `isError: true`.
Cancelamento da chamada inteira nunca é sucesso parcial.

Códigos incluem `invalid_input`, `unsupported_capability`, `not_installed`,
`blocked`, `rate_limited`, `http_error`, `invalid_content`, `tls_error`,
`timeout`, `cancelled`, `output_limit`, `invalid_output` e `worker_error`.
As mensagens não contêm credenciais, stderr bruto ou respostas externas.
403, 429, 5xx, desafios HTTP 200 e HTML inesperado não viram listas vazias.
Não há retries automáticos, downgrade TLS ou resolução de desafios de browser.

Padrões: três workers globais, um por origem, 30 segundos por origem e
180 segundos por chamada, incluindo a fila. Por worker: stdin 64 KiB,
stdout 1 MiB e stderr 64 KiB. O envelope MCP completo tem orçamento de
8 MiB, incluindo texto e conteúdo estruturado. Excesso gera erro explícito,
nunca truncamento silencioso de JSON. HTTP da origem também tem limites de
corpo e proteção contra descompressão; consulte o documento de desenvolvimento.

As configurações locais confiáveis podem ajustar `RENTAL_WORKERS`,
`RENTAL_WORKER_TIMEOUT_MS`, `RENTAL_DEADLINE_MS` e `RENTAL_STDOUT_BYTES`.
Valores inválidos falham antes de servir chamadas. Esses valores não são
argumentos MCP. `SOURCES_ROOT` e `PYTHON_ENVIRONMENTS_ROOT` selecionam somente
fontes e intérpretes locais administrados; usuários MCP não escolhem caminhos,
módulos, comandos, destinos de API ou bases de provedores.

Os testes Node em containers exigem `--init`, para que descendentes mortos
sejam recolhidos pelo subreaper em vez de permanecerem como zombies.
O runtime já inclui `tini -s`. Um comando de verificação local, no diretório
central, é:

```sh
docker --context docker-dev run --rm --init \
  --user "$(id -u):$(id -g)" -e npm_config_cache=/tmp/npm \
  -v "$PWD:/workspace" -w /workspace node:24-slim \
  sh -c 'npm ci && npm run check && npm run build && npm test'
```

Para o teste real da interface empacotada, com fixtures e sem consultas a sites:

```sh
docker --context docker-dev run --rm --init --ipc=host \
  --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$PWD:/workspace" -w /workspace \
  mcr.microsoft.com/playwright:v1.63.0-noble npm run test:browser
```

## Interface e desenvolvimento local

Hosts com Apps recebem `ui://rentals/search.html`, HTML único com formulário,
resultados, detalhe e paginação nativa em português. A UI usa apenas o bridge
do host, renderiza texto seguro, abre links com `App.openLink` e não baixa
imagens de terceiros. O recurso tem listas CSP de conexões, recursos externos
e frames vazias. Resultados obsoletos são ignorados e o teardown cancela as
operações do painel.

O modo HTTP opcional atende `/mcp` e `/health` apenas no desenvolvimento
local. Host e Origin são validados, sem CORS permissivo. Atrás de um proxy
de desenvolvimento, preserve esses cabeçalhos e mantenha acesso local.
Não configuramos Nginx Proxy Manager programaticamente nem autorizamos acesso
público. Instruções de Docker, locks, healthcheck e bootstrap das fontes estão
em [desenvolvimento](development.md).
