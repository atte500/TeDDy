"""Confirm the IPv6-first loopback stall and locate the pytest-httpserver host option.

The turn-4 probe measured a ~2s connect to ``localhost`` and 0ms to
``127.0.0.1`` on the same server port, with ``getaddrinfo`` fast for both.
This probe prints the unsorted resolver order, times each resolved address
explicitly, inspects the installed plugin for a host option, and compares a
default server against one constructed with ``host="127.0.0.1"``.
"""

import inspect
import pathlib
import socket
import time
import urllib.request

import pytest_httpserver
from pytest_httpserver import HTTPServer


def timed(label: str, action) -> None:
    start = time.perf_counter()
    try:
        action()
    except OSError as error:
        print(f"{label}: ERROR {type(error).__name__}: {error}")
        return
    print(f"{label}: {(time.perf_counter() - start) * 1000:.0f} ms")


def inspect_package() -> None:
    package = pathlib.Path(pytest_httpserver.__file__).parent
    print(f"HTTPServer signature: {inspect.signature(HTTPServer)}")
    tokens = ("host", "addoption", "url_for", "getfqdn")
    for name in ("pytest_plugin.py", "httpserver.py"):
        print(f"=== {name} ===")
        text = (package / name).read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            if any(token in line.lower() for token in tokens):
                print(f"{number:4d}: {line}")


def measure_cycle(host: str) -> None:
    try:
        server = HTTPServer(host=host)
    except TypeError as error:
        print(f"HTTPServer(host={host!r}) rejected: {error}")
        return
    server.expect_request("/api/v1/models").respond_with_json({"data": []})
    server.start()
    try:
        url = server.url_for("/api/v1/models")
        infos = socket.getaddrinfo("localhost", server.port, type=socket.SOCK_STREAM)
        print(
            f"--- constructed host={host!r} server.host={server.host!r} "
            f"port={server.port} url={url}"
        )
        print(f"    raw resolver order: {[info[4][0] for info in infos]}")
        for address in ("::1", "127.0.0.1"):
            timed(
                f"    connect {address}",
                lambda a=address: socket.create_connection((a, server.port), timeout=5),
            )
        timed(
            "    request url_for",
            lambda: urllib.request.urlopen(url, timeout=10).read(),
        )
    finally:
        server.stop()


def main() -> None:
    inspect_package()
    print("")
    measure_cycle("localhost")
    print("")
    measure_cycle("127.0.0.1")


if __name__ == "__main__":
    main()