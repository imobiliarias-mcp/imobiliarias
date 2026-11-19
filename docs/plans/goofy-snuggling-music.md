# Plano — Submódulo `portal_web`: frontend white label + módulo comercial de anunciantes

## Contexto

O portal atual é uma SPA Vite/React simples (`central_mcp/web/`), servida pelo próprio núcleo. Queremos um frontend comercial, com marca configurável por implantação, onde imobiliárias e corretores se cadastram, comprovam vínculo com imóveis já agregados e, numa rodada futura, compram destaques. O frontend atual deve ser desativado.

Esta rodada implementa as **fases 1 e 2** e para. A fase 3 (Mercado Pago, créditos, assinaturas, patrocinados) fica só esboçada.

## O que a auditoria mostrou (muda premissas do prompt)

| Premissa do prompt | Realidade no repositório |
|---|---|
| Banco, ORM, imóveis persistidos | **Não existe banco.** O núcleo consulta as imobiliárias ao vivo a cada busca (subprocesso por provedor) e guarda só caches TTL em memória e `locations.json`. |
| Deduplicação, merges, status de remoção | Não existem. "Removido" = deixou de aparecer na busca/detalhe ao vivo. |
| ID estável de imóvel | Par `(provider, code)`. `code` pode ser nulo (`web/listing.py`); sem código, o imóvel não pode ser reivindicado. |
| Identidade da fonte | `provider_id` de `PROVIDER_MAP` / `/api/providers` (16 fontes; `imovelweb` indisponível). |
| Autenticação existente | Nenhuma. Serviço público com rate limit por IP (`http_app.py`). |
| Venda | Só aluguel (`transaction=sale` retorna 400). |
| SEO/URLs de imóvel | Não há página por imóvel; o detalhe é um diálogo na SPA. Nada a preservar além dos parâmetros de URL da busca. |

Consequência: o módulo comercial precisa do **primeiro banco do projeto** (PostgreSQL), e ele pertence ao novo app, não ao núcleo. O núcleo continua sem estado.

## Decisões

1. **Novo submódulo `portal_web/`**, repositório público `imobiliarias-mcp/portal-web` (o workflow de release não clona submódulos privados). App Next.js (App Router, TypeScript strict) que é ao mesmo tempo o portal público e o painel de anunciantes. Aprovar este plano autoriza criar esse repositório.
2. **Núcleo intocado na lógica.** Reuso da API existente (`/api/providers`, `/api/locations`, `/api/facets`, `/api/search`, `/api/listings/{provider}/{code}`). Única mudança no núcleo: parar de embutir a SPA na imagem.
3. **Quem chama o núcleo:** o navegador, direto. O rate limiter agrupa por IP do cliente; se o Next buscasse no servidor, todos os visitantes dividiriam um balde de 30 req/min.
   - Produção: o Traefik roteia os cinco prefixos acima, mais `/mcp`, `/sse` e `/healthz`, para o núcleo (prioridade maior); o resto vai para o Next.
   - Dev: `rewrites` do Next para `CENTRAL_MCP_API_URL` (padrão `http://localhost:8000`).
   - Rotas próprias do Next ficam em `/api/auth/*` e `/api/advertiser/*`, sem colisão.
   - Chamadas servidor→núcleo só nas ações autenticadas de reivindicação (validar que `(provider, code)` existe), de baixo volume.
4. **White label = marca por implantação.** `BRAND_NAME`, `BRAND_LOGO_URL`, `BRAND_PRIMARY_COLOR`, `BRAND_ACCENT_COLOR`, `BRAND_REGION_LABEL`, `BRAND_SUPPORT_EMAIL` lidos **no servidor em tempo de execução** (não `NEXT_PUBLIC_*`, que é fixado no build). O layout raiz injeta variáveis CSS e um contexto de marca; `app/manifest.ts` gera o manifesto PWA dinamicamente. Uma imagem serve várias marcas.
5. **Autenticação: Better Auth + Prisma** (exceção registrada à regra global Auth.js). Minha leitura da sua resposta:
   - Login **Google** para anunciantes (e-mail já verificado pelo Google; sem SMTP nesta rodada).
   - **Admin local**: conta e-mail/senha criada por script idempotente a partir de `ADMIN_EMAIL`/`ADMIN_PASSWORD`; cadastro público por e-mail/senha desabilitado.
   - Plugins **admin** (papéis, banimento) e **organization** (imobiliária com equipe).
   - Nomes exatos de opções e do adaptador Prisma serão conferidos na documentação atual do Better Auth antes de codar, não de memória.
