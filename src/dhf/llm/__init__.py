"""Cached, budget-guarded provider interface. Reserve worst-case cost before calling."""

import fcntl
import hashlib
import json
import re
from pathlib import Path
from typing import Protocol

import yaml

from dhf.config import setting
from dhf.models import Claims, strict_claims_schema


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
        root: Path | None = None,
        adapter: Adapter | None = None,
        run_cap: float | None = None,
        build_cap: float | None = None,
        total_cap: float | None = None,
    ) -> None:
        self.provider = provider
        defaults = {"mock": "mock-v2", "openai": "gpt-4.1-mini", "anthropic": "claude-haiku-5-5"}
        self.model = setting(f"DHF_MODEL_{provider.upper()}", defaults.get(provider, ""))
        root = root or Path(setting("DHF_CACHE_ROOT", "out"))
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache = root / "cache"
        self.cache.mkdir(exist_ok=True)
        self.run_cap = float(setting("DHF_MAX_USD_PER_RUN", "0.25")) if run_cap is None else run_cap
        self.build_cap = (
            float(setting("DHF_BUILD_BUDGET_USD", "1.50")) if build_cap is None else build_cap
        )
        owner_cap = {"openai": 4.00, "anthropic": 2.50, "mock": 2.50}.get(provider, 2.50)
        self.total_cap = (
            float(setting("DHF_PROVIDER_BUDGET_USD", str(owner_cap)))
            if total_cap is None
            else total_cap
        )
        self.hard_cap = min(
            owner_cap,
            float(
                setting(
                    "DHF_HARD_CAP_USD_" + provider.upper(),
                    setting("DHF_HARD_CAP_USD", str(owner_cap)),
                )
            ),
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

    def model_for(self, tier: str = "default") -> str:
        if tier not in ("default", "analytical"):
            raise ValueError("Unknown model tier")
        model = self.model
        if tier == "analytical":
            model = setting(
                "DHF_MODEL_" + self.provider.upper() + "_ANALYTICAL",
                "gpt-5.4-mini" if self.provider == "openai" else self.model,
            )
        if self.provider == "openai" and "nano" in model:
            raise ValueError("Nano models are disabled by the review policy")
        return model

    def completion_limit(self, model: str, visible_limit: int) -> int:
        allowance = (
            int(setting("DHF_OPENAI_REASONING_TOKENS", "4000"))
            if self.provider == "openai" and model.startswith("gpt-5")
            else 0
        )
        if allowance < 0 or visible_limit <= 0:
            raise ValueError("Invalid completion token budget")
        return visible_limit + allowance

    def prices(self, model: str) -> tuple[float, float]:
        if self.provider == "mock":
            return 0.0, 0.0
        if self.provider == "openai":
            defaults = yaml.safe_load(Path("specs/llm/prices.yaml").read_text())["openai"].get(
                model, {}
            )
            key = "DHF_OPENAI_" + re.sub(r"[^A-Za-z0-9]", "_", model).upper()
            legacy = model == "gpt-4.1-mini"
            values = [
                setting(
                    key + "_" + direction + "_PER_MILLION",
                    setting(
                        "DHF_OPENAI_" + direction + "_PER_MILLION", str(defaults.get(field, ""))
                    )
                    if legacy
                    else str(defaults.get(field, "")),
                )
                for direction, field in (("INPUT", "input"), ("OUTPUT", "output"))
            ]
        else:
            values = [
                setting("DHF_" + self.provider.upper() + "_INPUT_PER_MILLION", "0.10"),
                setting("DHF_" + self.provider.upper() + "_OUTPUT_PER_MILLION", "0.50"),
            ]
        if any(not value or float(value) <= 0 for value in values):
            raise ValueError("Positive model-specific prices required")
        return float(values[0]), float(values[1])

    def budget_status(self) -> dict:
        """Read cumulative headroom without credentials or provider payloads."""
        path = self.root / "ledger.json"
        ledger = json.loads(path.read_text()) if path.exists() else {}
        entry = ledger.get(self.provider, {})
        actual = entry.get("actual_usd", 0.0)
        reserved = entry.get("reserved_usd", 0.0)
        return {
            "provider": self.provider,
            "actual_usd": actual,
            "reserved_usd": reserved,
            "hard_cap_usd": self.hard_cap,
            "remaining_usd": max(0.0, self.hard_cap - actual - reserved),
        }

    def generate(
        self,
        prompt_id: str,
        version: int,
        prompt: str,
        pack: dict,
        max_output_tokens: int = 4000,
        *,
        model_tier: str = "default",
    ) -> dict:
        if self.provider != "mock" and (
            any(
                not a.get("attributes", {}).get("synthetic", False)
                for a in pack.get("evidence", [])
            )
        ):
            raise ValueError("External APIs require exclusively synthetic evidence")
        model = self.model_for(model_tier)
        completion_limit = self.completion_limit(model, max_output_tokens)
        key = hashlib.sha256(
            canonical(
                {
                    "prompt_id": prompt_id,
                    "version": version,
                    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "provider": self.provider,
                    "model": model,
                    "model_tier": model_tier,
                    "reasoning_effort": setting("DHF_OPENAI_REASONING_EFFORT", "low")
                    if self.provider == "openai" and model.startswith("gpt-5")
                    else None,
                    "completion_limit": completion_limit,
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
            input_tokens = (
                len((prompt + canonical(pack) + canonical(strict_claims_schema())).encode()) + 512
            )
            if self.provider != "mock" and input_tokens > 100_000:
                raise ValueError("Input exceeds configured small-prompt pricing tier")
            in_price, out_price = self.prices(model)
            cost = (
                0
                if self.provider == "mock"
                else (input_tokens * in_price + completion_limit * out_price) / 1e6
            )
            ledger_path = self.root / "ledger.json"
            ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
            entry = ledger.get(self.provider, {})
            outstanding = entry.get("reserved_usd", 0.0)
            actual = entry.get("actual_usd", 0.0)
            spent = outstanding + actual
            if self.run_spend + cost > self.run_cap or spent + cost > min(
                self.build_cap, self.total_cap, self.hard_cap
            ):
                raise BudgetExceeded("LLM budget cap reached")
            self.run_spend += cost
            ledger[self.provider] = {
                **entry,
                "reserved_usd": outstanding + cost,
                "actual_usd": actual,
                "calls": ledger.get(self.provider, {}).get("calls", 0) + 1,
            }
            temp = ledger_path.with_suffix(".tmp")
            temp.write_text(canonical(ledger))
            temp.replace(ledger_path)
            self.calls += 1
            # Failed calls retain the reservation: fail safe rather than overspend.
            raw = self.adapter.complete(model, prompt, pack, completion_limit)
            if not isinstance(raw, dict):
                from dhf.llm.errors import DraftingUnavailable

                raise DraftingUnavailable("invalid_schema", self.provider)
            usage = raw.pop("_usage", None)
            result = Claims.model_validate(raw)
            if usage is not None:
                if any(
                    not isinstance(usage.get(k), int) or usage[k] < 0
                    for k in ("input_tokens", "output_tokens")
                ):
                    raise ValueError("Invalid provider usage")
                billed = (
                    usage["input_tokens"] * in_price + usage["output_tokens"] * out_price
                ) / 1e6
                entry = ledger[self.provider]
                entry["reserved_usd"] -= cost
                entry["actual_usd"] += billed
                entry["input_tokens"] = entry.get("input_tokens", 0) + usage["input_tokens"]
                entry["output_tokens"] = entry.get("output_tokens", 0) + usage["output_tokens"]
                self.run_spend += billed - cost
                temp.write_text(canonical(ledger))
                temp.replace(ledger_path)
            cached.write_text(result.model_dump_json())
            return result.model_dump(mode="json")
