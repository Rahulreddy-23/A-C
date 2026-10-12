"""Provider failure metadata safe to persist and display without response bodies."""

import re
import traceback


def safe_label(value: object) -> str | None:
    if value is None:
        return None
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(value))[:96]


class DraftingUnavailable(ValueError):
    def __init__(
        self,
        reason: str,
        provider: str,
        category: object = None,
        status: int | None = None,
        error_type: str | None = None,
        request_id: object = None,
    ) -> None:
        self.details = {
            "reason": safe_label(reason),
            "provider": safe_label(provider),
            "stop_details": {"category": safe_label(category)},
            "http_status": status,
            "error_type": safe_label(error_type),
            "request_id": safe_label(request_id),
        }
        super().__init__(f"{provider}: {reason}")


def provider_error(exc: Exception, provider: str) -> DraftingUnavailable:
    failure = DraftingUnavailable(
        "provider_error",
        provider,
        status=getattr(exc, "status_code", None),
        error_type=type(exc).__name__,
        request_id=getattr(exc, "request_id", None),
    )

    failure.details["debug_stack"] = [
        {"file": frame.filename, "line": frame.lineno, "function": frame.name}
        for frame in traceback.extract_tb(exc.__traceback__)
    ]
    return failure
