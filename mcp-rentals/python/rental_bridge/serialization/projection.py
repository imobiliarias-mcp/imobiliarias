"""Minimal projections retain only facts known from an existing result."""


def clean_projection(item):
    """Omit unknown fields without changing explicit zero or typed references."""
    return {key: value for key, value in item.items() if value is not None and value != ''}
