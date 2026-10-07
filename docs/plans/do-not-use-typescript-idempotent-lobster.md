# Plan: Normalize Monthly IPTU and Incorporate into total_price

## Context

When searching for rental properties, total monthly housing expenditure consists of the nominal rent, condominium fees (`condo_fee`), and property tax (`iptu`).
Previously, condominium fees were integrated across `central_mcp` and subprojects, while IPTU was deferred because portals expose it in varied cadences (annual, monthly installments, or embedded in descriptions/taxes).

Per user request:
- Subprojects must extract and normalize monthly IPTU into a standard `iptu` key (`float | None`).
- If a source exposes annual IPTU, normalize it to monthly by dividing by 12 (rounded to 2 decimal places).
- Central MCP's `_calculate_total_price` will sum `rent_price + condo_fee + iptu` (with missing fees treated as `0.0`, and returning `None` if `rent_price` is missing).
- Central MCP listing projections, detail enrichment, and domain entities must include the standard `iptu` key.

## Architectural Changes & Design

### 1. central_mcp

#### `central_mcp/src/central_mcp/application/service.py`
- **Helper `_extract_iptu(item: dict[str, Any]) -> float | None`**:
  Inspects candidate keys: `("iptu", "monthly_iptu", "valoriptu", "total_taxes_price", "tax")`.
  Uses `_parse_numeric_price` on candidates and returns the first non-`None` value.
- **Update `_calculate_total_price(rent: float | None, condo: float | None, iptu: float | None = None) -> float | None`**:
  ```python
  def _calculate_total_price(
      rent: float | None,
      condo: float | None,
      iptu: float | None = None,
  ) -> float | None:
      if rent is None:
          return None
      additional_fee = (condo or 0.0) + (iptu or 0.0)
      return round(rent + additional_fee, 2)
  ```
- **Update `project_listing(...)`**:
  Extracts `iptu = _extract_iptu(item)`.
  Computes `total_price = _calculate_total_price(rent_price, condo_fee, iptu)`.
  Adds `"iptu": iptu` to the projected dictionary.
- **Update `_enrich_detail_pricing(raw: Any) -> Any`**:
  Extracts `iptu = _extract_iptu(raw)`.
  Computes `total_price = _calculate_total_price(rent_price, condo_fee, iptu)`.
  Sets `raw["iptu"] = iptu` and `raw["total_price"] = total_price`.

#### `central_mcp/src/central_mcp/domain/entities.py`
- **`ListingFeatures`**:
  Add `iptu: float | None = None`.
- **`ListingSummary.to_dict()`**:
  Include `iptu = self.features.iptu`.
  Update fallback total: `self.features.total_price or round(rent_amount + (condo or 0.0) + (iptu or 0.0), 2)`.
  Include `"iptu": iptu` in returned dictionary.

### 2. Subprojects Normalization

#### `vivareal` (`vivareal/scripts/mcp/tools.py`)
- Source data provides `yearly_iptu` via `item.pricing.yearly_iptu` (in search) and `detail.pricing.yearly_iptu` (in detail).
- In `_format_item`:
  Calculate `monthly_iptu = round(float(item.pricing.yearly_iptu) / 12.0, 2) if item.pricing.yearly_iptu else None`.
  Emit `"iptu": monthly_iptu`.
- In `get_property_detail`:
  Extract yearly IPTU, compute monthly IPTU, and emit `"iptu": monthly_iptu`.

#### `minascaixaimoveis` (`minascaixaimoveis/scripts/client/parsers.py` & `scripts/domain/entities.py`)
- InGaia payload provides `valoriptu` and `valoriptuanual`.
- In `SearchResultParser._build_core`:
  Parse `valoriptu` as monthly; if absent or zero, fall back to `valoriptuanual / 12.0`.
  Pass `iptu: float | None` into `ListingValuation(..., iptu=iptu)`.
- In `ListingValuation`:
  Add `iptu: float | None = None`.
- In `RentalListing.to_dictionary()`:
  Include `"iptu": self.core.valuation.iptu`.

#### `cabralporto` (`cabralporto/scripts/client/parsers.py` & `scripts/domain/entities.py`)
- Tecimob API exposes `total_taxes_price` (e.g. `"R$0,00"`, `"R$220,00"`).
- In `ListingCardParser.parse_single_listing`:
  Parse `total_taxes_price` with `_parse_price_float`. If > 0, set `iptu`.
  Pass `iptu: float | None` into `ListingValuation(..., iptu=iptu)`.
