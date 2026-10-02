# Reverse-Engineered API Specification: Márcio Imóveis

## 1. Overview & Architecture

Márcio Imóveis (`https://marcioimoveis.net.br`) is a prominent real estate portal serving Timóteo, Coronel Fabriciano, Ipatinga, and the wider Vale do Aço region in Minas Gerais, Brazil.

The portal is built on top of **WordPress 6.x** paired with the **RealHomes Theme (Modern design variation)** and the **Easy Real Estate (ERE)** plugin by InspiryThemes. Search pages combine server-side rendered HTML (`text/html; charset=UTF-8`) with client-side dynamic AJAX filtering backed by `admin-ajax.php`.

### 1.1 Authentication & Security Requirements
- **Authentication**: **None required**. All rental searches, filter queries, pagination offsets, property detail pages, photo galleries, and taxonomy facets are completely publicly accessible without login, session cookies, API tokens, or CSRF tokens.
- **Critical Server Header Rule (ModSecurity / Content Negotiation)**:
  > [!IMPORTANT]
  > The Apache web server strictly requires the `Accept-Language` request header (e.g., `pt-BR,pt;q=0.9,en;q=0.8`). If `Accept-Language` is omitted, the server immediately rejects the request with **HTTP 406 Not Acceptable**. Standard desktop `User-Agent` is also required.
- **HTTP Methods**:
  - Listing Search, Pagination, Filtering, Details, and Facets: `GET`
  - AJAX Map Search & Filter: `POST` or `GET` to `/wp-admin/admin-ajax.php`

---

## 2. Search Endpoints & Routing Architecture

The search engine processes query criteria via two complementary mechanisms:
1. **Canonical SEO URL Routing (GET)**: Clean URLs with slash-delimited pagination and URL-encoded query parameters.
2. **WordPress AJAX Endpoints (POST/GET)**: Low-latency JSON and partial-HTML responses via `admin-ajax.php`.

### 2.1 Canonical SEO Search Routing Pattern

```http
GET /properties-search/?{query_parameters} HTTP/1.1
Host: marcioimoveis.net.br
Accept-Language: pt-BR,pt;q=0.9,en;q=0.8
User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36
```

#### Pagination Routing Rule
- Page 1: `/properties-search/?{query_parameters}`
- Page N (N > 1): `/properties-search/page/{N}/?{query_parameters}`
- Query parameter redirect: Passing `?paged=2` triggers an HTTP 301/302 canonical redirect to `/properties-search/page/2/?...`.

### 2.2 WordPress AJAX Endpoints

```http
POST /wp-admin/admin-ajax.php HTTP/1.1
Host: marcioimoveis.net.br
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With: XMLHttpRequest
Accept-Language: pt-BR,pt;q=0.9,en;q=0.8
User-Agent: Mozilla/5.0 ...

action=realhomes_map_ajax_search_results&statuses=alugar&bedrooms=2
```

| Action Name | Response Type | Content Description |
| :--- | :--- | :--- |
| `realhomes_map_ajax_search_results` | `application/json` | Returns `data.propertiesData` array of all matching listings with `id`, `title`, `price`, `url`, `lat`, `lng`, `thumb`, `icon`. |
| `realhomes_filter_ajax_search_results` | `application/json` | Returns `{success: true, data: {search_results: "<article ...>", max_pages: N, total_properties: M}}`. |
| `rh_sfoi_data_fetch` | `application/json` | Instant keyword search autocomplete. |

---

## 3. Request Parameters & Filter Conventions

All search filters can be combined in the query string:

| Parameter | Type | Example Values | Description & Logic |
| :--- | :--- | :--- | :--- |
| `status` | `string` | `alugar`, `a-venda`, `any` | Transaction purpose (`alugar` for rentals, `a-venda` for sales). |
| `location[]` | `string[]` | `location[]=timoteo&location[]=ipatinga` | Array of location slugs. Can be specified multiple times for multi-neighborhood/city filtering. |
| `type[]` | `string[]` | `type[]=apartamento&type[]=casa` | Array of property type slugs. Supports multi-selection. |
| `bedrooms` | `integer` | `1`, `2`, `3`, `4`, `any` | Bedrooms constraint. Matches properties with specified bedroom count. |
| `bathrooms` | `integer` | `1`, `2`, `3`, `any` | Bathrooms constraint. |
| `min-price` | `integer` | `500`, `1000`, `2000` | Minimum rental price in BRL. |
| `max-price` | `integer` | `1500`, `3000`, `5000` | Maximum rental price in BRL. |
| `min-area` | `integer` | `50`, `100` | Minimum usable area in m². |
| `max-area` | `integer` | `200`, `500` | Maximum usable area in m². |
| `sort-properties` | `string` | `default`, `price-asc`, `price-desc`, `date-asc`, `date-desc` | Result sorting criteria. |
| `property-id` | `string` | `RH-17772`, `17772` | Direct search by property code or ID. |
| `keyword` | `string` | `varanda`, `garagem` | Free-text keyword search across titles and descriptions. |

