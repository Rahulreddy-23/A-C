import json

from openai import OpenAI

from dhf.config import setting
from dhf.llm.errors import DraftingUnavailable, provider_error
from dhf.models import strict_claims_schema


class OpenAIAdapter:
    def complete(self, model: str, prompt: str, pack: dict, limit: int) -> dict:
        api_key = setting("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY; configure it in .env")
        try:
            response = OpenAI(api_key=api_key, max_retries=0).chat.completions.create(
                model=model,
                max_completion_tokens=limit,
                temperature=0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "claims_v1",
                        "strict": True,
                        "schema": strict_claims_schema(),
                    },
                },
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(pack)},
                ],
            )
        except Exception as exc:
            raise provider_error(exc, "openai") from None
        choice = response.choices[0]
        message = getattr(choice, "message", None)
        refused = getattr(message, "refusal", None)
        if choice.finish_reason != "stop" or refused or not getattr(message, "content", None):
            reason = (
                "refusal"
                if refused
                else ("truncated" if choice.finish_reason != "stop" else "empty_output")
            )
            raise DraftingUnavailable(reason, "openai")
        try:
            output = json.loads(choice.message.content)
        except (ValueError, TypeError):
            raise DraftingUnavailable("unparseable", "openai") from None
        if not isinstance(output, dict):
            raise DraftingUnavailable("invalid_schema", "openai")
        output["_usage"] = {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        }
        return output
