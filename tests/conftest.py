"""Test isolation: no developer credentials and no external sockets."""

import ipaddress
import os
import socket

import pytest

from dhf.config import load_env


class NetworkBlocked(OSError):
    pass


def is_loopback(host: object) -> bool:
    if isinstance(host, bytes):
        host = host.decode()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(str(host)).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def isolate_configuration_and_network(tmp_path, monkeypatch):
    empty = tmp_path / "empty.env"
    empty.write_text("")
    for name in list(os.environ):
        if name.startswith(("DHF_", "ADO_")) or name in (
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "APP_ADO_PAT",
            "SEED_ADO_PAT",
        ):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DHF_ENV_FILE", str(empty))
    load_env.cache_clear()
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_resolve = socket.getaddrinfo

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6) and not is_loopback(address[0]):
            raise NetworkBlocked("Tests prohibit non-loopback connections")
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6) and not is_loopback(address[0]):
            raise NetworkBlocked("Tests prohibit non-loopback connections")
        return original_connect_ex(sock, address)

    def resolve(host, *args, **kwargs):
        if not is_loopback(host):
            raise NetworkBlocked("Tests prohibit external DNS")
        return original_resolve(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    yield
    load_env.cache_clear()
