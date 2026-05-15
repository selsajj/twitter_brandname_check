"""
Generate likely impersonation variants of a given X/Twitter handle.
"""

import re
from itertools import product

# Character substitution map (leet-speak and lookalikes)
CHAR_SUBS: dict[str, list[str]] = {
    "a": ["4", "@"],
    "e": ["3"],
    "i": ["1", "l"],
    "l": ["1", "i"],
    "o": ["0"],
    "s": ["5"],
    "t": ["7"],
    "b": ["8"],
    "g": ["9"],
}

PREFIXES = ["real", "official", "the", "its", "i_am", "im", "actual", "true"]
SUFFIXES = ["real", "official", "hq", "co", "org", "inc", "tv", "official", "account"]

# X handle rules: 4–15 chars, alphanumeric + underscore only
HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")


def _is_valid(handle: str) -> bool:
    return bool(HANDLE_RE.match(handle)) and len(handle) >= 1


def _char_sub_variants(handle: str) -> list[str]:
    """Single-character substitutions (one substitution at a time)."""
    variants = []
    for i, ch in enumerate(handle.lower()):
        if ch in CHAR_SUBS:
            for sub in CHAR_SUBS[ch]:
                variant = handle[:i] + sub + handle[i + 1:]
                variants.append(variant)
    return variants


def _double_char_variants(handle: str) -> list[str]:
    """Double a character (e.g., twitter → twiitter)."""
    variants = []
    for i, ch in enumerate(handle):
        if ch.isalpha():
            variant = handle[:i] + ch + handle[i:]
            if len(variant) <= 15:
                variants.append(variant)
    return variants


def _drop_char_variants(handle: str) -> list[str]:
    """Drop a single character."""
    variants = []
    for i in range(len(handle)):
        variant = handle[:i] + handle[i + 1:]
        if len(variant) >= 1:
            variants.append(variant)
    return variants


def _swap_adjacent_variants(handle: str) -> list[str]:
    """Swap adjacent characters."""
    variants = []
    for i in range(len(handle) - 1):
        chars = list(handle)
        chars[i], chars[i + 1] = chars[i + 1], chars[i]
        variants.append("".join(chars))
    return variants


def _underscore_variants(handle: str) -> list[str]:
    """Add/remove underscores between words detected by case or existing underscores."""
    variants = []
    # Add underscore before each character position
    for i in range(1, len(handle)):
        v = handle[:i] + "_" + handle[i:]
        if len(v) <= 15:
            variants.append(v)
    # Remove existing underscores
    if "_" in handle:
        variants.append(handle.replace("_", ""))
    return variants


def _prefix_suffix_variants(handle: str) -> list[str]:
    """Apply common prefixes and suffixes."""
    variants = []
    for prefix in PREFIXES:
        v = f"{prefix}_{handle}"
        if len(v) <= 15:
            variants.append(v)
        v2 = f"{prefix}{handle}"
        if len(v2) <= 15:
            variants.append(v2)
    for suffix in SUFFIXES:
        v = f"{handle}_{suffix}"
        if len(v) <= 15:
            variants.append(v)
        v2 = f"{handle}{suffix}"
        if len(v2) <= 15:
            variants.append(v2)
    return variants


def generate_variants(handle: str, max_variants: int = 50) -> list[str]:
    """
    Generate a deduplicated, prioritised list of impersonation variants.
    The original handle is excluded from the results.
    """
    handle = handle.lower().strip().lstrip("@")
    seen: set[str] = {handle}
    ordered: list[str] = []

    generators = [
        _char_sub_variants,
        _prefix_suffix_variants,
        _double_char_variants,
        _underscore_variants,
        _drop_char_variants,
        _swap_adjacent_variants,
    ]

    for gen in generators:
        for v in gen(handle):
            v = v.lower()
            if v not in seen and _is_valid(v):
                seen.add(v)
                ordered.append(v)
            if len(ordered) >= max_variants:
                break
        if len(ordered) >= max_variants:
            break

    return ordered[:max_variants]
