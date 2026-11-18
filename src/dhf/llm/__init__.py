"""Cached, budget-guarded provider interface. Reserve worst-case cost before calling."""

import contextlib
import hashlib
import json
import re
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import yaml

from dhf.config import setting
from dhf.models import output_model, strict_output_schema


@contextlib.contextmanager
def exclusive(path: Path) -> Iterator[None]:
    """Exclusive inter-process lock on `path` for the whole block (ledger and cache):
    flock on macOS and Linux, a one-byte msvcrt lock on Windows."""
    with path.open("a+", encoding="utf-8", newline="\n") as handle:
        if sys.platform != "win32":
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX)
            yield
            return
        import msvcrt

        handle.seek(0)
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:  # held by another process
                time.sleep(0.05)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def combine_usage_sources(sources: list[str | None]) -> str:
    valid = {source for source in sources if source in ("reported", "estimated", "mixed")}
    if "mixed" in valid or len(valid) > 1:
        return "mixed"
    return next(iter(valid), "unavailable")


class Adapter(Protocol):
    def complete(
        self, model: str, prompt: str, pack: dict, limit: int, schema: dict | None = None
    ) -> dict: ...


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
        defaults = {
            "mock": "mock-v2",
            "openai": "gpt-4.1-mini",
            "anthropic": "claude-haiku-5-5",
            "copilotstudio": "bd-basic-gpt",
        }
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
        # A recorded clearance reference unlocks company evidence for the BD tenant only;
        # personal model APIs never receive it.
        self.real_data_approval = (
            setting("DHF_REAL_DATA_APPROVAL").strip() if provider == "copilotstudio" else ""
        )
        self.run_spend = 0.0
        self.hits = 0
        self.calls = 0
        self.last_model: str | None = None
        self.last_usage_source: str | None = None
        if provider == "copilotstudio":
            from dhf.llm.adapters.copilotstudio import usage_mode

            usage_mode()
        self.preload_errors: dict[str, Exception] = {}
        self.preloaded_keys: set[str] = set()
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
            elif provider == "copilotstudio":
                from dhf.llm.adapters.copilotstudio import CopilotStudioAdapter

                adapter = CopilotStudioAdapter()
            else:
                raise ValueError("Unknown provider")
        self.adapter = adapter

    def require_evidence_access(self, artifacts: list[dict]) -> None:
        if self.provider == "mock" or all(
            artifact.get("attributes", {}).get("synthetic") is True for artifact in artifacts
        ):
            return
        if not self.real_data_approval:
            raise ValueError("External APIs require exclusively synthetic evidence")
        from dhf.llm.adapters.copilotstudio import destination_fingerprint

        if destination_fingerprint() != setting("DHF_REAL_DATA_DESTINATION_SHA256").strip().lower():
            raise ValueError(
                "Copilot destination does not match the recorded company-data approval"
            )

    def model_for(self, tier: str = "default") -> str:
        if tier not in ("default", "analytical"):
            raise ValueError("Unknown model tier")
        if self.provider == "copilotstudio":
            return self.model  # Both document tiers use the tenant-approved Basic model.
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
        # Prices are per model; the provider-wide legacy keys price only its default model.
        prefix = "DHF_" + self.provider.upper() + "_"
        defaults = (
            yaml.safe_load(Path("specs/llm/prices.yaml").read_text(encoding="utf-8"))
            .get(self.provider, {})
            .get(model, {})
        )
        key = prefix + re.sub(r"[^A-Za-z0-9]", "_", model).upper()
        legacy = model == {"openai": "gpt-4.1-mini", "anthropic": "claude-haiku-5-5"}.get(
            self.provider
        )
        values = [
            setting(
                key + "_" + direction + "_PER_MILLION",
                setting(prefix + direction + "_PER_MILLION", str(defaults.get(field, "")))
                if legacy
                else str(defaults.get(field, "")),
            )
            for direction, field in (("INPUT", "input"), ("OUTPUT", "output"))
        ]
        try:
            input_price, output_price = map(float, values)
        except ValueError:
            raise ValueError("Positive finite model-specific prices required") from None
        if not (0 < input_price < float("inf") and 0 < output_price < float("inf")):
            raise ValueError("Positive finite model-specific prices required")
        return input_price, output_price

    def budget_status(self) -> dict:
        """Read cumulative headroom without credentials or provider payloads."""
        path = self.root / "ledger.json"
        ledger = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        entry = ledger.get(self.provider, {})
        if self.provider == "copilotstudio":
            cap = self.copilot_cap()
            actual = entry.get("actual_credits", 0.0)
            reserved = entry.get("reserved_credits", 0.0)
            return {
                "provider": self.provider,
                "actual_credits": actual,
                "reserved_credits": reserved,
                "hard_cap_credits": cap,
                "remaining_credits": max(0.0, cap - actual - reserved),
                "usage_source": entry.get("usage_source", "unavailable"),
                "credits_by_usage_source": entry.get("credits_by_usage_source", {}),
            }
        actual = entry.get("actual_usd", 0.0)
        reserved = entry.get("reserved_usd", 0.0)
        return {
            "provider": self.provider,
            "actual_usd": actual,
            "reserved_usd": reserved,
            "hard_cap_usd": self.hard_cap,
            "remaining_usd": max(0.0, self.hard_cap - actual - reserved),
        }

    def copilot_cap(self) -> float:
        """Keep the local guard below BD's 600-credit monthly tenant limit."""
        value = float(setting("DHF_COPILOT_CREDIT_CAP", "400"))
        if value <= 0:
            raise ValueError("Copilot credit cap must be positive")
        return min(value, 400.0)

    def request_key(
        self,
        prompt_id: str,
        version: int,
        prompt: str,
        pack: dict,
        schema: dict,
        model: str,
        model_tier: str,
        completion_limit: int,
        output_schema: str,
    ) -> str:
        return hashlib.sha256(
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
                    "output_schema": output_schema,
                    "schema": schema,
                    "pack": pack,
                    **(
                        {
                            "real_data_approval": self.real_data_approval,
                            "real_data_destination": setting("DHF_REAL_DATA_DESTINATION_SHA256"),
                        }
                        if self.real_data_approval
                        else {}
                    ),
                }
            ).encode()
        ).hexdigest()

    def copilot_request(
        self,
        prompt_id: str,
        version: int,
        prompt: str,
        pack: dict,
        max_output_tokens: int = 4000,
        model_tier: str = "default",
    ) -> dict:
        """Preview the exact adapter envelope without reserving credits or sending it."""
        from dhf.llm.adapters.copilotstudio import request_payload

        if self.provider != "copilotstudio":
            raise ValueError("Copilot request preview requires copilotstudio provider")
        self.require_evidence_access(pack.get("evidence", []))
        schema = strict_output_schema("claims.v1")
        model = self.model_for(model_tier)
        limit = self.completion_limit(model, max_output_tokens)
        key = self.request_key(
            prompt_id, version, prompt, pack, schema, model, model_tier, limit, "claims.v1"
        )
        return request_payload(key, prompt_id, version, prompt, pack, schema)

    def generate(
        self,
        prompt_id: str,
        version: int,
        prompt: str,
        pack: dict,
        max_output_tokens: int = 4000,
        *,
        model_tier: str = "default",
        output_schema: str = "claims.v1",
    ) -> dict:
        if self.provider == "copilotstudio" and output_schema != "claims.v1":
            from dhf.llm.errors import DraftingUnavailable

            raise DraftingUnavailable("unsupported_schema", "copilotstudio")
        self.require_evidence_access(pack.get("evidence", []))
        schema = strict_output_schema(output_schema)
        response_model = output_model(output_schema)
        model = self.model_for(model_tier)
        completion_limit = self.completion_limit(model, max_output_tokens)
        key = self.request_key(
            prompt_id,
            version,
            prompt,
            pack,
            schema,
            model,
            model_tier,
            completion_limit,
            output_schema,
        )
        cached = self.cache / f"{self.provider}-{key}.json"
        lock = self.root / "ledger.lock"
        with exclusive(lock):
            if key in self.preload_errors:
                raise self.preload_errors[key]
            if cached.exists():
                if key in self.preloaded_keys:
                    self.preloaded_keys.remove(key)
                else:
                    self.hits += 1
                if self.provider == "copilotstudio":
                    saved = json.loads(cached.read_text(encoding="utf-8"))
                    self.last_model = saved["model"]
                    self.last_usage_source = saved.get("usage_source", "reported")
                    return response_model.model_validate(saved["response"]).model_dump(mode="json")
                return response_model.model_validate_json(
                    cached.read_text(encoding="utf-8")
                ).model_dump(mode="json")
            # UTF-8 bytes bound input tokens conservatively; reserve all output tokens.
            input_tokens = len((prompt + canonical(pack) + canonical(schema)).encode()) + 512
            if self.provider == "copilotstudio":
                from dhf.llm.adapters.copilotstudio import request_payload

                request = request_payload(key, prompt_id, version, prompt, pack, schema)
                input_tokens = max(input_tokens, len(canonical(request).encode()) + 512)
                return self._generate_copilot(
                    prompt_id,
                    version,
                    prompt,
                    pack,
                    schema,
                    completion_limit,
                    key,
                    cached,
                    input_tokens,
                    response_model,
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
            ledger = (
                json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}
            )
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
            temp.write_text(canonical(ledger), encoding="utf-8", newline="\n")
            temp.replace(ledger_path)
            self.calls += 1
            # Failed calls retain the reservation: fail safe rather than overspend.
            raw = (
                self.adapter.complete(model, prompt, pack, completion_limit)
                if output_schema == "claims.v1"
                else self.adapter.complete(model, prompt, pack, completion_limit, schema=schema)
            )
            if not isinstance(raw, dict):
                from dhf.llm.errors import DraftingUnavailable

                raise DraftingUnavailable("invalid_schema", self.provider)
            usage = raw.pop("_usage", None)
            result = response_model.model_validate(raw)
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
                temp.write_text(canonical(ledger), encoding="utf-8", newline="\n")
                temp.replace(ledger_path)
            cached.write_text(result.model_dump_json(), encoding="utf-8", newline="\n")
            return result.model_dump(mode="json")

    def _generate_copilot(
        self,
        prompt_id: str,
        version: int,
        prompt: str,
        pack: dict,
        schema: dict,
        completion_limit: int,
        key: str,
        cached: Path,
        input_tokens: int,
        response_model: type,
    ) -> dict:
        """Reserve estimated credits, then settle attributed reported/estimated usage."""
        from dhf.llm.adapters.copilotstudio import request_payload

        rate = float(setting("DHF_COPILOT_CREDITS_PER_1K", "0.1"))
        run_cap = float(setting("DHF_COPILOT_CREDITS_PER_RUN", "250"))
        if rate < 0.1 or run_cap < 0:
            raise ValueError(
                "Copilot Basic credit rate must be at least 0.1 and run cap nonnegative"
            )
        reserve = (input_tokens + completion_limit) * rate / 1000
        path = self.root / "ledger.json"
        ledger = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        entry = ledger.get("copilotstudio", {})
        actual = entry.get("actual_credits", 0.0)
        outstanding = entry.get("reserved_credits", 0.0)
        if (
            self.run_spend + reserve > run_cap
            or actual + outstanding + reserve > self.copilot_cap()
        ):
            raise BudgetExceeded("Copilot credit cap reached")
        self.run_spend += reserve
        ledger["copilotstudio"] = {
            **entry,
            "actual_credits": actual,
            "reserved_credits": outstanding + reserve,
            "calls": entry.get("calls", 0) + 1,
        }
        temp = path.with_suffix(".tmp")
        temp.write_text(canonical(ledger), encoding="utf-8", newline="\n")
        temp.replace(path)
        self.calls += 1
        request = request_payload(key, prompt_id, version, prompt, pack, schema)
        raw = self.adapter.complete_request(request)
        usage = raw.pop("_usage", None)
        usage_source = raw.pop("_usage_source", "reported")
        reported_model = raw.pop("_model", None)
        if not isinstance(reported_model, str) or not reported_model:
            from dhf.llm.errors import DraftingUnavailable

            raise DraftingUnavailable("invalid_schema", "copilotstudio")
        result = response_model.model_validate(raw)
        if (
            usage_source not in ("reported", "estimated")
            or not isinstance(usage, dict)
            or any(
                not isinstance(usage.get(k), int) or isinstance(usage[k], bool) or usage[k] < 0
                for k in ("input_tokens", "output_tokens")
            )
        ):
            from dhf.llm.errors import DraftingUnavailable

            raise DraftingUnavailable("invalid_usage", "copilotstudio")
        self._settle_copilot(ledger["copilotstudio"], usage, usage_source, rate, reserve)
        temp.write_text(canonical(ledger), encoding="utf-8", newline="\n")
        temp.replace(path)
        self.last_model = reported_model
        self.last_usage_source = usage_source
        output = result.model_dump(mode="json")
        cached.write_text(
            canonical({"response": output, "model": reported_model, "usage_source": usage_source}),
            encoding="utf-8",
            newline="\n",
        )
        return output

    def _settle_copilot(
        self, entry: dict, usage: dict, source: str, rate: float, reserve: float
    ) -> None:
        """Keep cumulative estimates distinct from reported usage across both transports."""
        billed = (usage["input_tokens"] + usage["output_tokens"]) * rate / 1000
        # Legacy successful calls required reported token counts. Preserve that
        # provenance when extending an existing ledger, without rebilling them.
        if "credits_by_usage_source" not in entry:
            entry["credits_by_usage_source"] = {}
            if entry.get("input_tokens", 0) or entry.get("output_tokens", 0):
                entry["credits_by_usage_source"]["reported"] = entry["actual_credits"]
        by_source = entry["credits_by_usage_source"]
        by_source[source] = by_source.get(source, 0.0) + billed
        entry["usage_source"] = combine_usage_sources(list(by_source))
        entry["reserved_credits"] = max(0.0, entry["reserved_credits"] - reserve)
        entry["actual_credits"] += billed  # Legacy key: settled local credits, not tenant billing.
        entry["input_tokens"] = entry.get("input_tokens", 0) + usage["input_tokens"]
        entry["output_tokens"] = entry.get("output_tokens", 0) + usage["output_tokens"]
        self.run_spend += billed - reserve

    def preload_copilot_folder(self, doc: str, jobs: list[tuple]) -> None:
        """Exchange one document file, then populate the normal per-section cache."""
        from dhf.llm.adapters.copilotstudio import CopilotStudioAdapter
        from dhf.llm.errors import DraftingUnavailable

        if self.provider != "copilotstudio":
            raise ValueError("Folder preload requires copilotstudio")
        pending = {}
        for prompt_id, version, prompt, pack, visible_limit, tier in jobs:
            request = self.copilot_request(prompt_id, version, prompt, pack, visible_limit, tier)
            key = request["request_id"]
            cache = self.cache / f"copilotstudio-{key}.json"
            if not cache.exists():
                pending[key] = (request, visible_limit)
        if not pending:
            return
        rate = float(setting("DHF_COPILOT_CREDITS_PER_1K", "0.1"))
        run_cap = float(setting("DHF_COPILOT_CREDITS_PER_RUN", "250"))
        if rate < 0.1 or run_cap < 0:
            raise ValueError(
                "Copilot Basic credit rate must be at least 0.1 and run cap nonnegative"
            )
        reservations = {
            key: (len(canonical(request).encode()) + 512 + limit) * rate / 1000
            for key, (request, limit) in pending.items()
        }
        total = sum(reservations.values())
        lock = self.root / "ledger.lock"
        with exclusive(lock):
            path = self.root / "ledger.json"
            ledger = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            entry = ledger.get("copilotstudio", {})
            if (
                self.run_spend + total > run_cap
                or entry.get("actual_credits", 0) + entry.get("reserved_credits", 0) + total
                > self.copilot_cap()
            ):
                self.preload_errors.update(
                    {key: BudgetExceeded("Copilot credit cap reached") for key in pending}
                )
                return
            entry = {
                **entry,
                "actual_credits": entry.get("actual_credits", 0),
                "reserved_credits": entry.get("reserved_credits", 0) + total,
                "calls": entry.get("calls", 0) + len(pending),
            }
            ledger["copilotstudio"] = entry
            temp = path.with_suffix(".tmp")
            temp.write_text(canonical(ledger), encoding="utf-8", newline="\n")
            temp.replace(path)
            self.run_spend += total
            self.calls += len(pending)
            batch_id = hashlib.sha256(
                canonical({"doc": doc, "ids": sorted(pending)}).encode()
            ).hexdigest()
            envelope = {
                "request_id": batch_id,
                "document_id": doc,
                "sections": [value[0] for value in pending.values()],
            }
            try:
                raw = self.adapter.complete_batch(envelope)
            except DraftingUnavailable as exc:
                self.preload_errors.update({key: exc for key in pending})
                return
            replies = {
                row.get("request_id"): row
                for row in raw["sections"]
                if isinstance(row, dict) and isinstance(row.get("request_id"), str)
            }
            for key in pending:
                try:
                    parsed = CopilotStudioAdapter._parse(replies.get(key), key, pending[key][0])
                    usage = parsed.pop("_usage")
                    model = parsed.pop("_model")
                    usage_source = parsed.pop("_usage_source")
                    result = output_model("claims.v1").model_validate(parsed)
                except (DraftingUnavailable, ValueError, KeyError) as exc:
                    self.preload_errors[key] = (
                        exc
                        if isinstance(exc, DraftingUnavailable)
                        else DraftingUnavailable("invalid_schema", "copilotstudio")
                    )
                    continue
                self._settle_copilot(entry, usage, usage_source, rate, reservations[key])
                cache = self.cache / f"copilotstudio-{key}.json"
                cache.write_text(
                    canonical(
                        {
                            "model": model,
                            "response": result.model_dump(mode="json"),
                            "usage_source": usage_source,
                        }
                    ),
                    encoding="utf-8",
                    newline="\n",
                )
                self.preloaded_keys.add(key)
            temp.write_text(canonical(ledger), encoding="utf-8", newline="\n")
            temp.replace(path)
