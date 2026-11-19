# Plano: migrar módulos de scraping HTML para clientes de API interna (XHR/JSON)

## Contexto
O pedido parte de que a codebase usa "renderização completa de navegador" e que migrar para clientes HTTP diretos reduz custo e lentidão. O levantamento do código e uma sonda ao vivo mostram um cenário diferente:

- **Só o `imovelweb` usa navegador em tempo de execução** (Patchright, por causa do Cloudflare). Os outros 15 módulos já usam `httpx`/`requests`.
- **Já chamam API JSON** (fora do escopo de migração): `cabralporto` e `novaimobiliaria` (Tecimob), `casalinhares` (Imobzi), `minascaixaimoveis` (Imoview), `vivareal` (busca e facetas; o detalhe ainda é HTML).
- **Parseiam HTML** (candidatos): `arthusoimoveis` (busca; detalhe e facetas já são WP REST), `alecorretoramg` (JetEngine devolve HTML dentro de JSON), `marcioimoveis`, `newhouseimobiliaria`, `imobiliariavaleinvest`, `imobiliariaportalmg`, `veraimobiliaria`, o trio ImobiBrasil `epifanioimoveis`/`helenaimoveis`/`niltoncorretordeimoveis`, e o detalhe do `vivareal`.
- **Nenhum módulo tem** bootstrap de sessão/CSRF, retry com backoff ou tratamento de 401/403/419.
- **A API interna nem sempre é JSON estruturado.** Sondei o caso base New House com `httpx` puro (sem navegador): um `GET` em `/imoveis/para-alugar` entrega o `<meta name="csrf-token">` e os cookies `XSRF-TOKEN`/`site_praedium_session`; o `GET /buscar/imoveis/para-alugar[/1-quarto]` responde `200 application/json` com `{code, success, content}`. Mas `content.properties` é um **fragmento HTML** (cards com JSON-LD), não uma lista de objetos. O ganho real para o New House é página menor (15 KB contra a página inteira) e o **total de resultados** (`content.showing`: "Exibindo 1 - 4 de 4 resultados"), hoje errado: `total_count` do adaptador é o tamanho da página (`scripts/mcp/tools.py:41`). O endpoint funcionou até sem o header `X-CSRF-TOKEN`; vamos enviá-lo mesmo assim.

Objetivo: trocar o scraping de HTML pelo endpoint mais leve e estável de cada imobiliária, onde houver ganho real, sem quebrar o contrato do núcleo (`central_mcp`).

## Decisões já tomadas (suas respostas)
1. **Escopo:** descoberta em todos os módulos que parseiam HTML; implementar só onde o resultado for "go". Os que não tiverem endpoint melhor ficam como estão, com a conclusão documentada.
2. **Código compartilhado:** uma cópia pequena do helper dentro de cada módulo (modelo: `cabralporto/.../http_client.py`). Módulos continuam autônomos e testáveis sozinhos.
3. **Falha do endpoint novo:** cair para o parser HTML antigo (mantém os dois caminhos).

## Pré-requisitos
- **Playwright MCP** foi adicionado em `.mcp.json` (0.0.83) mas está "pending approval": rode `claude` neste projeto, aprove e **reinicie a sessão** antes da Fase 1. Para sites que se descobrem só lendo HTML/JS (como acima), `httpx` basta; o Playwright entra onde o XHR só dispara por interação (filtros, autocomplete).
- Capturas e HAR vão para `.playwright-mcp/` (já no `.gitignore`). Nunca gravar cookies, tokens nem HAR bruto em fixture ou doc.
- Sondagem educada: poucas requisições por site, User-Agent identificável como o do New House (`USER_AGENT` em `newhouse_research/infrastructure/http_client.py`).
- Cada módulo é um repositório git próprio. Trabalhar em worktree dentro do repo do módulo (`git worktree add .worktrees/<nome> -b <nome>`), commit lá, merge direto em `main`, push, e só então atualizar o ponteiro do submódulo na raiz. Sem PRs.