---

## 4. Pagination Mechanics & Boundary Behavior

- **Page Size**: **6 listings per page** across all search categories.
- **Pagination Structure**:
  - Container selector: `.rh_pagination`
  - Active page selector: `a.rh_pagination__btn.current`
  - Page links: `a.rh_pagination__btn[data-page-number]`
  - Stats container selector: `.rh_pagination__stats`
- **Stats Attributes**:
  ```html
  <div class="rh_pagination__stats" 
       data-page="1" 
       data-max="5" 
       data-total-properties="26" 
       data-page-id="135">
      1 to 6 out of 26 properties
  </div>
  ```
- **Boundary & Out-of-Bounds Behavior**:
  - Requesting an out-of-bounds page (e.g. `/properties-search/page/99/?status=alugar`) returns **HTTP 200 OK**.
  - The DOM contains 0 listing cards and renders the alert:
    ```html
    <div class="rh_page__listing">
        <p class="rh_not_found">Nenhum Resultado Encontrado!</p>
    </div>
    ```
  - The client detects pagination termination when `current_page >= max_pages` or when `articles` length is 0.

---

## 5. Search Results Card Parsing

Search result cards are rendered inside `.rh_page__listing` as `<article class="rh_prop_card">`:

### 5.1 Card Structure & DOM Selectors
```html
<article class="rh_prop_card post-17772 property type-property ...">
    <div class="rh_prop_card__wrap">
        <figure class="rh_prop_card__thumbnail">
            <a href="https://marcioimoveis.net.br/imovel/apartamento-santa-terezinha/">
                <img src="https://marcioimoveis.net.br/wp-content/uploads/2026/09/WhatsApp-Image-2026-09-24-at-10.02.02-1-488x326.jpeg" />
            </a>
        </figure>
        <div class="rh_prop_card__details">
            <h3 class="rh_prop_card__title">
                <a href="https://marcioimoveis.net.br/imovel/apartamento-santa-terezinha/">APARTAMENTO- SANTA TEREZINHA</a>
            </h3>
            <div class="rh_prop_card__priceLabel">
                <span class="rh_prop_card__price">R$1,150</span>
            </div>
            <div class="rh_prop_card__meta_wrap">
                <div class="rh_prop_card__meta">
                    <span class="rh_meta_titles">Quartos</span>
                    <span class="figure">3</span>
                </div>
                <div class="rh_prop_card__meta">
                    <span class="rh_meta_titles">Banheiros</span>
                    <span class="figure">2</span>
                </div>
            </div>
        </div>
    </div>
</article>
```

### 5.2 Extraction Selectors Table
| Field | Primary CSS Selector | Fallback / Processing |
| :--- | :--- | :--- |
| `title` | `h3 a`, `.rh_prop_card__title a` | `element.text.strip()` |
| `url` | `h3 a[href]`, `.rh_prop_card__title a[href]` | Normalized URL string |
| `price` | `.rh_prop_card__price`, `.price` | `PriceTextExtractor` (handles `R$1,150` format) |
| `bedrooms` | `.rh_prop_card__meta` matching `Quartos?\s*(\d+)` | Integer value |
| `bathrooms` | `.rh_prop_card__meta` matching `Banheiros?\s*(\d+)` | Integer value |
| `thumbnail` | `figure img[src]`, `.post_thumbnail[style]` | URL from `src` or CSS `background-image` |
| `property_code` | `post-{id}` class or slug from `url` | `PropertyCode` value object |

---

## 6. Property Detail Retrieval

- **Canonical URL Pattern**: `https://marcioimoveis.net.br/imovel/{slug}/` (e.g. `/imovel/apartamento-santa-terezinha/`).
- **Resolution Strategy**: Given a property reference code like `RH-17772` or numeric `17772`, the client queries `/properties-search/?property-id=17772`, extracts the canonical listing URL from the result card, and fetches the detail page.

