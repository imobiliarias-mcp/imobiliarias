# MCP central de pesquisa de aluguéis — planejamento atual

## Contexto

Em 2026-10-02, o usuário solicitou um MCP utilizando todos os módulos de aluguel da base atual e invocou `mcp-apps:create-mcp-app`. A entrega proposta é um único servidor MCP com descoberta de capacidades, pesquisa por provedor ou federada, detalhe/facetas onde realmente disponíveis e uma interface interativa para resultados com links públicos. Hosts sem MCP Apps continuam recebendo conteúdo textual e estruturado.

Este é um novo escopo arquitetural, não uma continuação da implementação de URLs abaixo. Só este arquivo pode ser editado durante o planejamento. A especificação e o plano serão apresentados juntos para aprovação; nenhuma implementação, instalação, sincronização Git ou publicação está autorizada nesta etapa.

## Direção de arquitetura

- Criar um projeto central independente na raiz, sem reescrever os clientes dos provedores ou cadastrar novos submódulos.
- Usar servidor TypeScript com SDK MCP 2.x e `@modelcontextprotocol/ext-apps`; UI Vanilla TypeScript empacotada em HTML único com Vite. Execução de desenvolvimento com `tsx`.
- Reutilizar o código Python através de workers isolados por provedor; não importar múltiplos pacotes `scripts` no mesmo processo.
- Registrar somente capacidades existentes e preservar o payload nativo junto de um envelope central de procedência, paginação e erros.
- Manter acesso público somente de leitura, sem contornar desafios de navegador, interpretar falhas como listas vazias ou criar URLs fictícias.

## Decisões de escopo e segurança

- O transporte padrão será `stdio`, sem servidor público, conta de usuário ou dependência de um modelo de linguagem. HTTP será um modo local opcional para verificação com um host de MCP Apps, com validação de Host/Origin e sem CORS permissivo. Deploy público, OAuth e configuração de NPM não fazem parte desta entrega.
- A UI terá formulário, resultados e estados de erro em português, respeitando tema e acessibilidade do host. Não haverá mapas, gráficos, favoritos persistentes, banco de dados ou downloads de imagens de terceiros nesta primeira versão. Links serão abertos pela API `App.openLink()`.
- A busca federada não terá paginação global fictícia, classificação por preços incomparáveis ou deduplicação que misture imóveis de provedores diferentes. Cada resultado mantém provedor, identificador e paginação nativa.
- Filtros não suportados serão rejeitados explicitamente, nunca ignorados. O catálogo de capacidades informa esquemas, identificadores e unidades usados por cada provedor.
- Processos terão concorrência, tempo e tamanho de saída limitados. Cancelamento/timeout encerra o worker e descendentes; limpeza de cliente, transporte e browser deve acontecer também no caminho de erro.
- Registry fixo: argumentos MCP não podem escolher caminho de Python, módulo, classe, comando shell, URL de API ou base de provedor. As configurações locais são confiáveis, validadas antes de servir chamadas e nunca incluídas nos resultados/logs se contiverem segredos.
- HTML vindo dos anúncios é dado não confiável. Usar renderização textual segura, validar HTTP(S) nos links e não permitir chamadas de rede na UI (`connectDomains`, `resourceDomains` e `frameDomains` vazios no recurso).

## Referências verificadas durante o planejamento

