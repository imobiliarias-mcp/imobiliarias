# Webapp de busca de aluguéis (Central MCP)

Interface web para uso pessoal: uma busca única em todas as imobiliárias, com foto de capa, preço total, descrição e link para o site oficial de cada imóvel. Roda no mesmo serviço do MCP (`central_mcp`), sem login.

## Uso

- Local (dev): `cd central_mcp && .venv/bin/python -m central_mcp.main --transport http --port 8000`, com `CENTRAL_MCP_STATIC_DIR` apontando para `central_mcp/web/dist` (ver build abaixo).
- Desenvolvimento da UI com recarga: `cd central_mcp/web && npm install && npm run dev`. O Vite faz proxy de `/api` para `http://localhost:8000` (ajuste com `CENTRAL_MCP_API_URL`).
- Produção: a imagem do `central_mcp/Dockerfile` já inclui a UI em `/`.

## Build do frontend

```bash
cd central_mcp/web
npm ci
npm run build   # gera dist/ (tsc + vite)
```

Stack: Vite, React 19, TypeScript, Tailwind CSS v4. Os componentes de `src/components/ui/` seguem o estilo do shadcn/ui (copiados para o repositório, sem CLI).

## Endpoints `/api` (JSON, somente leitura)

| Método | Caminho | Descrição |
| :--- | :--- | :--- |
| GET | `/api/providers` | Catálogo das imobiliárias |
| GET | `/api/facets?provider=` | Taxonomia (cidades, bairros, tipos) de uma imobiliária |
| GET | `/api/locations` | Cidades e bairros já conhecidos (`cities`: `key`, `name`; `neighborhoods`: `key`, `name`, `city_key`) |
| GET | `/api/search` | Busca federada. Filtros: `city` (chave ou nome), `neighborhoods` (csv de chaves), `transaction` (só `rent`; `sale` retorna 400), `min_price`, `max_price`, `bedrooms`, `property_type`, `providers` (csv), `sort` (`total_asc` padrão | `total_desc`), `page` (página do central, a partir de 1), `limit` (1–200, padrão 12), `refresh` (`1`/`true` ignora o cache da busca) |
| GET | `/api/listings/{provider}/{code}` | Detalhe de um imóvel com galeria completa e descrição |

Resposta de `/api/search`: `page`, `page_size`, `total` (imóveis em todas as páginas) e `has_more` (há página seguinte) para a paginação; `hidden_without_neighborhood` (imóveis ocultos pelo filtro de bairro por não terem bairro informado), `status` (`ok`, `partial`, `error`), `providers` (resultado por imobiliária ativa, para avisar quais falharam; imobiliárias desativadas como `imovelweb` ficam de fora) e `results` (imóveis com `cover_photo`, `photos`, `description`, `official_url`, preços e `total_price`).

Página além do fim retorna `results: []` com `has_more: false`. `page` nunca é repassado às imobiliárias: a paginação é feita pelo central. Erros: `400` para parâmetros inválidos (inclui `sort` e `refresh` fora do esperado), `404` para imobiliária desconhecida, `502` quando a imobiliária falha no detalhe.

## Localização e filtros

- `parse_location` (`web/locations.py`) extrai cidade e bairro de quatro formatos: campos estruturados, `"Bairro, Cidade"`, `"Bairro, Cidade / MG"` e `"Bairro - Cidade/MG"`. Acentos e caixa são ignorados nas chaves; o nome exibido prefere a forma com acento.
- `LocationCatalog` (`web/location_catalog.py`) grava em `CENTRAL_MCP_DATA_DIR/locations.json` (escrita atômica). Só insere cidades e bairros inéditos. Sem diretório gravável, mantém tudo em memória e registra aviso no log.
- `min_price` e `max_price` são aplicados pelo central sobre o aluguel (`rent_price`), após a resposta das imobiliárias; `min_price` não é repassado (nem todas o suportam). Com algum limite ativo, anúncios sem preço são ocultados.
- Valores de preço aceitam formato brasileiro: `1500`, `1500,00`, `1.500`, `1.500,00` e `R$ 1.500,00`. Texto inválido ou negativo retorna 400.
- Filtros são aplicados antes da paginação. Imóveis de imobiliárias sem localização herdam a cidade pesquisada e não são descartados pelo filtro de cidade.
- Ordenação (`sort`) é global, feita no servidor sobre todo o resultado: menor (ou maior) `total_price` primeiro; imóveis sem preço ficam sempre por último.

## Interface

