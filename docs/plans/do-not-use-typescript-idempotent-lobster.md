# Fix: Epifânio price parser and VivaReal default bedroom filter

## Context

Two bugs deferred during the `central_mcp` implementation review:

1. **Epifânio** (`scripts/client/search_parser.py:77-82`): `_extract_card_price` strips *all* non-digit characters with `re.sub(r"[^\d]", "", text)`. Brazilian formatting uses `.` as thousands separator and `,` for decimals — so `R$ 1.150,00` becomes `115000.0` (100× too large). The detail parser HTML fallback (`scripts/client/parsers.py:112`) has the same bug.
2. **VivaReal** (`scripts/mcp/tools.py:42`): `_build_filter` forces `rooms = [bedrooms] if bedrooms > 0 else [2, 3, 4]`. An unconstrained search (no bedroom intent) silently limits results to 2, 3 or 4 bedrooms, excluding studios and 1-bedroom properties. The underlying infrastructure already supports an empty filter — `FilterSpecification` defaults to `RoomFilter(())`, and the URL builder omits the `bedrooms` API parameter when the filter is empty.

## Scope

Touch only the two subproject files, their tests, and the two subproject suites. `central_mcp` code is unchanged; its 51-test suite stays green as-is.

## Plan

### Task 1: Epifânio price parser (TDD, RED→GREEN)

**Files:**
- `epifanioimoveis/scripts/client/search_parser.py` — `_extract_card_price` + shared `_parse_brl_price`
- `epifanioimoveis/scripts/client/parsers.py` — `_extract_price` HTML fallback
- `epifanioimoveis/tests/test_parsers.py` — add localized BRL regression cases

**Algorithm:**
BRL `R$ 1.150,00` → remove `R$` and spaces → `1.150,00` → remove `.` thousands separators → `1150,00` → replace `,` decimal → `1150.00` → `float("1150.00")` = `1150.0`.
Edge case: `R$ 2.930` (no cents) → `2.930` → `2930` → `2930.0`. ✓

**Shared helper** (≤15 lines, single indent, no `else`):
```python
def _parse_brl_price(text: str) -> float:
    """Convert Brazilian-formatted price string to float. Returns 0.0 on failure."""
    clean = re.sub(r"[R$\s]", "", text)          # remove R$, spaces
    clean = clean.replace(".", "").replace(",", ".")  # thousands → decimal dot
    return float(clean) if clean else 0.0
```

Use `_parse_brl_price` in both `_extract_card_price` (search_parser.py) and the HTML fallback of `_extract_price` (parsers.py).

**Tests to add** in `epifanioimoveis/tests/test_parsers.py`:
- Card with `R$ 1.150,00` → `price` field = `1150.0`
- Card with `R$ 2.930` (no comma) → `price` field = `2930.0`
- Detail HTML fallback (no JSON-LD) with `R$ 1.150,00` → price = `1150.0`

**Verification:**
```bash
cd epifanioimoveis && .venv/bin/pytest -q tests/test_parsers.py
# Expected: all existing + 3 new tests pass
```

---

### Task 2: VivaReal default bedroom filter (TDD, RED→GREEN)

**File:**
- `vivareal/scripts/mcp/tools.py` — `_build_filter` line 42
- `vivareal/tests/test_mcp_adapter.py` — add unconstrained search test

**Change** (one line):
```python
# Before
rooms = [bedrooms] if bedrooms > 0 else [2, 3, 4]
# After
rooms = [bedrooms] if bedrooms and bedrooms > 0 else []
```

Empty `rooms` → `RoomFilter.from_iterable([])` → `RoomFilter(())` → URL builder omits `bedrooms` parameter (existing behaviour in `url_builder.py:81-82`).

**Tests to add** in `vivareal/tests/test_mcp_adapter.py`:
- `adapter.search_rentals(city="Timóteo")` → captured `FilterSpecification.bedrooms` is empty (`is_empty()` = True)
- `adapter.search_rentals(city="Timóteo", bedrooms=0)` → same, empty filter
- Existing `bedrooms=2` test continues to pass unchanged

**Verification:**
```bash
cd vivareal && .venv/bin/pytest -q tests/test_mcp_adapter.py
# Expected: all existing + new tests pass
```

---

### Final verification

```bash
# Epifânio full suite
cd epifanioimoveis && .venv/bin/pytest -q
# Expected: 44+ passed

# VivaReal full suite
cd vivareal && .venv/bin/pytest -q
# Expected: 37+ passed

# Central MCP — unchanged, must stay 51/51
cd central_mcp && .venv/bin/pytest -q
# Expected: 51 passed
```

## Commit

One commit per subproject (epifânio, vivareal). Merge directly into `main`.