6. **Versões fixadas** (exatas, com lockfile): next 16.4.6, react 19.3.1, better-auth 1.7.25, prisma/@prisma/client 7.10.1 (a 8 ainda é RC), tailwindcss 4.3.5, zod 4.6.7, react-hook-form 7.92.0, @tanstack/react-query 5.107.1, sonner 2.0.8, vitest 5.1.0, @playwright/test 1.65.1; shadcn/ui + Radix + lucide-react.
7. **Desativar, não apagar.** `central_mcp/web/` fica no repositório, marcado como legado na documentação.

## Estrutura do submódulo

```text
portal_web/
  prisma/schema.prisma
  src/
    app/
      (public)/            # busca, detalhe do imóvel
      anunciantes/         # landing, entrar
      painel/              # meus-imoveis, reivindicacoes, configuracoes
      admin/               # anunciantes, reivindicacoes
      api/auth/[...all]/   # Better Auth
      api/advertiser/      # comandos do módulo comercial
      manifest.ts
    brand/                 # leitura e validação da marca (zod)
    catalog/               # cliente tipado da API do núcleo
    modules/advertiser-commerce/
      domain/{advertiser,claims}/
      application/{commands,queries}/
      infrastructure/persistence/
      presentation/{components,schemas}/
    components/ui/         # shadcn
  tests/{unit,e2e}/
  Dockerfile  compose.dev.yaml  .env.example  README.md
```

Convenções do repositório valem aqui: funções ≤ 15 linhas, sem `else`, value objects (`ProviderId`, `ListingCode`, `ListingRef`), erros específicos, validação nas bordas.

## Fase 1 — Portal público novo e desativação do antigo

**Paridade funcional** (lista de `docs/web-ui.md`), com desenho visual novo:

- Busca com filtros de cidade, bairros, preço mín./máx., quartos e imobiliárias; ordem por preço total; grade ou lista.
- Estado na URL com os mesmos nomes (`cidade`, `bairros`, `min`, `max`, `quartos`, `imobs`, `ordem`, `vista`).
- Rolagem infinita com botão reserva, sem repetir imóveis; aviso de imobiliárias que falharam; "tentar de novo" com `refresh=1`.
- Barra lateral no desktop, gaveta no celular; carrossel que só baixa a foto visível e as vizinhas.
- PWA: manifesto dinâmico, ícones e service worker de fotos.
- Novo: página própria por imóvel em `/imovel/[provider]/[code]` (o detalhe deixa de ser só um diálogo), com link para o site oficial.

**Reuso:** portar a lógica de `central_mcp/web/src/lib/` (`api.ts`, `url-state.ts`, `use-paged-search.ts`, `sort.ts`, `format.ts`, `storage.ts`) e os tipos de `types.ts`; `public/sw.js` e ícones.

**Mudanças fora do submódulo:**

- `central_mcp/Dockerfile`: remover o estágio `web-builder`, a cópia de `web/dist` e `ENV CENTRAL_MCP_STATIC_DIR`. `build_static_mount` já devolve `None` sem diretório, então `/api/*` segue ativo. **Não** usar `CENTRAL_MCP_WEB_ENABLED=false`: isso desligaria também a API.
- `central_mcp/compose.dev.yaml`: acrescentar `postgres` (17) e `portal-web`, com `TZ=America/Sao_Paulo` e health checks.
- `central_mcp/compose.prod.yaml`: serviços `portal-web` e `postgres` (volume nomeado, sem porta publicada), roteadores Traefik conforme a decisão 3.
- `.github/workflows/release.yml`: construir, auditar e publicar também `ghcr.io/imobiliarias-mcp/imobiliarias-portal-web`, com a mesma tag.
- `.gitmodules`: novo submódulo.

**Ordem de corte:** a mesma release sobe o `portal-web` roteado e remove a SPA do núcleo, para `/` nunca ficar vazio.

## Fase 2 — Contas, reivindicações e administração

**Modelo (Prisma, além das tabelas do Better Auth):**

- `AdvertiserProfile`: tipo (`REAL_ESTATE_AGENCY` | `INDEPENDENT_BROKER`), nome de exibição, CRECI (informativo, nunca prova), telefone; ligado ao usuário ou à organização.
- `Claim`: alvo de fonte (`providerId`) ou de imóvel (`providerId` + `listingCode`), evidência textual/URL, status `PENDING` | `APPROVED` | `REJECTED` | `REVOKED`, motivo.
- `SourceLink` e `ListingLink`: criados só pela aprovação; revogáveis.
- `ClaimAuditLog`: quem, quando, transição, motivo (somente inserção).

