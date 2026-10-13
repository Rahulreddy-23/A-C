"""BD-tenant prompt transport; never sends data to a personal model API."""

import json
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from dhf.config import setting
from dhf.llm.errors import DraftingUnavailable


def request_payload(
    request_id: str,
    prompt_id: str,
    prompt_version: int,
    instructions: str,
    pack: dict,
    schema: dict,
) -> dict:
    """Build the exact versioned text-input contract shared by both transports."""
    from dhf.llm import canonical

    return {
        "request_id": request_id,
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "instructions": instructions,
        "facts_json": canonical(pack["facts"]),
        "evidence_json": canonical(pack["evidence"]),
        "output_schema_json": canonical(schema),
        "max_claims": int(pack.get("max_claims", 6)),
    }


class CopilotStudioAdapter:
    """One request/response envelope; the LLM layer handles budget and cache."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client

    def complete_request(self, request: dict) -> dict:
        mode = setting("DHF_COPILOT_MODE", "http")
        if mode == "http":
            raw = self._http(request)
        elif mode == "folder":
            raw = self._folder(request)
        else:
            raise ValueError("DHF_COPILOT_MODE must be http or folder")
        return self._parse(raw, request["request_id"])

    def complete_batch(self, request: dict) -> dict:
        """One file per document; the cloud flow loops its section requests."""
        raw = self._folder(request)
        if not isinstance(raw, dict) or raw.get("request_id") != request["request_id"]:
            raise DraftingUnavailable("request_id_mismatch", "copilotstudio")
        if raw.get("document_id") != request["document_id"] or not isinstance(
            raw.get("sections"), list
        ):
            raise DraftingUnavailable("invalid_schema", "copilotstudio")
        return raw

    def _http(self, request: dict) -> dict:
        url = setting("DHF_COPILOT_FLOW_URL")
        if not url:
            raise ValueError("Configure DHF_COPILOT_FLOW_URL in .env")
        parsed = urlsplit(url)
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1")
        ):
            raise ValueError("Copilot flow URL must use HTTPS")
        try:
            if self.client is None:
                with httpx.Client(timeout=float(setting("DHF_COPILOT_TIMEOUT_S", "120"))) as client:
                    response = client.post(url, json=request)
            else:
                response = self.client.post(url, json=request)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise DraftingUnavailable(
                "provider_error", "copilotstudio", status=exc.response.status_code
            ) from None
        except (httpx.HTTPError, ValueError) as exc:
            # Request URLs can contain signed secrets. Never include exception text.
            raise DraftingUnavailable(
                "provider_error", "copilotstudio", error_type=type(exc).__name__
            ) from None

    def _folder(self, request: dict) -> dict:
        root_value = setting("DHF_COPILOT_EXCHANGE_DIR")
        if not root_value:
            raise ValueError("Configure DHF_COPILOT_EXCHANGE_DIR in .env")
        root = Path(root_value)
        outgoing, incoming = root / "requests", root / "responses"
        outgoing.mkdir(parents=True, exist_ok=True)
        incoming.mkdir(parents=True, exist_ok=True)
        request_id = request["request_id"]
        target = outgoing / (request_id + ".json")
        temp = outgoing / (request_id + ".tmp")
        temp.write_text(json.dumps(request, sort_keys=True, ensure_ascii=False))
        temp.replace(target)
        response = incoming / (request_id + ".json")
        deadline = time.monotonic() + float(setting("DHF_COPILOT_TIMEOUT_S", "120"))
        while time.monotonic() < deadline:
            if response.exists():
                try:
                    return json.loads(response.read_text())
                except (ValueError, OSError):
                    raise DraftingUnavailable("unparseable", "copilotstudio") from None
            time.sleep(0.2)
        raise DraftingUnavailable("timeout", "copilotstudio")

    @staticmethod
    def _parse(raw: object, request_id: str) -> dict:
        if not isinstance(raw, dict):
            raise DraftingUnavailable("invalid_schema", "copilotstudio")
        if raw.get("request_id") != request_id:
            raise DraftingUnavailable("request_id_mismatch", "copilotstudio")
        if raw.get("status") in ("refused", "failed"):
            raise DraftingUnavailable(
                "refusal" if raw["status"] == "refused" else "provider_error", "copilotstudio"
            )
        claims_json = raw.get("claims_json")
        if not claims_json:
            raise DraftingUnavailable("empty_output", "copilotstudio")
        if not isinstance(claims_json, str):
            raise DraftingUnavailable("invalid_schema", "copilotstudio")
        try:
            claims = json.loads(claims_json)
        except (ValueError, TypeError):
            raise DraftingUnavailable("unparseable", "copilotstudio") from None
        if not isinstance(claims, dict):
            raise DraftingUnavailable("invalid_schema", "copilotstudio")
        model = raw.get("model")
        if not isinstance(model, str) or not model or len(model) > 120:
            raise DraftingUnavailable("invalid_schema", "copilotstudio")
        usage = {k: raw.get(k) for k in ("input_tokens", "output_tokens")}
        if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in usage.values()):
            raise DraftingUnavailable("invalid_usage", "copilotstudio")
        return {**claims, "_usage": usage, "_model": model}