- [Exemplo oficial Vanilla MCP App](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/basic-server-vanillajs): `registerAppTool`, `registerAppResource`, URI `ui://`, `content` textual e `structuredContent`; handlers registrados antes de `App.connect()`.
- [API do SDK MCP Apps](https://github.com/modelcontextprotocol/ext-apps/blob/main/src/server/index.ts) e [tipos de segurança do recurso](https://github.com/modelcontextprotocol/ext-apps/blob/main/src/spec.types.ts): a CSP pertence a `contents[]._meta.ui.csp`, não à configuração de registro.
- [SDK TypeScript oficial indicado pelo usuário](https://github.com/modelcontextprotocol/typescript-sdk): `main` é SDK v2 estável, com pacotes separados e implementação da revisão `2026-07-28`. Reutilizar validação de schemas/outputs e erros do SDK, sem implementar protocolo JSON-RPC próprio.
- [Repositório oficial do protocolo indicado pelo usuário](https://github.com/modelcontextprotocol/modelcontextprotocol): fonte normativa da especificação e [schema `2026-07-28`](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/schema/2026-07-28/schema.ts).
- [Guia de versões do SDK](https://github.com/modelcontextprotocol/typescript-sdk/blob/main/docs/protocol-versions.md): usar `serveStdio(factory)` e `createMcpHandler(factory)` para servir era moderna e compatibilidade legada. O SDK negocia `server/discover` na era moderna e `initialize` na legada; não fixar manualmente uma única era nem duplicar wire encoding.
- [Transportes da revisão atual](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/transports/streamable-http.mdx): validação de Origin e bind local. A [revisão legada 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) fica como referência de compatibilidade, não como alvo principal.
- Consulta somente de leitura ao registry npm: `ext-apps` 2.0.3, SDK `server` 2.2.0 e `node` 2.1.0 publicados. Instalar versões compatíveis na implementação e registrar lockfile; não copiar versões do exemplo sem validar peers. Vite 8 requer Node ≥22.12 ou 20.19; recomendar Node 24 LTS.

## Contrato MCP proposto

Quatro ferramentas centrais, sem multiplicar dezenas de nomes equivalentes:

1. `list_rental_providers()` retorna os 15 IDs estáveis, capacidades reais, esquemas dos filtros, semântica de referências/paginação e disponibilidade de instalação local. Não faz consulta aos sites para afirmar saúde em tempo real.
2. `search_rentals({requests: [{provider, filters}]})` pesquisa um ou vários provedores, com 1–15 requisições explícitas. A transação é sempre aluguel e não pode ser sobrescrita para venda. `filters` passa por esquema fechado específico do provedor, incluindo sua paginação nativa. Provedor repetido ou desconhecido é inválido. O catálogo fornece os esquemas; na interface, os campos de cada provedor são apresentados com seus rótulos/unidades. Não inventar um filtro universal que mude a semântica da busca.
3. `get_rental_detail({provider, reference})` encaminha a referência com a semântica documentada para aquela origem, somente quando existe capacidade de detalhe.
4. `get_rental_facets({provider, request})` usa união fechada de seletores por origem. Vera: `cities` ou `neighborhoods` (exige `city_id`, tipo opcional e transação fixa de aluguel). Minas: `cities` ou `neighborhoods` (exige cidade). Arthuso: `cities`, `neighborhoods` ou `property_types`. VivaReal: `location_suggestions` (exige `query`, tamanho limitado). Nas origens com catálogo composto existente, usar seletor `all`/`locations` conforme o método real e informar seu alcance. Não preencher cidade faltante com Timóteo. Capacidade/selector ausente produz `unsupported_capability`; argumento obrigatório faltante é inválido. Catálogo composto é atômico: se um grupo falha, a ferramenta inteira retorna erro, sem apresentar os demais como catálogo completo.

O envelope de pesquisa contém `status` (`ok`, `partial`, `error`) e uma entrada por provedor solicitado, na mesma ordem da requisição. Cada entrada de sucesso contém o resultado nativo serializado sem perda de campos e uma projeção mínima para exibição (referência, URL, título, localização e preço quando realmente conhecidos). Paginação, contagem e indicação de próxima página pertencem ao provedor; valores desconhecidos continuam desconhecidos. Não somar contagens com significados diferentes como total global.

Antes de lançar qualquer worker, validar a requisição inteira: IDs, duplicatas, todos os filtros, selectors e referências. Argumento inválido retorna erro de ferramenta sem iniciar consultas, inclusive nas outras origens. Somente falhas de execução de entradas válidas geram sucesso parcial. Erro de uma origem contém código local normalizado e mensagem segura. As origens restantes continuam. Falha de todas as origens e erro de ferramenta individual retornam `isError: true`; sucesso parcial mantém `isError: false`, mas identifica explicitamente cada falha nos dados e no texto. Todo retorno tem fallback em `content`; resultados úteis também têm `structuredContent` com schema de saída validado. Cancelamento de toda a chamada não é sucesso parcial.

Buscas são somente de leitura (`readOnlyHint`, `destructiveHint: false`, `openWorldHint: true`); as annotations são informação, não substituem controles de segurança. Selecionar provedores não inicia chamadas de detalhe e não cria URLs: o link vem do serializer existente e é validado na fronteira central.

## Sequência de implementação após aprovação

### 1. Registro, contratos e testes de capacidades

- Confirmar estado Git e configurações disponíveis antes de qualquer mudança. Só sincronizar remoto que realmente exista; não tentar rebase de árvore suja nem cadastrar os quatro diretórios não rastreados automaticamente.
- Criar `mcp-rentals/` como projeto da raiz e registrar explicitamente os 15 provedores existentes, com referências a fontes/intérpretes locais confiáveis.
- Escrever primeiro testes de schemas, IDs desconhecidos, filtros extras, limites, capacidades ausentes e zero/um/vários resultados. Validar esquemas e testes do catálogo contra os métodos reais.

### 2. Bridge Python e adaptação dos provedores

- Criar `mcp-rentals/python/rental_bridge/worker.py`, contrato JSON versionado e adaptadores pequenos em `providers/`.
- Reutilizar uma camada existente por origem (core ou provider), escolhida pela cobertura e pelo contrato real; não duplicar parsers, HTTP nem regras de URL.
- Executar uma chamada por processo, em ambiente e diretório da origem. JSON em stdin/stdout; logs sanitizados em stderr. Validar novamente argumentos no Python, evitar shell e imports controlados por input.
- Testes offline dos 15 adaptadores usando fixtures/transportes simulados existentes, especialmente campos legados, referências públicas, paginação e ausência de chamadas extras.

### 3. Orquestração e servidor MCP

- Criar executor de workers, limitador de concorrência compartilhado entre chamadas, schemas de entrada/saída, agregador e quatro ferramentas em módulos focados. Defaults configuráveis: no máximo 3 workers simultâneos globalmente e 1 por origem, timeout de 30 s por origem, deadline de 180 s por chamada, stdin máximo de 64 KiB por origem, stdout máximo de 1 MiB por origem, stderr capturado com limite de 64 KiB e orçamento agregado de 8 MiB. Sem retries automáticos; respeitar e informar rate limits.
- Definir contratos em schemas TypeScript/Zod e exportar JSON Schema versionado para validação Python durante o build. O catálogo deriva dos mesmos schemas, sem copiar manualmente filtros entre tool, UI e worker; testes verificam equivalência e compatibilidade entre as duas linguagens.
- Aplicar timeout por origem/chamada, limite de bytes, cancelamento e encerramento de descendentes. Excesso de tamanho vira erro explícito da origem, sem truncar JSON silenciosamente.
- Registrar servidor `stdio` por padrão com `serveStdio(factory)`; modo HTTP local usa `createMcpHandler(factory)` e middleware oficial para Host, com política explícita de Origin. Manter compatibilidade legada habilitada. As factories reutilizam registro e limitadores compartilhados; não criar um orçamento de workers novo por request HTTP. Deixar negotiation, envelope e encoding a cargo do SDK. O comando de host deve executar `node` diretamente, evitando logs de `npm` no stdout do protocolo.
- Cobrir processos que encerram com erro, JSON inválido, stdout contaminado, resposta fora do contrato, timeout, cancelamento, falha parcial, limite global e shutdown. A fila também respeita o deadline; liberar slots e remover trabalhos pendentes quando cancelados.
- Propagar progresso por origem quando o cliente/host negociar suporte, usando o contexto do SDK; configurar timeout de cliente/UI compatível com o deadline. Mesmo sem progresso negociado, a resposta final informa resultados parciais e o encerramento continua limitado.

### 4. MCP App de resultados

- Criar recurso `ui://rentals/search.html`, associado à ferramenta de busca; empacotar HTML, CSS e JS em um arquivo.
- Usar `App` do SDK e registrar todos os handlers antes de conectar. Receber resultados do host e chamar as mesmas ferramentas pelo bridge do host; não fazer fetch direto para sites/servidor.
- Formulário por origem, lista de resultados, detalhe suportado e controles de próxima página por origem. Mostrar mensagens distintas para busca vazia, filtro inválido, provedor indisponível, timeout, bloqueio HTTP e cancelamento.
- Texto via DOM seguro, links por `App.openLink`, tema do host, labels, navegação por teclado e recuperação de erro. Ignorar resultados obsoletos quando uma busca nova substitui outra.

### 5. Empacotamento, integração e documentação

- Dependências Node instaladas com `npm install` e lockfile; build TypeScript/Vite, execução `tsx` em desenvolvimento e Node 24 LTS no runtime.
- Criar `python/pyproject.toml` para o bridge (inclui `jsonschema`, dependências dos adapters centrais e dev). Manter locks de instalação com hashes em `python/locks/{provider}.requirements.txt`, gerados dos metadados de cada origem mais dependências do bridge, com extras de testes separados. Registrar complementos necessários, como `requests` para Minas e `patchright`/`lxml` para importar Imovelweb, sem alterar locks dos subprojetos ou copiar `.venv`. Gerar e validar locks para Python 3.14/Linux usado no Docker. Schemas exportados residem em `dist/contracts/providers.json`, são empacotados no build e verificados pelo worker; não depender de arquivos temporários de desenvolvimento.
- Docker multi-stage com runtimes Node/Python compatíveis e cache separado de dependências/código. Ambientes Python por provedor evitam conflitos; incluir fontes locais explicitamente, excluindo `.git`, `.env`, credenciais, `.venv`, caches e artefatos.
- Validar que os 15 diretórios necessários existem e registrar revisões/digests de fontes usadas no build. Criar staging temporário de build por allowlist de código/metadados/fixtures necessários, inclusive quando as fontes estiverem fora de um worktree; não enviar o checkout inteiro ao Docker. Gerador/manifests ficam no projeto central e staging é gitignored. Não afirmar que um clone limpo possui os diretórios hoje não rastreados; documentar bootstrap de fontes locais sem mudar a topologia Git.
- Documentar configuração stdio para hosts, modo HTTP apenas local, comandos Docker `docker-dev`, catálogo/filtros/erros, limite de chamadas, pré-requisitos de dependências de browser e comportamento sem UI. Não editar configurações do host automaticamente nem publicar containers.

## Reutilização confirmada e critérios de escolha

Não registrar os `scripts/mcp/tools.py` existentes diretamente no servidor central: vários desses wrappers anunciam parâmetros que não aplicam ao filtro. A integração deve construir critérios/value objects e chamar os clientes/provedores, mantendo as regras já implementadas nos builders.

| Origem | Camada escolhida | Operações reutilizadas |
|---|---|---|
| Alê | Core `AleCorretoraRentalClient` | `search`/`search_rentals`, `get_details`, `get_locations` |
| Arthuso | Core `RentalResearchService` | `search_rentals(criteria, pagination)`, `get_property_by_id`/`get_property_by_slug`, três catálogos de taxonomias |
| Cabral Porto | Core `CabralPortoRentalClient` | `search`, `get_details`, `get_facets`; maior cobertura de critérios/facetas que o adapter |
| Casa Linhares | `CasaLinharesRentalProvider` | `search_rentals`, `get_property_detail`, `get_facets`; resolver de tenant existente |
| Epifânio | Core `EpifanioRentalClient` | `search` com critérios completos, `get_details`, `get_locations` |
| Helena | Core de `helena_research.application.service` | Busca, detalhe e fotos; não anunciar facetas sem método existente |
| Portal Imóveis MG | `scripts/providers/portalmg.py` | Busca, detalhe e facetas; o core delega a `scripts.*` |
| Vale Invest | `scripts/providers/vale_invest.py` | Busca, detalhe e facetas; evitar o wrapper MCP que limita combinações de preço |
| Imovelweb | `scripts/providers/imovelweb.py`, com `HttpTransport` injetado | Busca, detalhe e facetas com HTTP normal; não chamar `create_default()` nem transporte de evasão |
| Márcio | Core `marcio_research.providers.marcio` | Busca, detalhe e facetas; não registrar cópia paralela de `scripts/` |
| Minas Caixa | Core `minascaixa.application.RentalResearchService` | `search_rentals(criteria, pagination)` retorna `(total_count, collection)`; `get_property_detail`, `get_cities`, `get_neighborhoods(city)` sem cidade fixa |
| Nilton | Core `NiltonRentalClient` | Busca, detalhe e localizações; critérios completos do core |
| Nova | Core de `nova_research.client` | Busca, detalhe e localizações; resultado nativo usa `items` |
| Vera | Core de `vera_research.client` | Busca, detalhe e catálogos de cidades/bairros; paginação nativa |
| VivaReal | Core de `vivareal_research.client` | Busca, detalhe por URL e sugestões de localização; não confundir sugestões com catálogo de facetas |

IDs públicos do catálogo correspondem aos diretórios da raiz (`alecorretoramg`, `arthusoimoveis`, `cabralporto`, `casalinhares`, `epifanioimoveis`, `helenaimoveis`, `imobiliariaportalmg`, `imobiliariavaleinvest`, `imovelweb`, `marcioimoveis`, `minascaixaimoveis`, `niltoncorretordeimoveis`, `novaimobiliaria`, `veraimobiliaria`, `vivareal`). Nomes internos dos adapters continuam intactos.

`get_rental_facets` distinguirá `kind: "catalog"` de `kind: "location_suggestions"`; sugestões do VivaReal exigem os argumentos do método existente. Helena retornará `unsupported_capability` nesse endpoint. Não inventar catálogos nem ampliar APIs dos provedores para completar a tabela.

Pontos críticos já verificados:

- `arthusoimoveis/arthuso/application/service.py:73`: busca exige critérios **e** `PaginationSpec`; detalhe por post ID e por slug são métodos diferentes. Descrever tipo de referência no catálogo, sem transformar slug em ID.
- `cabralporto/src/cabralporto_research/client.py:25`: `search(SearchCriteria)` permite construir critérios completos; `get_facets()` integra estados, bairros e tipos. Cabral também altera `socket.getaddrinfo` na construção de transporte: isolamento é necessário além da colisão de imports.
- `casalinhares/scripts/providers/casalinhares.py:49`: resolver de banco/tenant faz parte do fluxo normal; manter suas chamadas, não prometer que toda pesquisa usa exatamente um request de rede. Apenas proibir request adicional de detalhe para descobrir links.
- `epifanioimoveis/src/epifanio_research/domain/criteria.py:92`: `SearchCriteria` composto suporta mais campos do que a factory de conveniência. Mapear campos efetivos pelo builder, não só pela assinatura de `search_rentals`.
- `alecorretoramg/src/alecorretora_research/domain/listing.py:82`: reutilizar serializer de pesquisa e metadados `current_page`, `max_pages`, `total_found`.
- `arthusoimoveis/arthuso/domain/models.py:106`: detalhe não tem serializer próprio. Criar serializer explícito apenas no bridge central, reutilizando `summary.to_dictionary()`; não expor `__dict__`, objetos de transporte ou estado privado. A mesma regra vale para detalhes/facetas tipados sem serializer nos demais cores.
- `cabralporto/src/cabralporto_research/collaborators.py:32` e `infrastructure/http_client.py:71`: busca/facetas não validam status HTTP antes de devolver a resposta. Injetar no bridge um decorator pequeno de transporte que valide status/conteúdo antes do parser, mantendo requests, URLs e parsing existentes. Não esconder 403/429/5xx como coleção vazia. Aplicar essa proteção nas origens que apresentam a mesma lacuna, com testes offline.

A referência de detalhe terá schema específico por provedor: ID, código público, slug ou URL não são intercambiáveis. Para referências URL (VivaReal, Márcio e Vale Invest), validar origem pública e rota de imóvel por allowlist/configuração confiável antes de executar; rejeitar credenciais embutidas, portas não configuradas, travessia de caminho e URLs de rede interna, API, imagem ou pesquisa. Validar também redirecionamentos nas fronteiras dos transports centrais; não permitir que o detalhe se torne fetch arbitrário.

### Correções de integração necessárias, sem alterar os subprojetos

- **Imovelweb:** `scripts/client/http_transport.py:20` e `scripts/providers/imovelweb.py:33` usam browser com flags de evasão no default. Construir `ImovelwebRentalProvider` explicitamente com `HttpTransport` e cliente HTTP gerenciado; não iniciar Patchright/browser nem solucionar desafios. Sua importação ainda exige o pacote Python declarado, mas não exige instalar binários de browser para atender esse caminho. `query_builder.py:56` rejeita preço: o catálogo central não oferecerá limites de preço nessa origem. HTTP 403 ou página de desafio recebe erro `blocked`, nunca lista vazia; disponibilidade ao vivo não é garantida.
- **Márcio:** `src/marcio_research/client/http_transport.py:48` desabilita TLS. Injetar um adapter central seguro compatível com `HttpTransportProtocol`, reutilizando headers da configuração e o formato `HttpResponse`. Não usar o default inseguro nem desabilitar TLS após erro. `providers/marcio.py:62` aceita URLs arbitrárias e cria fallback de slug quando código não resolve: o detalhe central usará somente URL pública validada de um card, com o parser/provider existente, evitando a ramificação de fallback por código.
- **Vale Invest:** `scripts/client/query_builder.py:105` fixa cidade/bairro/tipo no detalhe por ID numérico. A referência central de detalhe será a URL validada do card; reutilizar `ValeInvestHttpTransport.get_text` e `ValeInvestPropertyDetailParser.parse_property_detail` diretamente no adapter central, sem essa rota fixa. Não anunciar lookup numérico como funcional nesse caminho.
- **Minas Caixa:** usar o core e preservar `total_count` separado da coleção (`to_dictionary_list()`). Seu `SearchPayloadBuilder` não aplica bairro/tipo, portanto esses filtros não serão anunciados. Os catálogos de bairros recebem cidade explícita por `get_neighborhoods(city)`, evitando a cidade fixa do adapter. Montar service com `requests.Session` gerenciada por contexto, transport e deserializer públicos, sem buscar estado privado da factory.
- **Portal MG:** preservar `pagina` como offset calculado pelo builder e as page sizes existentes; o central recebe `page_number` e deixa o módulo traduzir. `get_facets()` usa seus endpoints fixos e dados sem cidade: anunciar o alcance efetivo; não prometer catálogo dependente de cidade ou configuração de base que esse método não utiliza.
- **Vera:** não ativar postfiltro local de quartos por default. Expor a semântica efetiva da query e preservar contagens nativas; não reinterpretar a contagem do servidor como contagem de itens pós-filtrados.

- **VivaReal:** `src/vivareal_research/domain/listing.py:55` não possui serializer de pesquisa; o core armazena `canonical_url`. Criar serializer explícito central para pesquisa, detalhe e sugestões, preservando IDs, `canonical_url`, `total_count`, campos opcionais e desconhecidos. A projeção pública `url` usa esse `canonical_url` validado, não o URL da Glue API; custos ausentes não viram zero conhecido nem total mensal inventado.
- **Guard de conteúdo:** HTTP 200 não comprova pesquisa válida. Em Imovelweb, `scripts/client/parsers.py:132` aceita qualquer HTML sem cards como vazio; validar identidade/estrutura esperada da página, marcadores contextuais de desafio/erro e marcador explícito de pesquisa sem resultados antes de chamar o parser. Não detectar bloqueio apenas pela palavra Cloudflare. Usar fixtures de desafio 200, HTML inesperado e zero legítimo; aplicar guards equivalentes onde outros parsers silenciosamente aceitam conteúdo fora do contrato.

Clientes persistentes serão construídos explicitamente com ownership no bridge e fechados em contexto/finally. Nos clientes stateless, reutilizar os context managers existentes. Essa adaptação não exige novos métodos `close()` nos provedores nem acesso a atributos privados.

## Estado da raiz confirmado na inspeção

`README.md` contém somente boilerplate e `docs/README.md` não existe; não há aplicação central ou infraestrutura de build na raiz que possa ser reaproveitada. A raiz não tem remoto. Vale Invest, Imovelweb, Márcio e VivaReal continuam diretórios não rastreados na raiz; os demais são gitlinks. O caminho `source/repos/imobiliarias` resolve ao mesmo workspace observado como `repos/imobiliarias`; usar paths resolvidos, sem duplicar fontes ou assumir dois checkouts independentes. Apenas o arquivo autorizado de plano foi editado nesta etapa.

## Arquivos centrais previstos

- `mcp-rentals/package.json`, `package-lock.json`, `tsconfig*.json`, `vite.config.ts`: dependências/builds separados de UI e servidor, sem apagar o HTML ao compilar servidor.
- `mcp-rentals/src/{server.ts,main.ts,configuration.ts,contracts/,providers/registry.ts}`: factory do servidor, transportes e catálogo fixo.
- `mcp-rentals/src/workers/`, `application/`, `tools/`: lançamento/limpeza, agregação e ferramentas; não concentrar todas as responsabilidades em `server.ts`.
- `mcp-rentals/python/rental_bridge/{worker.py,contracts.py,providers/,serialization/,transport/}`: adaptação local por origem e validação de fronteiras.
- `mcp-rentals/ui/{mcp-app.html,app.ts,components/,styles.css}`: formulário, lista e detalhe com lifecycle do host.
- `mcp-rentals/tests/{contracts,workers,tools,ui,e2e}/`, `python/tests/`: testes centrais e de integração local.
- `mcp-rentals/Dockerfile`, configuração Docker de desenvolvimento, `.env.example`, `.gitignore`, `README.md`; substituir o boilerplate da raiz `README.md` por apresentação/entrada curta para o servidor e provedores, sem criar um índice `docs/README.md` só para uniformidade.

Todo código novo segue SOLID/composição e limites de Object Calisthenics do projeto; dividir módulos, funções e estado quando necessário. Usar docstrings/descrições públicas concisas, sem getters artificiais ou comentários narrando as alterações. Não modificar os 15 repositórios para uniformizar interfaces que o bridge consegue adaptar.

## Verificação e critérios de aceite

Aplicar RED → GREEN em cada etapa. Instalações/builds e testes somente após aprovação, no contexto `docker-dev`; não executar pesquisas reais para desenvolver o contrato.

1. **Catálogo:** teste enumera exatamente os 15 IDs, métodos reais, filtros, tipos de referência e limitações. Capacidade indisponível não é anunciada como funcional; configuração inválida falha cedo sem rede.
2. **Filtros:** testes de contrato conferem cada filtro anunciado no request gerado pelo builder real, não apenas no mock do provider. Cobrir intervalo de preço, mínimo/exato de quartos, slugs/IDs, zero, texto vazio, enums e paginação. Filtro existente na assinatura mas ignorado no builder não entra no catálogo central.
3. **Adaptação:** fixtures de zero/um/vários imóveis para todas as origens, serializers nativos preservados, URLs públicas idênticas na UI/texto/JSON, sem requests extras de detalhe; detalhes/catálogos tipados convertidos explicitamente. VivaReal cobre `canonical_url`/`url`, `total_count`, campos físicos opcionais e encargos desconhecidos; Minas cobre o retorno `(total_count, collection)`; Vera/Minas cobrem catálogos de duas cidades distintas e argumento de cidade obrigatório.
4. **Falhas:** 403, 429, 5xx, conteúdo inválido e desafio HTTP 200 não viram pesquisa vazia; fixtures distinguem desafio, HTML inesperado e pesquisa legitimamente vazia. Todas as falhas/algumas falhas, origem não instalada, detalhe ausente e capability não suportada têm resultados distintos. Um filtro inválido em qualquer entrada inicia zero workers; falha de um grupo de catálogo composto não apresenta catálogo completo. Erro TLS permanece erro, sem downgrade.
5. **Isolamento:** executar duas origens com `scripts.*` em paralelo e comprovar que os imports não se misturam. Testar limite global, worker neto, cancelamento, timeout, erro de saída, bytes excedidos, finalização e ausência de processos/clientes/browser órfãos.
6. **MCP real:** cliente oficial contra stdio/HTTP com workers offline cobre tanto `initialize` legado quanto `server/discover` da revisão `2026-07-28`, `tools/list`, `tools/call`, schemas e `resources/read`; stdout contém só protocolo. Usar negotiation explícita nos testes, não lançar probes adicionais em todas as conexões stdio por default. Testar encoding/normalização de `structuredContent` e cancelamento em ambas as eras através do SDK. Hosts sem Apps recebem `content` útil. Modo HTTP local testa Host/Origin inválidos e shutdown; healthcheck não depende de `ping` MCP ausente na era moderna.
7. **UI:** testar `ontoolinput`, `ontoolresult`, `ontoolcancelled`, mudança de tema e teardown, filtro/erro/detalhe/paginação, mensagens antigas, texto malicioso e links inválidos. Inspecionar CSP em `contents[]._meta.ui.csp`. Testar o HTML bundle com host local de referência e fixtures, não sites públicos. Qualquer captura fica em `.playwright-mcp`, gitignored.
8. **Qualidade:** `npm ci`, build/TypeScript, testes Node/UI e pytest/Ruff do bridge. Rodar suítes offline dos provedores separadamente, com rede desabilitada e testes live explicitamente excluídos; relatar diagnósticos herdados separadamente. Verificar Markdown, `.env.example` sem segredos e `git diff --check`.
9. **Build reproducível:** imagem criada com fontes/locks identificados inclui os 15 módulos e seus imports, sem `.env` ou histórico Git. Smoke de saúde valida processo/registro, não disponibilidade dos sites. HTTP de desenvolvimento usa `TZ=America/Sao_Paulo`, healthcheck e publicação restrita ao ambiente local; modo stdio termina limpo no fechamento do host.

O aceite exige as 15 origens integradas à busca, chamadas suportadas preservadas, erro explícito onde capacidade/fonte falta, fallback textual e MCP App funcional com fixtures. Nenhum teste offline prova disponibilidade ao vivo; smoke público posterior é limitado, opcional e não deve contornar bloqueios.

## Limites desta aprovação

A implementação autorizada por este plano se limita ao novo projeto central e à sua documentação/configuração de desenvolvimento. Não fazer push, abrir PR, mergear branches, registrar os quatro diretórios como submódulos, reescrever provedores ou alterar configurações MCP globais/NPM automaticamente. Preservar as revisões existentes e alterações alheias; caso a execução use worktree, os workers devem apontar fontes identificadas do checkout original em modo somente leitura, pois os diretórios não rastreados não aparecerão no novo worktree.

A inspeção cobriu as 15 origens. A revisão independente somente de leitura identificou cinco lacunas — serializer de pesquisa do VivaReal, escopo dos catálogos, locks Python, validação de HTML 200 e fronteira de erro de entrada versus falha parcial — incorporadas ao desenho acima. Este plano não afirma build, testes ou acesso ao vivo bem-sucedidos: nenhum deles foi executado nesta fase.

---

<details>
<summary>Plano histórico de URLs — preservado como referência; não executar neste novo escopo</summary>

# Plano histórico: link público do imóvel em todos os resultados de pesquisa

## Contexto

O usuário quer abrir a página do imóvel diretamente a partir de cada resultado de pesquisa dos 15 módulos. Hoje alguns provedores retornam o link, outros guardam apenas um caminho relativo e outros descartam o endereço ao construir o adaptador/JSON. O objetivo é disponibilizar o link também nas saídas programáticas, MCP e CLI existentes, sem consultar o detalhe de cada imóvel apenas para descobrir sua URL.

**Arquitetura:** mudança aditiva nos fluxos existentes, com resolução de URLs dentro de cada módulo e preservação dos campos legados. Não criar dependência compartilhada entre repositórios nem novos servidores/adaptadores MCP ou CLIs onde essas interfaces não existem.

**Tecnologias:** Python, `urllib.parse`, parsers/entidades/configurações existentes, pytest, Ruff e Docker `docker-dev`.

> Implementação somente após aprovação deste plano. Aplicar TDD por tarefa; usar `superpowers:executing-plans` ou `superpowers:subagent-driven-development` conforme o modo de execução adotado.

## Contrato de saída

- Cada imóvel serializado deve conter `url`: uma string HTTP(S) absoluta apontando à página pública daquele imóvel. Nunca usar a URL da API, da imagem ou da pesquisa.
- Preservar os demais campos, tipos de coleção e atributos existentes. Manter campos legados como `detail_url`, `url_path` e `canonical_path`, inclusive os caminhos relativos usados por consumidores.
- Márcio e VivaReal já possuem a chave `url`: normalizar seu valor quando vier relativo é a alteração intencional desse campo; não criar uma segunda chave concorrente.
- Preferir o link presente no card/JSON. Se ausente, usar somente uma rota pública já suportada/documentada e o identificador correto. Não inventar slug nem usar o ID interno da API como código público.
- Se não existir link recuperável nem fallback público válido, levantar a exceção local de extração/validação com contexto do imóvel. Não devolver `null`, string vazia ou link fictício como se atendesse ao contrato.
- Usar a base pública configurada do provedor, distinta da base da API. Injetar configuração/resolução nos parsers ou fronteiras da aplicação; serializers de domínio não devem consultar ambiente, rede ou configuração global mutável.
- Preservar parâmetros que identificam o imóvel, como `?id=608`. Manter regras já existentes de remoção de tracking, sem alterar os campos legados correspondentes.
- Exibir o link nas CLIs e nos trechos de pesquisa dos runners de verificação existentes. Não modificar filtros, preços, classificação, paginação ou condições de disponibilidade.

## Diagnóstico dos 15 módulos

| Módulo | Situação atual | Mudança necessária |
|---|---|---|
| Alê | Core conserva `ListingSummary.url`; runner não o apresenta; não há serializer de pesquisa | Manter o campo, normalizar quando necessário, acrescentar representação serializável e mostrar no runner |
| Arthuso | Core conserva `detail_url`; runner já mostra o endereço | Acrescentar `url` na representação serializável sem remover `detail_url` |
| Cabral Porto | Core serializa `detail_url`; adaptador descarta o `url` recebido da API | Preservar o link nas duas camadas, adicionar `url` e mostrar na CLI |
| Casa Linhares | Parser ignora `site_url` do JSON | Resolver `site_url` contra a origem pública e propagá-lo para entidade, JSON, MCP e CLI |
| Epifânio | Core conserva `data-link` em `url_path`; adaptador descarta o endereço | Preservar o caminho, acrescentar URL absoluta à representação pública e corrigir o adaptador |
| Helena | Core conserva `url_path`; não há serializer nem adaptador MCP de pesquisa | Acrescentar representação serializável com `url` e mostrar no runner existente |
| Portal Imóveis MG | JSON/MCP já devolvem `detail_url`, mas relativo | Manter `detail_url`, adicionar `url` absoluto e mostrar na CLI |
| Vale Invest | Parser usa o `href` apenas para obter o ID e descarta o link | Propagar o `href`; não usar o fallback que fixa cidade/tipo de imóvel |
| Márcio | Core e scripts já devolvem `url`; CLI já imprime o endereço | Normalizar links relativos e verificar paridade das duas implementações |
| Minas Caixa | Core e adaptador não possuem link; pesquisa fornece `codigo` | Construir a rota pública documentada `/detalhe-imovel/{codigo}` e propagar o resultado |
| Nilton | Core conserva `url_path`; adaptador usa o caminho só para extrair código | Acrescentar representação com `url`, preservar o link no adaptador e mostrar no runner |
| Nova | Core conserva `canonical_path` relativo; não há CLI/MCP de pesquisa | Usar a base pública `https://jnovaimobiliaria.com.br` e acrescentar representação serializável |
| Vera | Core conserva `url_path`; CLI não imprime o link | Acrescentar representação serializável e mostrar o link na CLI existente |
| Imovelweb | JSON/MCP devolvem apenas `url_path` relativo | Preservar `url_path`, adicionar `url` absoluto e mostrar na CLI |
| VivaReal | MCP já devolve `url` e CLI já imprime; `link.href` pode ser relativo | Resolver contra a base web, não a base Glue API, e testar todas as saídas |

## Reutilização e arquivos críticos

Aplicar os padrões abaixo nos arquivos equivalentes de cada módulo, sem reescrever parsers que já cumprem o contrato:

- **Links dos cards:** reutilizar `CardFeatureExtractor._extract_url` em `alecorretoramg/src/alecorretora_research/parsers/feature_extractor.py`, `SearchHtmlParser._extract_link_info` em `arthusoimoveis/arthuso/infrastructure/html_parser.py`, os parsers `data-link` dos módulos ImobiBrasil e o `href` de Vale Invest.
- **Construção já existente:** reutilizar a resolução de `detail_url` em `cabralporto/src/cabralporto_research/parsers/search_parser.py`, `PortalMGConfiguration.detail_url()` em `imobiliariaportalmg/scripts/client/configuration.py` e os builders públicos `/imovel/{id}` apenas como fallback válido. Não confundir o builder da página de pesquisa de Cabral com um link de imóvel.
- **Link atualmente descartado:** corrigir parsers como `casalinhares/scripts/client/parsers.py` e `imobiliariavaleinvest/scripts/client/parsers.py`; suas entidades e collections já possuem `to_dictionary()` e fazem o encaminhamento ao MCP.
- **DTOs e composição:** ajustar `scripts/domain/entities.py` dos adaptadores afetados. Para estruturas de dois campos como `ListingDetails(location_summary, media_url)`, decompor mídia/navegação em um colaborador pequeno; não acrescentar indiscriminadamente um terceiro campo. Preservar as chaves públicas, como `media_url`, e o comportamento de `format_summary()`.
- **Resultados tipados:** adicionar comportamento de serialização nas entidades/collections existentes, como `novaimobiliaria/src/nova_research/domain/listing.py` e os modelos de Alê, Arthuso, Helena, Epifânio, Nilton e Vera. A URL resolvida deve entrar pela fronteira de parsing/aplicação, mantendo o domínio puro e a API existente compatível.
- **Saídas já quase prontas:** `imovelweb/scripts/domain/entities.py`, `vivareal/scripts/mcp/tools.py` e as duas cópias de parser/entidade de Márcio em `scripts/` e `src/marcio_research/`.
- **Documentação:** atualizar os documentos de API/uso e índices existentes dos módulos efetivamente alterados, incluindo exemplos do novo campo. Não criar documentação ou interfaces de subsistemas ausentes apenas para completar a tabela.

## Tarefas de implementação

### 1. Resolução pública e testes de contrato locais

- [ ] Registrar o estado inicial de cada repositório e preservar as alterações alheias antes de trabalhar.
- [ ] Acrescentar testes de regressão para o `url` absoluto na saída de pesquisa, usando fixtures e transportes simulados já existentes.
- [ ] Assistir aos testes falharem pelo link ausente/relativo, não por imports ou dependências faltantes.
- [ ] Implementar normalização local com `urljoin` e validação de esquema/host, reutilizando configuração e builders existentes. Novos argumentos de configuração devem ser opcionais para manter os chamadores atuais.
- [ ] Cobrir explicitamente base de API versus base pública, parâmetro `id`, URLs inválidas e fallback documentado. Para Minas Caixa, usar o código validado e a rota pública, sem inventar slug.

### 2. Propagar os links que hoje são descartados ou inexistentes

**Provedores:** Cabral Porto, Casa Linhares, Epifânio, Vale Invest, Minas Caixa e Nilton.

- [ ] Transportar o endereço do parser até o modelo e `to_dictionary()`, conservando preços, imagens e demais campos.
- [ ] Usar composição focada para metadados de mídia/navegação nos adaptadores; respeitar métodos pequenos, limite de campos e módulos menores que 200 linhas no código novo.
- [ ] Conferir ambas as camadas nos provedores que têm core e adaptador independentes; façades que já delegam ao adaptador não precisam duplicar a lógica.
- [ ] Adicionar testes offline de parser, serializer, resultado MCP e ausência de consultas extras. Os runners `run_tests.py` orientados a endpoints ao vivo não substituem esses testes.

### 3. Expor a representação serializável dos resultados tipados

**Provedores:** Alê, Arthuso, Epifânio, Helena, Nilton, Nova e Vera.

- [ ] Manter o tipo retornado por `search` e as collections existentes.
- [ ] Acrescentar `to_dictionary()` ou o comportamento equivalente já adotado pelo projeto para cada imóvel e coleção, incluindo `url` e preservando os atributos/caminhos nativos.
- [ ] Cobrir zero, um e vários resultados; preservar contagens e metadados de paginação.
- [ ] Não criar adaptadores MCP, CLI de pesquisa ou novo pacote central onde essas interfaces não existem.

### 4. Completar JSON/MCP e apresentação existentes

**Provedores com link parcial/já presente:** Portal Imóveis MG, Imovelweb, Márcio e VivaReal; demais provedores após as tarefas anteriores.

- [ ] Portal: manter `detail_url` e acrescentar `url` absoluto.
- [ ] Imovelweb: manter `url_path` e acrescentar `url` absoluto, sem depender do browser para testar a serialização.
- [ ] Márcio: testar a normalização e o mesmo contrato em `scripts/` e `src/`, mantendo os modos texto/JSON existentes.
- [ ] VivaReal: normalizar `link.href` contra a base web e verificar a chave `url` já presente no MCP e na CLI.
- [ ] Mostrar `Link: <URL pública>` junto a cada resultado nas CLIs/runners existentes que ainda omitem essa informação; capturar stdout com clientes simulados.
- [ ] Atualizar documentação e exemplos para os caminhos de saída que mudaram.

## Exemplo concreto de regressão

Em `casalinhares/tests/test_search_urls.py`, testar a assinatura planejada `SearchResultParser(public_base_url=...)`, com default preservado para os chamadores existentes:

```python
from scripts.client.parsers import SearchResultParser

PROPERTY_PATH = "/imovel/apartamento-2-quartos-eldorado-timoteo-1-vaga-code-1427"
PUBLIC_BASE = "https://www.casalinhares.com.br"
CARD = {
    "code": "1427", "site_title": "Apartamento", "rental_value": 1500,
    "site_url": PROPERTY_PATH,
}
PAYLOAD = {"properties": {"count": 1, "properties": [CARD]}}


def test_search_serializes_public_property_url():
    parser = SearchResultParser(public_base_url=PUBLIC_BASE)
    result = parser.parse_search_response(PAYLOAD)
    serialized = result.to_dictionary()
    item = serialized["listings"][0]
    assert item["url"] == PUBLIC_BASE + PROPERTY_PATH
    assert item["code"] == "1427"
    assert item["rental_price"] == 1500
    assert serialized["returned_count"] == 1
```

Estender a matriz de entradas em cada módulo com URL absoluta, caminho relativo, URL relativa ao protocolo, query identificadora, ausência com fallback válido e entrada inválida/irrecuperável. Nos adaptadores MCP, afirmar a mesma URL por imóvel e as chaves legadas; nos transportes simulados, afirmar que só ocorreram as chamadas originais da pesquisa.

## Verificação final e aceite

- [ ] Executar cada projeto em um processo separado no contexto Docker `docker-dev`; os vários pacotes `scripts` não podem ser importados juntos em um teste global improvisado.
- [ ] Rodar testes de parser, domínio/serialização, cliente/provedor, MCP e captura CLI pertinentes; depois a suíte de cada módulo. Registrar falhas ambientais/preexistentes separadamente.
- [ ] Usar as dependências de cada projeto; Imovelweb precisa de `lxml` e `patchright` para importar seu transporte, mas os testes deste contrato não precisam resolver desafios de navegador.
- [ ] Rodar Ruff nos arquivos alterados e verificações estáticas de documentação; revisar diffs para preservar campos, preços, filtros e paginação.
- [ ] Confirmar os 15 provedores: cada imóvel retornado possui um link público recuperável, cada representação serializada expõe `url` absoluto e as interfaces existentes o conservam/exibem.
- [ ] Fazer somente smoke tests públicos limitados quando disponíveis; HTTP 403 ou indisponibilidade não equivale a coleção vazia e não justifica contornar desafios externos.

Exemplo de comando **para a implementação**, não executado durante o planejamento:

```bash
docker --context docker-dev run --rm \
  -v /home/samuelcaldas/source/repos/imobiliarias/cabralporto:/workspace:ro \
  -w /workspace python:3.14-slim sh -c '
    python -m venv /tmp/venv &&
    /tmp/venv/bin/pip install -q httpx beautifulsoup4 pytest ruff &&
    /tmp/venv/bin/python -m pytest -p no:cacheprovider \
      --ignore=tests/test_live_integration.py -q
  '
```

## Preservação e limites

A raiz está em `main`, no commit `b97f53d`. Há alterações preexistentes em Nilton e Vera e diretórios/arquivos não rastreados; não incluí-los indiscriminadamente nas mudanças. A raiz não tem remoto configurado, e faltam mapeamentos de `.gitmodules`; corrigir/cadastrar a estrutura de submódulos não faz parte desta tarefa.

Durante o planejamento, apenas este arquivo pode ser alterado. Não executar testes, instalar dependências, fazer fetch/rebase, criar branches/commits ou publicar conteúdo nesta etapa. Na implementação, verificar o estado e os remotos antes das operações Git; não fazer push nem cadastrar os diretórios não rastreados como novos submódulos sem autorização específica.

</details>
