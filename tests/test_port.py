from runpy import run_path

check_port = run_path("tools/check_port.py")["check_port"]


def test_port_covers_current_specs_and_exact_prompt_instructions():
    result = check_port()
    assert result["rules"] == 27
    assert result["tenant_parity"] == "pending"
