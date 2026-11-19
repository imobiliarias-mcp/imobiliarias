# 0002 — Clientes de API interna em vez de scraping de HTML

**Status:** em andamento (veredito por módulo abaixo; implementação parcial)

## Contexto

Os módulos de imobiliárias extraem dados de páginas HTML. Só o `imovelweb` usa navegador em tempo de execução (Patchright, por causa do Cloudflare). A hipótese inicial era que a maioria dos sites consome APIs internas JSON e que trocar o HTML por essas APIs reduziria custo e lentidão.

A sondagem mostrou um cenário mais misto: algumas APIs são JSON de verdade, outras entregam HTML dentro de JSON, e algumas têm payload pesado ou não batem com a página.

## Critérios de "go"

1. Resposta estruturada, ou fragmento bem mais leve que a página, com total de resultados confiável.
2. Funciona com HTTP puro (ou TLS impersonado, se for o caso), sem navegador.
3. Cobre os campos do contrato do adaptador (`id`/`code`, `title`, `url`, preço, `bedrooms`, localização, `media_url`).
4. Paridade: a mesma consulta pelo caminho novo e pelo antigo devolve os mesmos imóveis.

## Veredito por módulo

| Módulo | Veredito | Evidência |
|---|---|---|
| `newhouseimobiliaria` | **Go, implementado** (merge local `d412a9d`, sem push) | `/buscar/imoveis/...` JSON; mesmos ids e ordem da página; total `de N resultados`; payload 20 KB contra 245 KB da página. Filtros de quartos e preço com resultado não vazio ainda não verificados. |
| `imovelweb` | **Go condicionado** (aguarda aprovação de dependência e investigação de resposta vazia) | `curl_cffi` (impersonate chrome) recebe 200 sem navegador. `POST /rplis-api/postings` com filtros do doc (`tipoDeOperacion`, `city`, `habitacionesminimo/maximo`, `sort`) devolveu 8 ids, os mesmos 8 da página de Timóteo 1–2 quartos (ordem diferente). Uma requisição de página voltou sem cards: intermitência não explicada. |
| `arthusoimoveis` | **Pausado, decisão pendente** | WP REST `properties` funciona (até 100 por página; `property_status` "alugar" = id 3, 60 imóveis). Filtros de quartos e preço (`fave_property_*`) são ignorados pela API, então precisam ser filtrados no cliente sobre a lista inteira (~400 KB por requisição, contra ~180 KB de uma página HTML de 9 imóveis). Falha no critério 1 (leveza). |
| `vivareal` | **No-go no detalhe**; busca já é JSON | O item de `/v2/listings` traz preço, quartos, áreas, mas não traz descrição nem fotos. A hipótese de reaproveitar o item para o detalhe não se sustenta. |
| `marcioimoveis` | **No-go por enquanto** | `realhomes_map_ajax_search_results` devolve 170 imóveis com id, preço, url e miniatura, mas sem quartos. `realhomes_filter_ajax_search_results` devolve fragmento HTML com `total_properties` e `max_pages`. Nenhum dos dois dá o contrato completo com ganho claro. |
| `imobiliariavaleinvest` | **No-go** | O fragmento `?pagina=resultado` traz 12 cards, incluindo Coronel Fabriciano, enquanto a página completa de Timóteo mostra outra lista. Paridade falha. |
| `alecorretoramg` | Não sondado nesta rodada | Já usa `admin-ajax` JSON com HTML dentro. |
| `epifanioimoveis`, `helenaimoveis`, `niltoncorretordeimoveis` (ImobiBrasil), `imobiliariaportalmg` (Orangeimob), `veraimobiliaria` (ASP clássico) | Não sondados nesta rodada | Provável no-go; exigem captura de rede antes de decidir. |
| `cabralporto`, `novaimobiliaria` (Tecimob), `casalinhares` (Imobzi), `minascaixaimoveis` (Imoview) | Já usam API JSON | Fora do escopo de migração. |

## Decisões

- Cada módulo mantém a própria cópia do cliente (sessão, retry, parsers). Não há pacote compartilhado.
- Se a API falhar (envelope inválido, erro persistente), a busca cai para o HTML antigo, que continua funcionando.
- A renovação de sessão é reativa: o cliente só busca a página HTML e o token CSRF após 403 ou 419, porque o endpoint do New House responde sem handshake. Um handshake prévio adicionaria a página inteira (245 KB) a cada busca, já que cada chamada do central roda em subprocesso novo.
- `total_count` do adaptador passa a ser o total do site quando ele é informado, e não o tamanho da página.

## Consequências

- O New House é o piloto. O endpoint JSON, a renovação de sessão e o fallback estão cobertos por testes (52 passando, 2 live pulados).
- Os demais módulos seguem no HTML até o veredito mudar. Sem pré-requisito de navegador novo, exceto o `curl_cffi` do Imovelweb, que ainda não foi aprovado para o `pyproject.toml`.
- O Imovelweb depende de uma resposta vazia não explicada ser tratada: é preciso medir a taxa de falha antes de remover o Patchright.
