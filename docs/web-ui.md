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
| GET | `/api/search` | Busca federada. Filtros: `city` (chave ou nome), `neighborhoods` (csv de chaves), `transaction` (só `rent`; `sale` retorna 400), `min_price`, `max_price`, `bedrooms`, `property_type`, `providers` (csv), `page`, `limit` (1–200, padrão 60) |
| GET | `/api/listings/{provider}/{code}` | Detalhe de um imóvel com galeria completa e descrição |

Resposta de `/api/search`: `hidden_without_neighborhood` (imóveis ocultos pelo filtro de bairro por não terem bairro informado), `status` (`ok`, `partial`, `error`), `providers` (resultado por imobiliária ativa, para avisar quais falharam; imobiliárias desativadas como `imovelweb` ficam de fora) e `results` (imóveis com `cover_photo`, `photos`, `description`, `official_url`, preços e `total_price`).

Erros: `400` para parâmetros inválidos, `404` para imobiliária desconhecida, `502` quando a imobiliária falha no detalhe.

## Localização e filtros

- `parse_location` (`web/locations.py`) extrai cidade e bairro de quatro formatos: campos estruturados, `"Bairro, Cidade"`, `"Bairro, Cidade / MG"` e `"Bairro - Cidade/MG"`. Acentos e caixa são ignorados nas chaves; o nome exibido prefere a forma com acento.
- `LocationCatalog` (`web/location_catalog.py`) grava em `CENTRAL_MCP_DATA_DIR/locations.json` (escrita atômica). Só insere cidades e bairros inéditos. Sem diretório gravável, mantém tudo em memória e registra aviso no log.
- `min_price` é aplicado pelo central sobre o aluguel (`rent_price`), não repassado às imobiliárias; com mínimo ativo, anúncios sem preço são ocultados.
- Filtros são aplicados antes do corte de `limit`. Imóveis de imobiliárias sem localização herdam a cidade pesquisada e não são descartados pelo filtro de cidade.

## Interface

- Estado na URL (`cidade`, `bairros`, `min`, `max`, `quartos`, `imobs`, `ordem`, `vista`). Recarregar a página refaz a busca com os mesmos filtros. O último estado também fica no `localStorage`.
- Últimos resultados por consulta ficam no `localStorage` por 15 minutos, para mostrar algo imediatamente ao recarregar.
- Desktop: barra lateral fixa. Celular: botão "Filtros" abre uma gaveta em tela cheia.
- Grade ou lista. Venda aparece desabilitada até a fase de venda (a API ainda não aceita `transaction=sale`).
- `public/sw.js` guarda fotos no navegador (cache-first, até 200 entradas). Requer HTTPS em produção ou `localhost`.

## Como os dados são montados

1. A busca consulta todas as imobiliárias em paralelo e obtém todos os imóveis encontrados.
2. Os resultados são intercalados por imobiliária (round-robin) e só então cortados pelo `limit`. Assim, cada imobiliária aparece já na primeira página.
3. Para cada imóvel da página, a foto de capa vem da galeria do detalhe; se não houver, usa a imagem (`media_url`) que a própria busca devolve. A descrição vem do detalhe.
4. Falhas são isoladas por imóvel e por imobiliária. Detalhes bem-sucedidos ficam em cache na memória por `CENTRAL_MCP_DETAIL_CACHE_TTL` segundos.
5. A descrição é texto puro, limitada a 2000 caracteres, e é renderizada como texto (nunca como HTML). Links são aceitos apenas em `http(s)`.
6. `epifanioimoveis` e `niltoncorretordeimoveis` não devolvem imóveis sem cidade. Quando a busca não informa `city`, eles usam Timóteo (`default_city` em `src/central_mcp/providers/capabilities.py`). Cidade informada explicitamente é sempre respeitada.

## Variáveis de ambiente

| Variável | Padrão | Função |
| :--- | :--- | :--- |
| `CENTRAL_MCP_WEB_ENABLED` | `true` | Liga as rotas `/api` |
| `CENTRAL_MCP_STATIC_DIR` | (vazio) | Pasta com o build da UI; se ausente ou inexistente, a UI não é servida |
| `CENTRAL_MCP_ENRICH_CONCURRENCY` | `5` | Detalhes buscados em paralelo por requisição |
| `CENTRAL_MCP_DETAIL_CACHE_TTL` | `900` | Tempo de vida do cache de detalhes, em segundos (`0` desliga) |
| `CENTRAL_MCP_DATA_DIR` | (vazio) | Pasta gravável do catálogo de cidades e bairros. Na imagem Docker é `/data` (volume nomeado em `compose.prod.yaml`) |

As variáveis de rate limit (`CENTRAL_MCP_RATE_LIMIT_PER_MINUTE`, `CENTRAL_MCP_RATE_LIMIT_BURST`) também se aplicam às rotas `/api` e aos arquivos estáticos da UI.

## Limitações conhecidas

- **Fotos:** `vivareal`, `veraimobiliaria`, `helenaimoveis` e `arthusoimoveis` expõem galeria no detalhe; várias outras imobiliárias trazem apenas uma imagem na busca, e algumas não trazem nenhuma. Esses imóveis aparecem com "Sem foto" e o link oficial.
- **Imobiliária desativada:** `imovelweb` exige navegador (Cloudflare/Patchright) e está oculto da UI, do seletor e do aviso. Continua disponível pelo MCP. O aviso de falhas da UI mostra apenas falhas reais.
- **Primeira busca:** cada imóvel da página sem cache gera uma chamada de detalhe. Com a página padrão de 60 imóveis, a busca leva em torno de 10–15 s.
- **Dados:** os imóveis vêm como estão nas imobiliárias, incluindo comerciais e títulos vazios.
