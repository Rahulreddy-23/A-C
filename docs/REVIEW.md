# Review Log

Written by Claude (PM and reviewer). Codex reads this file at the start of every milestone.

**Item format:** `R-NNN [blocking|non-blocking] M<N> — finding (file:line) — expected fix`

**Codex:**
- Fix every `[blocking]` item before starting new work.
- Append `Resolved in <sha>: <note>` under each item you fix.
- Don't edit or delete the reviewer's text.
- If you disagree with an item, write your reasoning under it.

## Open

### M0 review (tag `m0-done`, 98aa27a) — verdict: **approved with fixes**

Verified independently:
- `uv run pytest` passes (5 tests); ruff check and format are clean; `dhf --help` works.
- GitHub Actions is green on `dev` and `m0-done`.
- `.env` and the PDF are not tracked.
- The acceptance criteria are met: schema-valid mock claims, and tests for cache hit/miss, ledger persistence, per-run cap and the 80% hard stop.

**R-001 [blocking] M0 — The cache key can collide and ignores prompt text** (`src/dhf/llm/__init__.py:76-78`)
- The key is `prompt_id + str(version) + model + canonical(pack)`, concatenated with no separators, so `("x", 12)` and `("x1", 2)` produce the same key.
- The prompt text isn't part of the key. Editing a prompt without bumping its version silently returns the stale cached answer, which breaks prompt iteration (the main job of the prompt lab).
- **Expected fix:** key = sha256 of `canonical({"prompt_id", "version", "prompt_sha256", "provider", "model", "pack"})`. Add tests for both cases.

Resolved in 9cbfcc0: canonical structured cache identity includes prompt hash, provider, model and evidence; collision and prompt-edit regression tests pass.

**R-002 [blocking] M0 — Tests read the developer's real `.env` and aren't blocked from the network** (`src/dhf/config.py:7-17`, `tests/`)
- `.env` now holds real Anthropic and OpenAI keys. `setting()` loads it into the test process, so local config can change test results.
- "Tests never call paid APIs" is enforced only by convention. A test that builds `LLM("anthropic")` without an adapter would spend real money.
- **Expected fix:**
  1. An autouse fixture in `tests/conftest.py` that points config at an empty env file (support `DHF_ENV_FILE`) and removes `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` from the environment.
  2. A socket guard that refuses non-loopback connections during tests. Loopback must stay allowed for the ADO mock.
  3. A test proving a real-provider call fails fast under the guard.
- Also load `.env` once (memoize) instead of on every `setting()` call.

Resolved in 9cbfcc0: DHF_ENV_FILE config is memoized; autouse fixtures remove credentials, isolate configuration and block external DNS/sockets while allowing loopback. Real OpenAI transport is proven blocked.

**R-003 [non-blocking, fix before M4 — required before any live Anthropic call] M0 — The Anthropic adapter will fail or overspend on real calls** (`src/dhf/llm/adapters/anthropic.py`, `.env.example:10,15-16`)
- **Wrong model and price.** `claude-haiku-4-5` costs $1 / $5 per MTok. The current Haiku is `claude-haiku-5-5` at $0.10 / $0.50 per MTok (prompts up to 100K), which is 10× cheaper on a $5 budget. Update `DHF_MODEL_ANTHROPIC` and both price variables.
- **`temperature=0` causes errors.** Haiku 5.5 returns a 400 for non-default sampling parameters. Remove `temperature`; determinism comes from the cache and the validator.
- **`response.content[0].text` breaks.** Haiku 5.5 uses adaptive thinking by default, so the first content block can be a `thinking` block. Find the text block by `type`.
- **JSON isn't enforced.** Use structured outputs: `output_config={"format": {"type": "json_schema", "schema": <claims.v1>}, "effort": "low"}`, or `client.messages.parse(..., output_format=Claims)`.
- **Response handling.** Check `stop_reason` for `max_tokens` and `refusal` before parsing. Thinking counts toward `max_tokens`, so 1000 is too tight; start at about 4000.
- **Prompt layout.** Put the prompt in `system` and the evidence pack in the user message, so the prefix stays stable for caching.
- **Record real usage.** Return `usage.input_tokens` / `usage.output_tokens` to the ledger (see R-005).
- **Pin the SDK.** Pin `anthropic>=1.0`; the lock already resolves 1.13.0 and the code should target 1.x.

**R-004 [non-blocking, fix before M4] M0 — The OpenAI adapter doesn't enforce the claims schema** (`src/dhf/llm/adapters/openai.py`)
- `response_format={"type": "json_object"}` only guarantees *some* JSON. JSON mode is also rejected unless the messages contain the word "JSON".
- **Expected fix:**
  - Use strict JSON-schema structured output with `claims.v1`. Strict mode needs every property listed in `required`, so make `confidence` `["number", "null"]` and keep the pydantic model as the validator.
  - Prefer `max_completion_tokens`.
  - Record real usage.
  - Check the exact parameter names against the locked SDK (openai 3.29.0).
- This adapter matters most for Copilot Studio parity, because Copilot Studio runs OpenAI-family models.

**R-005 [non-blocking, fix before M4] M0 — The ledger records reservations only, never actual spend** (`src/dhf/llm/__init__.py:86-111`)
- The reservation counts UTF-8 bytes as tokens (about 3–4× real input) plus the full `max_output_tokens`. So the $1.50 build cap allows only about a third of the real calls it should.
- **Expected fix:** keep the reservation as written. After a successful call, replace it with the actual cost from provider usage; on failure, keep the reservation. Store both `reserved_usd` and `actual_usd` per provider, and show actual spend in PROGRESS.md.

**R-006 [non-blocking] M0 — An empty evidence pack blocks every real-provider call** (`src/dhf/llm/__init__.py:71-75`)
- `not pack.get("evidence")` raises for sections with no evidence, such as "Purpose & scope". An empty pack can't leak anything.
- **Expected fix:** reject only if *any* evidence item is non-synthetic, and allow an empty list.

**R-007 [non-blocking] M0 — PROGRESS.md is stale** (`docs/PROGRESS.md`)
- The status line still says "M0 (in progress)" after `m0-done`.
- The Milestones table is empty.
- The M0 evidence sits after "LLM spend" instead of under "Acceptance evidence".
- "GitHub Actions result — pending first push" is out of date: runs 38280581197 and 38280582320 passed.
- **Expected fix:** update the status line, the table and the evidence placement at every tag. The reviewer's monitor watches the status line.

Resolved in 9cbfcc0 (R-007 status maintenance): PROGRESS now records M0 done, its tag/commit, verified CI runs and evidence in the Acceptance evidence section.

## Resolved

_None yet._
