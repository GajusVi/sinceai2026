import re

STEM_LENGTH = 6


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens cut to a short prefix, a cheap stand-in for Russian stemming
    ("herbicides" and "herbicide" become the same token; works for Russian inflections too)."""
    return [token[:STEM_LENGTH] for token in re.findall(r"\w+", text.lower()) if len(token) > 1]