## Fase 1: descoberta (um veredito por módulo)
Para cada módulo candidato, registrar: endpoint de busca/detalhe/facetas (método, path vs. query), handshake (token, cookies, headers), tradução dos filtros do nosso `RentalSearchCriteria` para os parâmetros do site, formato da resposta e como a paginação informa o total. Critérios de **go**:
1. Resposta estruturada ou fragmento muito mais leve que a página completa, e total de resultados confiável.
2. Funciona com handshake HTTP puro, também do IP de produção (o Dokploy/g-vps; Cloudflare pode se comportar diferente de uma máquina de dev).
3. Cobre todos os campos que o adaptador devolve hoje (ver contrato abaixo).
4. **Paridade ao vivo:** mesma consulta pelo caminho novo e pelo antigo devolve os mesmos imóveis.

Ordem de prioridade (hipótese a confirmar):

| Grupo | Módulos | Hipótese |
|---|---|---|
| A. JSON provável | `arthusoimoveis` (`/wp-json/wp/v2/properties`, já documentado, até 100 por página), `vivareal` detalhe (reusar o item de `/v2/listings`, que já traz a entidade completa), `marcioimoveis` (`realhomes_map_ajax_search_results` já implementado em `src/.../marcio.py:101` mas sem quartos/banheiros; `realhomes_filter_ajax_search_results` traz `max_pages`/`total_properties` em HTML) | provável go |
| B. XHR com fragmento HTML | `newhouseimobiliaria` (piloto), `alecorretoramg` (`jet_smart_filters`, já é o caminho atual), `imobiliariavaleinvest` (`?pagina=resultado` com `X-Requested-With`, documentado e não usado) | go se o ganho for página menor + total correto |
| C. desconhecido | `epifanioimoveis`/`helenaimoveis`/`niltoncorretordeimoveis` (ImobiBrasil t27), `imobiliariaportalmg` (Orangeimob), `veraimobiliaria` (ASP clássico) | provável no-go; capturar rede com Playwright antes de decidir |
| D. bloqueado | `imovelweb`: `POST /rplis-api/postings` está documentado (payload completo, cidade 104019), mas nada prova que `httpx` passa pelo Cloudflare e o formato da resposta nunca foi capturado | testar `httpx` com o handshake; se barrar, avaliar `curl_cffi` ou manter o navegador. Pode ser no-go |

Entregáveis da fase:
- Seção "Cliente de API interna" no `docs/api-research.md` de cada módulo candidato (existe em todos exceto `casalinhares`; `newhouseimobiliaria` não tem `docs/sot/` nem `docs/adr/`): endpoints, handshake, tabela de mapeamento de filtros, formato e paginação.
- Uma ADR na raiz, `docs/adr/0002-clientes-de-api-interna.md`, com a tabela de veredito go/no-go por módulo e o motivo. Resultado da fase: lista final de módulos a migrar. **Se a lista final divergir muito da hipótese acima, paro e mostro antes de implementar.**
- Fixtures reais sanitizadas (sem token, cookie nem dado pessoal) em `tests/fixtures/` de cada módulo go.

## Fase 2: implementação por módulo "go"
Piloto: **`newhouseimobiliaria`**, porque o endpoint já está verificado.

Peças por módulo (nomes completos, Object Calisthenics no que roda em `scripts/`; ≤2 variáveis de instância, funções ≤15 linhas):
- `SessionBootstrapper`: `GET` na página de origem, extrai `<meta name="csrf-token">` e cookies, mantém em memória (com trava), expõe os headers de sessão. Renova uma vez e repete a chamada em 401/403/419.
- `RetryPolicy`: até 3 tentativas com backoff exponencial e jitter em timeout, 429 e 5xx; erros específicos (`SessionExpiredError`, `ApiContractError`, `NetworkTransportException`), sem engolir exceção.
- Cliente da API (`<modulo>_api_client`): monta URL com a regra do site (ex.: New House: filtros de quartos no path `/1-quarto`, preço e ordenação na query, nome exato `ordernar-por`), headers `Accept`, `X-Requested-With`, `Referer`, `User-Agent`; devolve o corpo bruto.
- Parser da resposta: reaproveita o parser HTML existente para fragmentos (`SearchPageParser` do New House) e passa a ler o JSON-LD dos cards quando for mais estável que seletores CSS; o total vem de `content.showing`/paginação.
- `FallbackRentalGateway` (composição, padrão Strategy): tenta o cliente de API; em `ApiContractError`/`SessionExpiredError`/erro de rede persistente, registra contexto e delega ao gateway HTML antigo. O gateway HTML continua sendo a fonte do detalhe quando a Fase 1 não achou endpoint melhor.

