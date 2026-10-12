"""Shared conservative token estimate for ordinary engineering text."""


def estimate_tokens(text: str) -> int:
    return (len(text.encode("utf-8")) + 2) // 3
