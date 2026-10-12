"""Shared pure ID and number parsing, independent of generation orchestration."""

import re
from decimal import Decimal

ID_PATTERN = re.compile(
    r"\b(?:UN|SYS|SRS|HAZ|RC|COMP|TC|BUG|PR|RUN|RES|UNIT|SOUP|ADR|ACT|REV)-[A-Za-z0-9_.-]+"
)
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d+(?:\.\d+)?(?![A-Za-z0-9_])")


def numbers(text: str) -> set[str]:
    text = ID_PATTERN.sub("", text)
    return {format(Decimal(n).normalize(), "f") for n in NUMBER_PATTERN.findall(text)}


def fact_numbers(value: object) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(fact_numbers(v) for v in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(fact_numbers(v) for v in value)) if value else set()
    if isinstance(value, bool) or value is None:
        return set()
    return numbers(str(value))
