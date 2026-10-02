# Verificação da implementação central

Verificações finais em 2026-10-02, no contexto Docker `docker-dev`.
Não foram executadas consultas reais aos sites para validar disponibilidade.

| Verificação | Resultado |
| --- | --- |
| `npm ci`, TypeScript e build servidor/UI/contracts | Passaram |
| Suíte Node central | 98 testes passaram |
| UI com DOM simulado | 33 testes, incluídos na suíte Node |
| Clientes MCP oficiais, duas eras e dois transportes | 36 testes incluídos |
| Bridge Python, 15 processos de teste separados | 121 testes passaram |
| Contratos, workers, projeção e transporte comuns | 24 testes passaram |
| Staging e geração de locks | 8 testes passaram |
| Bundle real em Chromium com `AppBridge` | 1 teste passou |
| Suítes originais offline dos 15 provedores | 594 testes e 20 subtestes |
| Ruff, Markdown, Compose e whitespace | Passaram |

Os testes Python usam ambientes travados por origem e networking desabilitado.
Os módulos `scripts.*` não são coletados juntos no mesmo processo. Testes
live dos subprojetos foram excluídos explicitamente; fontes foram montadas
somente para leitura. Testes Node em containers usam `--init`; o runtime usa
`tini -s` para recolher descendentes encerrados.

## Imagem e protocolo

Imagem local: `mcp-rentals:dev`. Identificador do build final:

```text
sha256:8bcb4e40f93bfe8a8f193e5337c9c435a896e9ac2201b363d50e04072f6aeaf8
```

Runtime Node 24.21.0/Python 3.14.8, usuário não root `mcp-rentals`, UID 1000,
fuso `America/Sao_Paulo` e ambientes Python independentes para as 15 origens.
O manifest identifica as revisões e SHA-256 das fontes. Os 36 arquivos Python
do bridge, o HTML e os contratos do runtime foram comparados com as saídas
finais locais, sem divergências. O último build terminou com código zero.

Smoke do pacote com o cliente oficial verificou quatro ferramentas, catálogo
com 15 instalações disponíveis, recurso HTML e CSP, tanto com `initialize`
legado quanto com `server/discover` da revisão `2026-07-28`. O teste do host
local verificou o bundle exato, handshake, formulários, detalhe, abertura de
links pelo host, teclado, erros e teardown, sem requisições externas.

O modo HTTP local validou Host/Origin, portas publicadas e encerramento.
Healthcheck verifica processo, registro, schemas e imports, não saúde dos sites.
O contexto e a imagem não incluem `.env`, histórico Git, fontes de ambientes
`.venv` ou caches do checkout.

## Limites mantidos

Bloqueios, rate limits, falhas TLS e respostas inválidas continuam sendo erros;
não há retries, downgrade TLS, browser de evasão ou resolução de desafios.
Redirecionamentos HTTP e respostas comprimidas são recusados explicitamente.
Essa política pode tornar uma origem indisponível sem que o servidor esteja
com defeito. Os controles de processos suportam Linux/POSIX com `/proc`.

Não houve push, merge, PR, cadastro de submódulos, alteração dos 15 clientes,
publicação de imagem ou edição automática de configuração de hosts/NPM.
O bootstrap das fontes locais permanece necessário para outros checkouts.
