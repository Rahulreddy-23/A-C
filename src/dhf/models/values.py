"""Shared pure ID and number parsing, independent of generation orchestration."""

import re
from decimal import Decimal

ID_PATTERN = re.compile(
    r"\b(?:(?:UN|SYS|SRS|HAZ|RC|COMP|TC|BUG|PR|RUN|RES|ACT|REV|ADR|SOUP|ADO)-"
    r"\d[\w.-]*|UNIT-[a-z_]+"
    # Real-project IDs: document IDs (SPEC-KS-4303, PREQ-KS-1) and imported architecture
    # items and units (SI-Fleet-Service, UNIT-Fleet.Ks.Fleet.Core).
    r"|[A-Z][A-Z0-9]+-[A-Z][A-Z0-9]+-\d+"
    r"|(?:SI|UNIT)-[A-Z][A-Za-z0-9]*(?:[.-][A-Za-z0-9]+)*)\b"
)
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_.])[-+]?\d+(?:\.\d+)?(?![A-Za-z0-9_]|\.\d)")

UNIT_NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.])[-+]?\d+(?:\.\d+)?"
    r"(?=(?:ms|s|min|h|kPa|Pa|mL|L|kg|mg|g|bytes?|KB|MB|Hz)\b)"
)


def numbers(text: str) -> set[str]:
    text = ID_PATTERN.sub("", text)
    return {
        format(Decimal(n).normalize(), "f")
        for n in [*NUMBER_PATTERN.findall(text), *UNIT_NUMBER_PATTERN.findall(text)]
    }


def fact_numbers(value: object) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(fact_numbers(v) for v in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(fact_numbers(v) for v in value)) if value else set()
    if isinstance(value, bool) or value is None:
        return set()
    return numbers(str(value))
