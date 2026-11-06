"""Tests that search projections recognize every provider's property identifier."""

import pytest

from central_mcp.application.service import project_listing


@pytest.mark.parametrize(
    ("item", "expected_code"),
    [
        ({"code": "A1"}, "A1"),
        ({"id": 42}, "42"),
        ({"property_code": "P9"}, "P9"),
        ({"property_id": "PX-3"}, "PX-3"),
        ({"reference": "REF-7"}, "REF-7"),
    ],
)
def test_project_listing_reads_code_from_any_known_identifier(item, expected_code):
    assert project_listing("imobiliariaportalmg", item)["code"] == expected_code
