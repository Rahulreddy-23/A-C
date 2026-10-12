import json

from anthropic import Anthropic


class AnthropicAdapter:
    def complete(self, model: str, prompt: str, pack: dict, limit: int) -> dict:
        response = Anthropic().messages.create(
            model=model,
            max_tokens=limit,
            temperature=0,
            messages=[{"role": "user", "content": prompt + "\n" + json.dumps(pack)}],
        )
        return json.loads(response.content[0].text)