### 6.1 Detail Page Elements
| Field | Extraction Method | Sample Value |
| :--- | :--- | :--- |
| `title` | `h1.rh_page__title`, `.entry-title` | `"APARTAMENTO- SANTA TEREZINHA"` |
| `property_code` | Regex `Cod\.\s*do\s*Imóvel\s*:\s*([A-Za-z0-9_-]+)` | `"RH-17772"` |
| `price` | `.price` | `"R$ 1.150,00"` |
| `status` | Breadcrumbs / header | `"Para Alugar"` |
| `property_type` | Breadcrumbs / header | `"Apartamento"` |
| `bedrooms` | Regex `Quartos?\s*[:\n\r]*\s*(\d+)` | `3` |
| `bathrooms` | Regex `Banheiros?\s*[:\n\r]*\s*(\d+)` | `2` |
| `garages` | Regex `Garag(?:em|ens)?\s*[:\n\r]*\s*(\d+)` | `1` |
| `photos` | `a[data-fancybox]`, `img[src*='/wp-content/uploads/']` | 26 high-resolution image URLs |
| `map_data` | Embedded script `propertyMapData = {...}` | `lat: 25.7308309`, `lng: -80.444149` |
| `description` | `.rh_content`, `.rh_property__content` | Full textual description |

---

## 7. Facets & Taxonomy Catalog

The portal embeds a complete JSON taxonomy tree inside the search page via the global variable:
```javascript
var realhomesLocationsData = {
    any_text: "Todos",
    any_value: "any",
    select_names: ["location", "child-location", "grandchild-location", "great-grandchild-location"],
    all_locations: [ ... ]
};
```

### 7.1 Location Hierarchy Summary
- **Total Locations**: **179 distinct geographic entities** (cities and neighborhoods).
- **Top-Level Municipalities / Sectors (25 nodes)**:
  - Antonio Dias (ID: 220)
  - Belo Oriente (ID: 256)
  - Bromélias (ID: 237)
  - Caratinga (ID: 229, includes Bairro das Graças)
  - Cocais - Fabriciano (ID: 250)
  - Coronel Fabriciano (ID: 73, includes 30 neighborhoods)
  - Ipatinga (ID: 62, includes 35 neighborhoods)
  - Timóteo (ID: 104, includes 48 neighborhoods)
  - Marliéria, Jaguaraçu, Periquito, etc.
- **Property Types (19 categories)**:
  `apartamento`, `apartamentocobertura`, `area`, `casa`, `casa-alvenaria`, `casa-duplex`, `casa-geminada`, `casa-barracao`, `chacara`, `fazenda`, `galpao`, `galpao-industrial`, `loja`, `lote`, `predio`, `quitinete`, `sala-comercial`, `salao-de-festa`, `sitio`.

---

## 8. Target URL Reproduction & Verification

### 8.1 User Target URL Specification
```
https://marcioimoveis.net.br/properties-search/?location%5B%5D=antonio-dias&location%5B%5D=belo-oriente&location%5B%5D=bromelias-2&...&status=alugar&bedrooms=2
```

### 8.2 Reproduction Mechanics
1. **Query Construction**: The query selects all 179 locations (`location[]={slug}`), sets transaction purpose `status=alugar`, and constrains bedrooms `bedrooms=2`.
2. **Execution & Live Response**:
   - Total matching properties: **6**
   - Active page: **Page 1 of 1**
   - Identified listings:
     1. `APARTAMENTO- SANTA TEREZINHA` (`RH-17772`) - R$ 1.150,00 - 3 Bedrooms, 2 Bathrooms
     2. `CASA GEMINADA- ANA MOURA` (`casa-geminada-ana-moura`) - R$ 1.200,00 - 2 Bedrooms, 1 Bathroom
     3. `CASA- SANTA MARIA` (`casa-santa-maria`) - R$ 2.000,00 - 3 Bedrooms, 3 Bathrooms
     4. `CASA GEMINADA- CIRILO` (`casa-geminada-cirilo`) - R$ 1.400,00 - 2 Bedrooms, 1 Bathroom
     5. `APARTAMENTO-GUARAPARI` (`apartamento-guarapari`) - R$ 300,00 - 3 Bedrooms, 2 Bathrooms
     6. `BARRACÃO-CACHOEIRA DO VALE` (`barracao-cachoeira-do-vale`) - R$ 450,00 - 2 Bedrooms, 1 Bathroom
