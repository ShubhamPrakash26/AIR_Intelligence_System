"""Utility helper functions."""

from typing import Any
from uuid import uuid4


def generate_incident_id() -> str:
    """
    Generate a unique incident ID.

    Returns:
        UUID string
    """
    return str(uuid4())


def safe_get(data: dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Safely get a value from a dictionary.

    Args:
        data: Dictionary to access
        key: Key to look up
        default: Default value if key not found

    Returns:
        Value at key or default
    """
    if data is None:
        return default
    return data.get(key, default)


def normalize_whitespace(text: str | None) -> str | None:
    """
    Normalize whitespace in text.

    Args:
        text: Text to normalize

    Returns:
        Normalized text or None
    """
    if text is None:
        return None
    return " ".join(text.split())


def chunk_list(lst: list[Any], chunk_size: int) -> list[list[Any]]:
    """
    Split a list into chunks of specified size.

    Args:
        lst: List to chunk
        chunk_size: Size of each chunk

    Returns:
        List of chunks
    """
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = "_") -> dict[str, Any]:
    """
    Flatten nested dictionary.

    Args:
        d: Dictionary to flatten
        parent_key: Parent key prefix
        sep: Separator for nested keys

    Returns:
        Flattened dictionary
    """
    items: list = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)
