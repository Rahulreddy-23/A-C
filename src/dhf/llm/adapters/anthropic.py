import json

from anthropic import Anthropic

from dhf.config import setting
from dhf.llm.errors import DraftingUnavailable, provider_error
from dhf.models import strict_claims_schema


class AnthropicAdapter:
    def complete(
        self, model: str, prompt: str, pack: dict, limit: int, schema: dict | None = None
    ) -> dict:
        api_key = setting("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Missing ANTHROPIC_API_KEY; configure it in .env")
        try:
            response = Anthropic(api_key=api_key, max_retries=0).messages.create(
                model=model,
                max_tokens=limit,
                system=prompt,
                output_config={
                    "format": {"type": "json_schema", "schema": schema or strict_claims_schema()},
                    "effort": "low",
                },
                messages=[{"role": "user", "content": json.dumps(pack)}],
            )
        except Exception as exc:
            raise provider_error(exc, "anthropic") from None
        if response.stop_reason in ("max_tokens", "refusal"):
            details = getattr(response, "stop_details", None)
            category = (
                details.get("category")
                if isinstance(details, dict)
                else getattr(details, "category", None)
            )
            raise DraftingUnavailable(response.stop_reason, "anthropic", category=category)
        texts = [block.text for block in response.content if block.type == "text"]
        if not texts:
            raise DraftingUnavailable("empty_output", "anthropic")
        try:
            output = json.loads("".join(texts))
        except (ValueError, TypeError):
            raise DraftingUnavailable("unparseable", "anthropic") from None
        if not isinstance(output, dict):
            raise DraftingUnavailable("invalid_schema", "anthropic")
        output["_usage"] = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return output