**Regras:**

- Cadastro não concede nada. Vínculo só nasce de aprovação manual do admin.
- Fontes agregadoras (`vivareal`, `imovelweb`; lista em configuração) aceitam apenas reivindicação por imóvel.
- Imóvel sem `code` não é reivindicável.
- Toda operação comercial passa por um único verificador de autorização (`ListingRef` → vínculo ativo do anunciante), no servidor; o ID vindo do cliente nunca basta.
- Revogação bloqueia imediatamente novas operações (a política para promoções ativas entra com a fase 3).

**Telas:**

- `/anunciantes` (apresentação), `/anunciantes/entrar` (Google; e-mail/senha só para o admin).
- `/painel`: identidade e status de verificação; `/painel/reivindicacoes` (buscar fonte ou imóvel indexado, enviar, acompanhar); `/painel/meus-imoveis` (somente leitura, consulta ao vivo: `/api/search?providers=<id>` para vínculo de fonte e detalhe por imóvel; ausente = "indisponível no momento", sem tratar falha temporária como remoção; botão "reportar informação incorreta" grava um pedido para revisão); `/painel/configuracoes`.
- `/admin/anunciantes`, `/admin/reivindicacoes` (aprovar, rejeitar com motivo, revogar; TanStack Table).

**LGPD:** guardar só nome, e-mail, tipo, CRECI e telefone; consentimento no cadastro; exclusão de conta remove o perfil e anonimiza o log de auditoria; nenhum dado pessoal em log.

## Fase 3 — Só esboço (não implementar agora)

Pedidos, Checkout Pro e assinaturas do Mercado Pago, webhook verificado no servidor em `/api/advertiser/webhooks/mercadopago`, carteira de créditos com razão imutável, direitos de promoção. Patrocinados entram na ordenação em `SearchFlow.run` / `order_by_total_price` (`central_mcp/src/central_mcp/web/`), por meio de uma lista de `(provider, code)` ativos fornecida pelo portal, com rótulo explícito.

## Documentação

- `docs/adr/0003-portal-web-e-modulo-comercial.md`: app Next separado, primeiro banco, roteamento navegador→núcleo, exceção Better Auth, identidade `(provider, code)`.
- Atualizar `docs/web-ui.md` (SPA legada), `central_mcp/README.md` (§1 e §5), `README.md` e `CLAUDE.md` da raiz (comandos do `portal_web`, que ele não é um provedor).

## Execução

Worktree `.worktrees/portal-web` no repositório principal; commits por mudança lógica; TDD nas regras de autorização e de reivindicação; merge `--no-ff` em `main`, sem PR. **Não crio tag de release nem altero produção sem sua confirmação.**

## Você precisa fornecer

- **Google OAuth:** client ID e secret, com redirect `https://<domínio>/api/auth/callback/google` e `http://localhost:3000/api/auth/callback/google`. Sem eles eu verifico tudo pelo admin local; o login Google fica implementado, mas não testado de ponta a ponta.
- **`.env` do `portal_web`:** `BETTER_AUTH_SECRET`, `DATABASE_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, variáveis `BRAND_*` (deixo `.env.example` e gero valores locais de dev).
- **Produção (quando for implantar):** como o Dokploy obtém o compose (não verifiquei se é do Git ou colado), segredo do Postgres no Dokploy e confirmação do domínio.

## Verificação

1. Núcleo: `cd central_mcp && .venv/bin/pytest` continua com 281 aprovados; `ruff check src tests` sem achados novos.
2. Imagem do núcleo: `/healthz` e `/api/search?city=Timóteo` respondem; `/` não serve mais a SPA.
3. `portal_web`: `npm run lint`, `npm run build`, `npx prisma migrate deploy` em banco limpo, `npx vitest run`.
4. Vitest: cadastro não gera vínculo; anunciante não opera imóvel alheio trocando o ID; aprovação cria vínculo; rejeição e revogação registram auditoria; fonte agregadora recusa reivindicação de fonte; imóvel sem código é recusado.
5. Playwright contra a stack `compose.dev.yaml`: paridade da busca (filtros, URL, paginação, grade/lista, gaveta no celular), página do imóvel, troca de marca por variável de ambiente sem rebuild, login do admin local, fluxo enviar → aprovar → "meus imóveis".
6. `docker compose -f central_mcp/compose.dev.yaml up -d` com todos os serviços `healthy`.