- In `ListingValuation`:
  Add `iptu: float | None = None`.
- In `RentalListing.to_dictionary()`:
  Include `"iptu": self.core.valuation.iptu`.

#### `imobiliariaportalmg` (`imobiliariaportalmg/scripts/client/parsers.py` & `scripts/domain/entities.py`)
- Detail HTML exposes `IPTU: R$ {N}`.
- In `PropertyDetailParser._extract_financials`:
  Match `r"IPTU:\s*R\$\s*([\d\.,]+)"`.
  If matched, create `ListingPrice` and assign to `ListingFinancials.iptu`.
- In `RentalPropertyDetail.to_dictionary()`:
  Include `"iptu": self.financials.iptu.value() if self.financials.iptu else None`.

## Test-Driven Development (TDD) Plan: RED → GREEN

### Phase 1: central_mcp
1. **RED tests** in `central_mcp/tests/test_service.py` & `central_mcp/tests/test_domain.py`:
   - `test_project_listing_with_condo_and_iptu`: rent 1200.0, condo 300.0, iptu 100.0 -> total 1600.0.
   - `test_project_listing_with_iptu_only`: rent 1000.0, condo None, iptu 50.0 -> total 1050.0.
   - `test_service_detail_includes_iptu_and_total_price`.
   - `test_listing_summary_includes_iptu`.
2. **GREEN implementation**:
   - Implement `_extract_iptu`, update `_calculate_total_price`, update `project_listing`, and `_enrich_detail_pricing`.
   - Update `ListingFeatures` and `ListingSummary.to_dict()` in domain entities.
   - Run `cd central_mcp && .venv/bin/pytest -v`.

### Phase 2: vivareal
1. **RED test** in `vivareal/tests/test_mcp_adapter.py`:
   - Assert `listing["iptu"] == 50.0` (from yearly 600) and `detail["iptu"] == 50.0`.
2. **GREEN implementation** in `vivareal/scripts/mcp/tools.py`:
   - Add monthly IPTU conversion and output.
   - Run `cd vivareal && .venv/bin/pytest -v`.

### Phase 3: minascaixaimoveis
1. **RED test** in `minascaixaimoveis/tests/test_service_mock.py`:
   - Assert `listing["iptu"] == 150.0` when `valoriptu` is present.
   - Assert `listing["iptu"] == 100.0` when `valoriptuanual == "1200,00"`.
2. **GREEN implementation** in `minascaixaimoveis/scripts/client/parsers.py` & `scripts/domain/entities.py`:
   - Implement extraction, domain field, and serialization.
   - Run `cd minascaixaimoveis && PYTHONPATH=. .venv/bin/pytest -v`.

### Phase 4: cabralporto
1. **RED test** in `cabralporto/tests/test_parsers.py`:
   - Assert `detail["iptu"] == 120.0` from `total_taxes_price: "R$ 120,00"`.
2. **GREEN implementation** in `cabralporto/scripts/client/parsers.py` & `scripts/domain/entities.py`:
   - Parse `total_taxes_price` into `ListingValuation.iptu` and serialize.
   - Run `cd cabralporto && .venv/bin/pytest -v`.

### Phase 5: imobiliariaportalmg
1. **RED test** in `imobiliariaportalmg/tests/test_mcp_adapter.py` and `test_parsers.py`:
   - Detail page containing `"IPTU: R$ 85,00"` outputs `"iptu": 85.0`.
2. **GREEN implementation** in `imobiliariaportalmg/scripts/client/parsers.py` & `scripts/domain/entities.py`:
   - Extract regex from text, assign to `ListingFinancials.iptu`, and serialize.
   - Run `cd imobiliariaportalmg && .venv/bin/pytest -v`.

### Phase 6: End-to-End Verification
- Run all test suites across modified projects:
  - `cd central_mcp && .venv/bin/pytest`
  - `cd vivareal && .venv/bin/pytest`
  - `cd minascaixaimoveis && PYTHONPATH=. .venv/bin/pytest`
  - `cd cabralporto && .venv/bin/pytest`
  - `cd imobiliariaportalmg && .venv/bin/pytest`
- Run linting: `ruff check .`

## Object Calisthenics Compliance
- **No `else`**: Use guard clauses and default values (`fee or 0.0`).
- **≤ 15 lines per function**: Helper functions (`_extract_iptu`, `_calculate_total_price`) kept concise.
- **≤ 1 indent level**: Guard clauses for early exit.
- **Value Objects**: Domain models continue using `ListingPrice` where appropriate.
