import json

from anthropic import Anthropic

from dhf.config import setting
from dhf.models import strict_claims_schema


class AnthropicAdapter:
    def complete(self, model: str, prompt: str, pack: dict, limit: int) -> dict:
        api_key = setting("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Missing ANTHROPIC_API_KEY; configure it in .env")
        response = Anthropic(api_key=api_key, max_retries=0).messages.create(
            model=model,
            max_tokens=limit,
            system=prompt,
            output_config={
                "format": {"type": "json_schema", "schema": strict_claims_schema()},
                "effort": "low",
            },
            messages=[{"role": "user", "content": json.dumps(pack)}],
        )
        if response.stop_reason in ("max_tokens", "refusal"):
            raise ValueError(f"Anthropic response unusable: {response.stop_reason}")
        texts = [block.text for block in response.content if block.type == "text"]
        if not texts:
            raise ValueError("Anthropic returned no text output")
        output = json.loads("".join(texts))
        output["_usage"] = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return output