- Estado na URL (`cidade`, `bairros`, `min`, `max`, `quartos`, `imobs`, `ordem`, `vista`). Recarregar a página refaz a busca com os mesmos filtros. O último estado também fica no `localStorage`.
- A primeira página de cada consulta fica no `localStorage` por 15 minutos, para mostrar algo imediatamente ao recarregar.
- Rolagem infinita carrega a página seguinte ao se aproximar do fim da lista (sentinela com `IntersectionObserver`); o botão "Carregar mais" é o reserva. Páginas seguintes são acrescentadas sem repetir imóveis já exibidos.
- "Tentar de novo" na primeira página pede `refresh=1` ao servidor. Trocar ordem, bairro ou preço mínimo não refaz a busca nas imobiliárias.
- Fotos: só a foto em exibição e as vizinhas são baixadas; as demais slots ficam em branco até o usuário navegar.
- Desktop: barra lateral fixa. Celular: botão "Filtros" abre uma gaveta em tela cheia.
- Grade ou lista. Venda aparece desabilitada até a fase de venda (a API ainda não aceita `transaction=sale`).
- `public/sw.js` guarda fotos no navegador (cache-first, até 200 entradas). Requer HTTPS em produção ou `localhost`.

## Como os dados são montados

1. A busca consulta todas as imobiliárias em paralelo e obtém todos os imóveis encontrados.
2. O resultado bruto da busca fica em cache na memória por `CENTRAL_MCP_SEARCH_CACHE_TTL` segundos, por combinação de imobiliárias, cidade, preço máximo, quartos e tipo. Pedidos simultâneos com a mesma combinação aguardam um único fan-out. Respostas com `status` `error` não são guardadas. Bairro, preço mínimo e ordem são aplicados depois, sobre o cache, sem nova consulta às imobiliárias. Até 6 combinações ficam em memória.
3. Ordena por preço total, separa a página pedida (12 por padrão) e só então busca os detalhes (foto da galeria, descrição) dos imóveis dessa página.
4. Para cada imóvel da página, a foto de capa vem da galeria do detalhe; se não houver, usa a imagem (`media_url`) que a própria busca devolve. A descrição vem do detalhe.
5. Falhas são isoladas por imóvel e por imobiliária. Detalhes bem-sucedidos ficam em cache na memória por `CENTRAL_MCP_DETAIL_CACHE_TTL` segundos.
6. A descrição é texto puro, limitada a 2000 caracteres, e é renderizada como texto (nunca como HTML). Links são aceitos apenas em `http(s)`.
7. `epifanioimoveis` e `niltoncorretordeimoveis` não devolvem imóveis sem cidade. Quando a busca não informa `city`, eles usam Timóteo (`default_city` em `src/central_mcp/providers/capabilities.py`). Cidade informada explicitamente é sempre respeitada.

## Variáveis de ambiente

| Variável | Padrão | Função |
| :--- | :--- | :--- |
| `CENTRAL_MCP_WEB_ENABLED` | `true` | Liga as rotas `/api` |
| `CENTRAL_MCP_STATIC_DIR` | (vazio) | Pasta com o build da UI; se ausente ou inexistente, a UI não é servida |
| `CENTRAL_MCP_ENRICH_CONCURRENCY` | `5` | Detalhes buscados em paralelo por requisição |
| `CENTRAL_MCP_DETAIL_CACHE_TTL` | `900` | Tempo de vida do cache de detalhes, em segundos (`0` desliga) |
| `CENTRAL_MCP_SEARCH_CACHE_TTL` | `600` | Tempo de vida do resultado bruto da busca federada, em segundos. `0` mantém só a deduplicação de pedidos simultâneos |
| `CENTRAL_MCP_DATA_DIR` | (vazio) | Pasta gravável do catálogo de cidades e bairros. Na imagem Docker é `/data` (volume nomeado em `compose.prod.yaml`) |

As variáveis de rate limit (`CENTRAL_MCP_RATE_LIMIT_PER_MINUTE`, `CENTRAL_MCP_RATE_LIMIT_BURST`) também se aplicam às rotas `/api` e aos arquivos estáticos da UI.

## Limitações conhecidas

- **Fotos:** `vivareal`, `veraimobiliaria`, `helenaimoveis` e `arthusoimoveis` expõem galeria no detalhe; várias outras imobiliárias trazem apenas uma imagem na busca, e algumas não trazem nenhuma. Esses imóveis aparecem com "Sem foto" e o link oficial.
- **Imobiliária desativada:** `imovelweb` exige navegador (Cloudflare/Patchright) e está oculto da UI, do seletor e do aviso. Continua disponível pelo MCP. O aviso de falhas da UI mostra apenas falhas reais.
- **Primeira página:** a primeira busca de uma combinação espera todas as imobiliárias, por isso pode levar até cerca de 2 minutos (várias imobiliárias estouram o timeout de 30 s). As páginas seguintes saem do cache, em instantes, enquanto o TTL durar. Depois do TTL, a próxima página dispara um novo fan-out.
- **Detalhes:** cada imóvel da página sem cache gera uma chamada de detalhe. O enriquecimento tem orçamento de 8 s por página: detalhes que não chegam nesse prazo são descartados (o imóvel aparece sem foto e com o link oficial) e continuam no cache para a próxima vez.
- **Dados antigos:** o resultado pode ter até `CENTRAL_MCP_SEARCH_CACHE_TTL` segundos de atraso; "Tentar de novo" força atualização.
- **Dados:** os imóveis vêm como estão nas imobiliárias, incluindo comerciais e títulos vazios.
