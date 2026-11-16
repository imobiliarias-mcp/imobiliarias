# 0003 — Portal web separado (`portal_web`) e módulo comercial de anunciantes

**Status:** aceito (fases 1 e 2 implementadas; cobrança pendente)

## Contexto

O portal era uma SPA Vite servida pelo próprio núcleo (`central_mcp/web`), sem login. O produto passa a ter marca configurável por implantação (white label) e uma área onde imobiliárias e corretores comprovam vínculo com imóveis já agregados, para depois comprar destaques.

O núcleo não tem banco, autenticação nem imóveis persistidos: cada busca consulta as imobiliárias ao vivo e só há caches em memória. Não existe deduplicação nem status de remoção. A única identidade estável de um imóvel é o par `(provider, code)`, e `code` pode faltar.

## Decisão

- **App separado.** `portal_web/` é um submódulo (Next.js, App Router) com imagem própria. Ele é o portal público e o painel de anunciantes. Não é um módulo de provedor.
- **O núcleo continua sem estado** e sem conhecer anunciantes. Sua imagem deixa de embutir a SPA; `/api/*`, `/mcp` e `/healthz` seguem iguais. `central_mcp/web/` fica no repositório como legado.
- **Primeiro banco do projeto:** PostgreSQL, pertencente ao `portal_web` (Prisma). Guarda contas, perfis, pedidos de vínculo e auditoria. Não guarda imóveis.
- **O navegador chama o núcleo direto.** O limite de requisições do núcleo é por IP do cliente. Em produção o proxy reverso roteia `/api/providers`, `/api/locations`, `/api/facets`, `/api/search`, `/api/listings`, `/mcp`, `/sse`, `/messages` e `/healthz` para o núcleo, e o resto para o portal. Em desenvolvimento o `portal_web` encaminha esses caminhos (`src/proxy.ts`). Chamadas servidor→núcleo existem só nas ações autenticadas de pedido de vínculo.
- **Marca em tempo de execução.** Variáveis `BRAND_*` lidas no servidor a cada requisição; uma imagem serve várias marcas.
- **Better Auth + Prisma**, exceção à regra do projeto de usar Auth.js. Motivo: plugins de administração e organização prontos. Anunciantes entram com Google; e-mail e senha existe só para o administrador local criado por script, com cadastro público desabilitado.
- **Vínculo = pedido aprovado.** Um pedido (`Claim`) aponta para uma fonte inteira (`providerId`) ou para um imóvel (`providerId` + `listingCode`). O status `APPROVED` é o próprio vínculo; não há tabela de vínculo separada. Só um administrador aprova, recusa ou revoga, e cada mudança grava auditoria.
- **Agregadores** (`vivareal`, `imovelweb`) só aceitam pedido por imóvel. Imóvel sem código não é reivindicável.
- **Autorização única.** Toda ação sobre um imóvel passa por `ListingAuthorization`, no servidor.

## Consequências

- A release publica duas imagens com a mesma tag. O compose de produção precisa do `portal-web`, do PostgreSQL e das rotas do proxy **antes** de receber uma imagem do núcleo sem a SPA; do contrário `/` fica sem página.
- "Imóvel removido" significa apenas "não voltou na busca ou no detalhe ao vivo". O painel mostra "indisponível no momento" e não trata falha temporária como remoção. A política para destaques pagos de imóveis ausentes fica para a fase de cobrança.
- Imóveis patrocinados entrarão na ordenação do núcleo (`SearchFlow.run`, `order_by_total_price`) a partir de uma lista de `(provider, code)` fornecida pelo portal. Ainda não implementado, assim como Mercado Pago, créditos e assinaturas.
- LGPD: o portal guarda nome, e-mail, tipo, CRECI e telefone do anunciante, com consentimento no cadastro. Excluir a conta remove perfil e pedidos; a auditoria permanece sem o autor.
