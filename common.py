"""Helpers shared by the UDisc and TechDisc data modules."""

from datetime import date


def check_day(value, name):
    """Return value as a normalized YYYY-MM-DD string; None and empty pass through. Raises ValueError otherwise."""
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        raise ValueError(f"{name} must be a date like 2026-10-17, got {value!r}") from None
