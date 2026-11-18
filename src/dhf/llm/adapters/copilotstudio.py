"""BD-tenant prompt transport; never sends data to a personal model API."""

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from dhf.config import setting
from dhf.llm.errors import DraftingUnavailable
from dhf.llm.tokens import estimate_tokens


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


def destination_fingerprint() -> str:
    """Identify the configured Power Automate trigger or resolved OneDrive folder."""
    mode = setting("DHF_COPILOT_MODE", "http")
    if mode == "http":
        value = setting("DHF_COPILOT_FLOW_URL")
        try:
            parsed = urlsplit(value)
            host = parsed.hostname or ""
            trusted_host = host.endswith((".api.powerplatform.com", ".logic.azure.com"))
            if (
                parsed.scheme != "https"
                or not trusted_host
                or parsed.username is not None
                or parsed.port not in (None, 443)
                or parsed.fragment
                or not parsed.path
            ):
                raise ValueError
        except ValueError:
            raise ValueError("Company evidence requires a Power Automate HTTPS trigger") from None
    elif mode == "folder":
        folder = setting("DHF_COPILOT_EXCHANGE_DIR")
        if not folder or not Path(folder).is_dir():
            raise ValueError("Company evidence requires an existing approved OneDrive folder")
        value = str(Path(folder).resolve())
    else:
        raise ValueError("DHF_COPILOT_MODE must be http or folder")
    return hashlib.sha256(f"{mode}\0{value}".encode()).hexdigest()


def usage_mode() -> str:
    mode = setting("DHF_COPILOT_USAGE", "reported")
    if mode not in ("reported", "estimated"):
        raise ValueError("DHF_COPILOT_USAGE must be reported or estimated")
    return mode


def estimated_usage(request: dict, claims_json: str) -> dict:
    """Estimate the eight prompt text inputs and serialized output, never the URL."""
    text = "".join(str(value) for value in request.values())
    return {"input_tokens": estimate_tokens(text), "output_tokens": estimate_tokens(claims_json)}


class CopilotStudioAdapter:
    """One request/response envelope; the LLM layer handles budget and cache."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client

    def complete_request(self, request: dict) -> dict:
        usage_mode()  # Reject invalid configuration before dispatch.
        mode = setting("DHF_COPILOT_MODE", "http")
        if mode == "http":
            raw = self._http(request)
        elif mode == "folder":
            raw = self._folder(request)
        else:
            raise ValueError("DHF_COPILOT_MODE must be http or folder")
        return self._parse(raw, request["request_id"], request)

    def complete_batch(self, request: dict) -> dict:
        """One file per document; the cloud flow loops its section requests."""
        usage_mode()
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
                    response = client.post(url, json=request, follow_redirects=False)
            else:
                response = self.client.post(url, json=request, follow_redirects=False)
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
        temp.write_text(
            json.dumps(request, sort_keys=True, ensure_ascii=False), encoding="utf-8", newline="\n"
        )
        temp.replace(target)
        response = incoming / (request_id + ".json")
        deadline = time.monotonic() + float(setting("DHF_COPILOT_TIMEOUT_S", "120"))
        while time.monotonic() < deadline:
            if response.exists():
                try:
                    return json.loads(response.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    raise DraftingUnavailable("unparseable", "copilotstudio") from None
            time.sleep(0.2)
        raise DraftingUnavailable("timeout", "copilotstudio")

    @staticmethod
    def _parse(raw: object, request_id: str, request: dict | None = None) -> dict:
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
        mode = usage_mode()
        usage = {k: raw.get(k) for k in ("input_tokens", "output_tokens")}
        # Missing/null fields mean usage is unavailable. Supplied invalid values
        # remain failures in both modes; estimation must not hide corrupt reports.
        if any(
            v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 0)
            for v in usage.values()
        ):
            raise DraftingUnavailable("invalid_usage", "copilotstudio")
        source = "reported"
        if any(v is None for v in usage.values()):
            if mode != "estimated" or request is None:
                raise DraftingUnavailable("invalid_usage", "copilotstudio")
            usage, source = estimated_usage(request, claims_json), "estimated"
        return {**claims, "_usage": usage, "_usage_source": source, "_model": model}
