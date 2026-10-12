import json

from openai import OpenAI


class OpenAIAdapter:
    def complete(self, model: str, prompt: str, pack: dict, limit: int) -> dict:
        response = OpenAI().chat.completions.create(
            model=model,
            max_tokens=limit,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt + "\n" + json.dumps(pack)}],
        )
        return json.loads(response.choices[0].message.content)
