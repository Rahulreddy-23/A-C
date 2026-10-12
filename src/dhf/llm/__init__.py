"""Cached, budget-guarded provider interface. Reserve worst-case cost before calling."""

import fcntl
import hashlib
import json
from pathlib import Path
from typing import Protocol

from dhf.config import setting
from dhf.models import Claims


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Adapter(Protocol):
    def complete(self, model: str, prompt: str, pack: dict, limit: int) -> dict: ...


class BudgetExceeded(ValueError):
    pass


class LLM:
    def __init__(
        self,
        provider: str = "mock",
        root: Path = Path("out"),
        adapter: Adapter | None = None,
        run_cap: float | None = None,
        build_cap: float | None = None,
        total_cap: float | None = None,
    ) -> None:
        self.provider = provider
        self.model = setting(f"DHF_MODEL_{provider.upper()}", "mock-v1")
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache = root / "cache"
        self.cache.mkdir(exist_ok=True)
        self.run_cap = float(setting("DHF_MAX_USD_PER_RUN", "0.25")) if run_cap is None else run_cap
        self.build_cap = (
            float(setting("DHF_BUILD_BUDGET_USD", "1.50")) if build_cap is None else build_cap
        )
        self.total_cap = (
            float(setting("DHF_PROVIDER_BUDGET_USD", "5")) if total_cap is None else total_cap
        )
        self.run_spend = 0.0
        self.hits = 0
        self.calls = 0
        if adapter is None:
            if provider == "mock":
                from dhf.llm.adapters.mock import MockAdapter

                adapter = MockAdapter()
            elif provider == "anthropic":
                from dhf.llm.adapters.anthropic import AnthropicAdapter

                adapter = AnthropicAdapter()
            elif provider == "openai":
                from dhf.llm.adapters.openai import OpenAIAdapter

                adapter = OpenAIAdapter()
            else:
                raise ValueError("Unknown provider")
        self.adapter = adapter

    def generate(
        self, prompt_id: str, version: int, prompt: str, pack: dict, max_output_tokens: int = 1000
    ) -> dict:
        if self.provider != "mock" and (
            not pack.get("evidence")
            or any(not a.get("attributes", {}).get("synthetic", False) for a in pack["evidence"])
        ):
            raise ValueError("External APIs require exclusively synthetic evidence")
        key = hashlib.sha256(
            canonical(
                {
                    "prompt_id": prompt_id,
                    "version": version,
                    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "provider": self.provider,
                    "model": self.model,
                    "pack": pack,
                }
            ).encode()
        ).hexdigest()
        cached = self.cache / f"{self.provider}-{key}.json"
        lock = self.root / "ledger.lock"
        with lock.open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            if cached.exists():
                self.hits += 1
                return Claims.model_validate_json(cached.read_text()).model_dump(mode="json")
            # UTF-8 bytes bound input tokens conservatively; reserve all output tokens.
            input_tokens = len((prompt + canonical(pack)).encode())
            in_price = float(setting(f"DHF_{self.provider.upper()}_INPUT_PER_MILLION", "0"))
            out_price = float(setting(f"DHF_{self.provider.upper()}_OUTPUT_PER_MILLION", "0"))
            if self.provider != "mock" and (in_price <= 0 or out_price <= 0):
                raise ValueError("Positive configured provider prices required")
            cost = (
                0
                if self.provider == "mock"
                else (input_tokens * in_price + max_output_tokens * out_price) / 1e6
            )
            ledger_path = self.root / "ledger.json"
            ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
            spent = ledger.get(self.provider, {}).get("reserved_usd", 0.0)
            if self.run_spend + cost > self.run_cap or spent + cost > min(
                self.build_cap, self.total_cap * 0.8
            ):
                raise BudgetExceeded("LLM budget cap reached")
            self.run_spend += cost
            ledger[self.provider] = {
                "reserved_usd": spent + cost,
                "calls": ledger.get(self.provider, {}).get("calls", 0) + 1,
            }
            temp = ledger_path.with_suffix(".tmp")
            temp.write_text(canonical(ledger))
            temp.replace(ledger_path)
            self.calls += 1
            # Failed calls retain the reservation: fail safe rather than overspend.
            result = Claims.model_validate(
                self.adapter.complete(self.model, prompt, pack, max_output_tokens)
            )
            cached.write_text(result.model_dump_json())
            return result.model_dump(mode="json")