Contrato que o adaptador precisa continuar cumprindo (`central_mcp/src/central_mcp/providers/protocol.py`, `application/service.py`): `search_rentals`, `get_property_detail`, `get_facets`, `get_provider_info`; listagem com `code`/`id`, `title`, `url`, preço, `bedrooms`, localização, `media_url`; detalhe com `description`, `photos`, taxas. O formato **não muda**, então os testes do núcleo continuam valendo.

Caminho que roda em produção: o `scripts/` do módulo para os que o adaptador usa lá (`cabralporto`, `epifanioimoveis`, `imobiliariaportalmg`, `imobiliariavaleinvest`, `marcioimoveis`...) ou o `src/` para `alecorretoramg`, `arthusoimoveis`, `helenaimoveis`. Alterar o caminho que o adaptador realmente executa; as árvores duplicadas não usadas ficam como estão.

## Fase 3: integração
- Testes do módulo: `.venv/bin/pytest` e `ruff check .` em cada submódulo alterado.
- Testes do núcleo: `cd central_mcp && .venv/bin/pytest` (esperado 281 passed) e `ruff check src tests` (8 achados I001 preexistentes).
- Atualizar o ponteiro de cada submódulo na raiz e a seção de provedores de `central_mcp/README.md` (§2) e, se mudar o comportamento, os gotchas do `CLAUDE.md` (ex.: a nota de que o `total_price` do New House na busca é só aluguel).
- Dockerfile: sem mudança, a menos que apareça diretório novo (cada módulo tem `COPY` por lista).
- **Release (tag `v*`) e deploy só com sua confirmação.**

## Arquivos principais
- Por módulo go: `scripts/client/http_transport.py` ou `src/<pacote>/infrastructure/http_client.py` (cliente), parsers em `scripts/client/parsers.py` ou `src/<pacote>/parsers/`, `docs/api-research.md`, `tests/` + `tests/fixtures/`.
- Piloto: `newhouseimobiliaria/src/newhouse_research/infrastructure/{url_builder,http_client}.py`, `collaborators.py`, `parsers/search_parser.py`, `scripts/mcp/tools.py` (corrigir `total_count`).
- Modelo de cliente com tratamento de status e headers: `cabralporto/scripts/client/http_transport.py`.
- Raiz: `docs/adr/0002-clientes-de-api-interna.md` (novo), `central_mcp/README.md`.

## Verificação
- **Unitária:** por módulo, `httpx.MockTransport` com fixtures sanitizadas cobrindo: handshake, renovação em 419/403, retry em 5xx/timeout, fallback para HTML, 0/1/muitos resultados, página vazia, filtros de path vs. query, encoding.
- **Paridade (golden):** para uma consulta fixa, o caminho novo e o antigo devolvem os mesmos `code`s e os mesmos campos do contrato; teste ao vivo atrás de variável de ambiente (padrão `NEWHOUSE_LIVE=1`).
- **Ponta a ponta:** subir `python -m central_mcp.main --transport http`, buscar pelo web e pelo MCP, conferir listagens, fotos, total e paginação; comparar bytes e latência antes/depois por módulo.
- **Produção:** rodar a sonda de handshake a partir do host de produção antes de liberar a tag.
- Nada vai para commit, push, tag ou deploy sem você pedir.
