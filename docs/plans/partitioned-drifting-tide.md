# Link público do imóvel em todos os resultados de pesquisa

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
