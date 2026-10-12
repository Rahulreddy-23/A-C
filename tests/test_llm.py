import json
from pathlib import Path

import pytest

from dhf.llm import LLM, BudgetExceeded
from dhf.models import Claims

PACK = {
    "facts": {},
    "evidence": [
        {"id": "SRS-001", "body": "Deliver configured flow.", "attributes": {"synthetic": True}}
    ],
}


def test_mock_cache_and_schema(tmp_path: Path) -> None:
    llm = LLM(root=tmp_path)
    Claims.model_validate(llm.generate("test", 1, "Return claims.", PACK))
    llm.generate("test", 1, "Return claims.", PACK)
    assert (llm.calls, llm.hits) == (1, 1)
    llm.generate("test", 2, "Return claims.", PACK)
    assert llm.calls == 2
    assert LLM(root=tmp_path).generate("test", 1, "Return claims.", PACK)


def test_caps_persistence_and_failed_reservation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DHF_OPENAI_INPUT_PER_MILLION", "1000")
    monkeypatch.setenv("DHF_OPENAI_OUTPUT_PER_MILLION", "1000")
    from dhf.llm.adapters.mock import MockAdapter

    llm = LLM("openai", tmp_path, MockAdapter(), run_cap=0.001)
    with pytest.raises(BudgetExceeded):
        llm.generate("t", 1, "p", PACK)
    llm = LLM("openai", tmp_path, MockAdapter(), run_cap=5, build_cap=5, total_cap=2)
    llm.generate("t", 1, "p", PACK)
    assert json.loads((tmp_path / "ledger.json").read_text())["openai"]["reserved_usd"] > 1
    with pytest.raises(BudgetExceeded):
        LLM("openai", tmp_path, MockAdapter(), run_cap=5, build_cap=5, total_cap=2).generate(
            "t", 2, "p", PACK
        )


def test_non_synthetic_never_sent(tmp_path: Path) -> None:
    from dhf.llm.adapters.mock import MockAdapter

    with pytest.raises(ValueError, match="synthetic"):
        LLM("openai", tmp_path, MockAdapter()).generate("t", 1, "p", {"evidence": [{"id": "REAL"}]})


def test_build_cap_and_cumulative_run_cap(tmp_path: Path, monkeypatch) -> None:
    from dhf.llm.adapters.mock import MockAdapter

    monkeypatch.setenv("DHF_OPENAI_INPUT_PER_MILLION", "1000")
    monkeypatch.setenv("DHF_OPENAI_OUTPUT_PER_MILLION", "1000")
    with pytest.raises(BudgetExceeded):
        LLM("openai", tmp_path, MockAdapter(), run_cap=5, build_cap=0.5).generate("x", 1, "p", PACK)
    llm = LLM("openai", tmp_path, MockAdapter(), run_cap=1.5, build_cap=5)
    llm.generate("x", 1, "p", PACK)
    with pytest.raises(BudgetExceeded):
        llm.generate("x", 2, "p", PACK)


def test_schema_file_matches_contract() -> None:
    assert (
        json.loads(Path("specs/schemas/claims.v1.json").read_text()) == Claims.model_json_schema()
    )
