"""Unknown display fields are absent; explicit zero remains known."""
from rental_bridge.serialization.projection import clean_projection


def test_unknown_display_fields_are_not_empty_known_values():
    item = {'reference': None, 'url': None, 'title': '', 'location': None, 'price': 0}
    assert clean_projection(item) == {'price': 0}


def test_typed_reference_and_public_link_are_preserved_exactly():
    item = {'reference': {'kind': 'slug', 'value': 'apartamento-centro'}, 'url': 'https://arthusoimoveis.com.br/imovel/apartamento-centro/', 'title': 'Apartamento'}
    assert clean_projection(item) == item
