"""Windows portability: text I/O never depends on the platform's defaults.

Windows reads and writes text as cp1252 with CRLF line endings unless told otherwise, so
reports, docs-repo commits and git hook scripts would differ by operating system."""

import ast
from pathlib import Path


def text_mode(call: ast.Call) -> str | None:
    """'r' or 'w' for a text-mode read_text/write_text/open call or a text subprocess call."""
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    keywords = {k.arg: k.value for k in call.keywords}
    if name in ("read_text", "write_text"):
        return name[0]
    if name in ("run", "check_output", "Popen"):
        text = keywords.get("text") or keywords.get("universal_newlines")
        return "r" if isinstance(text, ast.Constant) and text.value else None
    if name != "open" or getattr(getattr(func, "value", None), "id", "") in ("webbrowser", "os"):
        return None
    args = call.args[1:] if isinstance(func, ast.Name) else call.args
    given = keywords.get("mode", args[0] if args else None)
    mode = given.value if isinstance(given, ast.Constant) and isinstance(given.value, str) else "r"
    return None if "b" in mode else "w" if set(mode) & set("wax") else "r"


def test_text_io_is_utf8_with_lf_line_endings() -> None:
    offenders = []
    for path in sorted(p for root in ("src", "tools", "tests") for p in Path(root).rglob("*.py")):
        for call in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(call, ast.Call) or not (mode := text_mode(call)):
                continue
            keywords = {k.arg for k in call.keywords}
            if "encoding" not in keywords or (mode == "w" and "newline" not in keywords):
                offenders.append(f"{path}:{call.lineno}")
    assert not offenders, "pass encoding='utf-8' (and newline='\\n' on writes): " + str(offenders)
