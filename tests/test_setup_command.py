import re

from cryptography.fernet import Fernet
from typer.testing import CliRunner

from dhf.cli import app
from dhf.config import load_env


def test_setup_creates_env_with_a_key_and_never_overwrites_one(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DHF_ENV_FILE", raising=False)
    (tmp_path / ".env.example").write_text(
        "# template\nAPP_ENCRYPTION_KEY=\nDHF_PROVIDER=mock\n", encoding="utf-8", newline="\n"
    )
    env = tmp_path / ".env"
    first = CliRunner().invoke(app, ["setup"])
    assert first.exit_code == 0, first.output
    text = env.read_text(encoding="utf-8")
    key = re.search(r"(?m)^APP_ENCRYPTION_KEY=(\S+)$", text)[1]
    Fernet(key.encode())  # a usable key
    assert key not in first.output and "DHF_PROVIDER=mock" in text
    again = CliRunner().invoke(app, ["setup"])
    assert again.exit_code == 0 and env.read_text(encoding="utf-8") == text
    env.write_text("APP_ENCRYPTION_KEY=not-a-key\n", encoding="utf-8", newline="\n")
    broken = CliRunner().invoke(app, ["setup"])
    assert broken.exit_code == 1
    assert env.read_text(encoding="utf-8") == "APP_ENCRYPTION_KEY=not-a-key\n"


def test_setup_outside_the_repository_explains_where_to_run(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DHF_ENV_FILE", raising=False)
    result = CliRunner().invoke(app, ["setup"])
    assert result.exit_code == 1 and not (tmp_path / ".env").exists()


def test_env_saved_with_a_byte_order_mark_still_loads(tmp_path) -> None:
    path = tmp_path / ".env"
    path.write_bytes(b"\xef\xbb\xbfAPP_ENCRYPTION_KEY=abc\r\nDHF_PROVIDER=mock\r\n")
    assert load_env(path) == {"APP_ENCRYPTION_KEY": "abc", "DHF_PROVIDER": "mock"}
