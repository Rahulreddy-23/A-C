from http.server import BaseHTTPRequestHandler

import pytest
from typer.testing import CliRunner

from dhf.cli import app
from dhf.serve import LocalServer, port_in_use


def listening() -> LocalServer:
    return LocalServer(("127.0.0.1", 0), BaseHTTPRequestHandler)


def test_a_second_server_cannot_share_a_busy_port() -> None:
    # On Windows, SO_REUSEADDR alone would let this bind succeed and steal the old traffic.
    first = listening()
    try:
        with pytest.raises(OSError) as raised:
            LocalServer(("127.0.0.1", first.server_address[1]), BaseHTTPRequestHandler)
        assert port_in_use(raised.value)
    finally:
        first.server_close()


def test_serve_explains_a_busy_port_and_still_starts_on_a_free_one(tmp_path, monkeypatch) -> None:
    args = ["serve", "--no-open-browser", "--output-dir", str(tmp_path), "--project-id", "p"]
    first = listening()
    port = first.server_address[1]
    try:
        busy = CliRunner().invoke(app, [*args, "--port", str(port)])
    finally:
        first.server_close()
    assert busy.exit_code == 1
    assert f"Port {port} is already in use" in busy.output

    def stop(self) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(LocalServer, "serve_forever", stop)
    free = CliRunner().invoke(app, [*args, "--port", "0"])
    assert free.exit_code == 0, free.output
    assert "Open this link in your browser (it works once): http://127.0.0.1:" in free.output
    assert "#access=" in free.output


def test_serve_prints_the_access_link_even_when_the_browser_opens(tmp_path, monkeypatch) -> None:
    # The page tells people to use the link in the dhf serve window, so it must be there.
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)

    def stop(self) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(LocalServer, "serve_forever", stop)
    args = ["serve", "--output-dir", str(tmp_path), "--project-id", "p", "--port", "0"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert opened and opened[0] in result.output and "#access=" in opened[0]
