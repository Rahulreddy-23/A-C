import json

from openai import OpenAI

from dhf.config import setting
from dhf.models import strict_claims_schema


class OpenAIAdapter:
    def complete(self, model: str, prompt: str, pack: dict, limit: int) -> dict:
        response = OpenAI(api_key=setting("OPENAI_API_KEY"), max_retries=0).chat.completions.create(
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
        choice = response.choices[0]
        if choice.finish_reason != "stop" or choice.message.refusal or not choice.message.content:
            raise ValueError("OpenAI returned truncated, refused or empty output")
        output = json.loads(choice.message.content)
        output["_usage"] = {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        }
        return output
