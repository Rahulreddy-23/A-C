# A-C
## DHF Automation — How to run

Python 3.12 and uv are required (`out/bin/uv` is the local workstation install).

```sh
uv sync
uv run dhf --help
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Configuration comes from the ignored `.env`. Copy `.env.example` on a fresh clone.
Tests use mock LLM responses and never call paid APIs. Provider model names and
prices are configurable; verify current pricing before enabling live calls.
Budget accounting reserves a conservative upper-bound cost before each request,
including failed requests. Cache hits are free. Paid calls require synthetic evidence.
