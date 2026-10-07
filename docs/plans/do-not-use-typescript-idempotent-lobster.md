# Plan: Incorporate Condominium Fees and Total Cost in central_mcp and Subprojects

## Context

When searching for rental properties, nominal rent does not reflect the total monthly cost. Condominium fees (`condo_fee`) often represent a substantial portion of monthly expenditure.
Per user instructions:
- Output detailed prices: `rent_price`, `condo_fee`, and `total_price` (calculated as `rent_price + condo_fee`, or `rent_price` if condo is 0 or absent).
- Keep `price` for backward compatibility.
- Update `central_mcp` projection, filtering, and detail endpoints.
- Update subproject parsers/adapters where condominium data is available in APIs or HTML.

## Architectural Changes & Design

### 1. central_mcp (`central_mcp/src/central_mcp/application/service.py`)

- **Extract Rent Price (`_parse_numeric_price`)**:
  Helper converting numeric/formatted BRL prices (e.g. `1500.0`, `"R$ 1.500,00"`) into `float | None`.
- **Extract Condo Fee (`_extract_condo_fee`)**:
  Searches keys: `condo_fee`, `condo`, `monthly_condo`, `condominium`, `condominio`, `valor_condominio`, `condominium_price`, `expenses`.
  Normalizes via `_parse_numeric_price` to `float | None`.
- **Calculate Total Price (`_calculate_total_price`)**:
  Returns `round(rent + (condo or 0.0), 2)` if `rent` is known, else `None`.
- **Update `project_listing`**:
  ```python
  {
      "provider": provider,
      "code": str(code) if code is not None else None,
      "title": str(title) if title is not None else None,
      "location": location,
      "price": price,  # backwards-compatible string or raw value
      "rent_price": rent_price,  # float | None
      "condo_fee": condo_fee,    # float | None
      "total_price": total_price, # float | None
      "bedrooms": int(bedrooms) if bedrooms is not None else None,
      "url": str(url) if url is not None else None,
  }
  ```
- **Update `detail` endpoint**:
  Normalize `rent_price`, `condo_fee`, and `total_price` in the property detail result dict.
- **Update `ListingFeatures` and `ListingSummary` in domain** (`central_mcp/src/central_mcp/domain/entities.py`):
  Add `condo_fee: float | None = None` and `total_price: float | None = None` to `ListingSummary.to_dict()`.

### 2. Subproject Updates

- **`vivareal`** (`vivareal/scripts/mcp/tools.py`):
  Currently returns `"condo": item.pricing.monthly_condo`.
  Add `"condo_fee": float(item.pricing.monthly_condo) if item.pricing.monthly_condo else 0.0`.
  In `get_property_detail`, include `condo_fee: float | None`.
- **`minascaixaimoveis`** (`minascaixaimoveis/scripts/client/parsers.py` & `scripts/domain/entities.py`):
  `valorcondominio` is already in the API payload.
  Extract `condo_fee` in `SearchResultParser` and include `condo_fee` in `ListingValuation` / `RentalListing.to_dictionary()`.
- **`cabralporto`** (`cabralporto/scripts/mcp/tools.py`):
  Expose `condo_fee` in `get_property_detail` if present in `PropertyDetail`.
- **`imobiliariaportalmg`** (`imobiliariaportalmg/scripts/mcp/tools.py`):
  Expose `condo_fee` in `get_property_detail`.

### 3. Test-Driven Development (TDD) Steps

1. **RED in central_mcp**:
   Add unit tests in `central_mcp/tests/test_service.py`:
   - `test_project_listing_with_condo_and_total_price`: verifying `rent_price=1200.0`, `condo_fee=300.0`, `total_price=1500.0`.
   - `test_project_listing_without_condo_fee`: verifying `rent_price=1000.0`, `condo_fee=None`, `total_price=1000.0`.
   - `test_service_detail_includes_condo_breakdown`.
2. **GREEN in central_mcp**:
   Implement helper functions and updated projection in `central_mcp/src/central_mcp/application/service.py`.
   Update domain entities in `central_mcp/src/central_mcp/domain/entities.py`.
3. **RED in vivareal & minascaixaimoveis**:
   Add test for `condo_fee` field in `vivareal/tests/test_mcp_adapter.py` and `minascaixaimoveis/tests/test_service_mock.py`.
4. **GREEN in vivareal & minascaixaimoveis**:
   Implement `condo_fee` exposure in their listing serializers.
5. **Full Suite Verification**:
   - `cd central_mcp && .venv/bin/pytest -v` (all 51+ tests pass).
   - `cd vivareal && .venv/bin/pytest -v`.
   - `cd minascaixaimoveis && .venv/bin/pytest -v`.
   - Live query validation.

## Critical Files

- `central_mcp/src/central_mcp/application/service.py`
- `central_mcp/src/central_mcp/domain/entities.py`
- `central_mcp/src/central_mcp/server.py`
- `central_mcp/tests/test_service.py`
- `vivareal/scripts/mcp/tools.py`
- `vivareal/tests/test_mcp_adapter.py`
- `minascaixaimoveis/scripts/client/parsers.py`
- `minascaixaimoveis/scripts/domain/entities.py`
- `minascaixaimoveis/tests/test_service_mock.py`
