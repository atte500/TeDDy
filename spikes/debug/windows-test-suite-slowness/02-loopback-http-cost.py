"""Isolate the fixed cost of one loopback HTTP request under pytest-httpserver.

Each openrouter test costs about 2.0s while the cache-hit tests that start the
same server without issuing a request cost 0.01s, so the cost lives in the
request. This probe measures name resolution, proxy resolution, raw connect,
and full request time against the same pytest-httpserver instance, plus a plain
http.server control to separate the library from the operating-system stack.
"""

import os
import socket
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import requests
from pytest_httpserver import HTTPServer

REPEAT = 3


def probe(label: str, action, repeat: int = REPEAT) -> None:
    durations: list[float] = []
    for _ in range(repeat):
        start = time.perf_counter()
        try:
            action()
        except OSError as error:
            print(f"{label}: ERROR {type(error).__name__}: {error}")
            return
        durations.append(time.perf_counter() - start)
    fastest = min(durations) * 1000
    slowest = max(durations) * 1000
    print(f"{label}: min {fastest:.0f} ms, max {slowest:.0f} ms over {repeat}")


class TinyHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b'{"data": []}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


def run_pytest_httpserver_cycle() -> None:
    start = time.perf_counter()
    server = HTTPServer()
    server.expect_request("/api/v1/models").respond_with_json({"data": []})
    server.start()
    started = time.perf_counter() - start
    print(f"httpserver start: {started * 1000:.0f} ms (host={server.host!r} port={server.port})")
    try:
        url = server.url_for("/api/v1/models")
        port = urlsplit(url).port
        loopback = f"http://127.0.0.1:{port}/api/v1/models"
        addresses = sorted(
            {
                info[4][0]
                for info in socket.getaddrinfo(
                    "localhost", port, type=socket.SOCK_STREAM
                )
            }
        )
        print(f"getaddrinfo localhost -> {addresses}")

        probe(
            "getaddrinfo localhost",
            lambda: socket.getaddrinfo("localhost", port, type=socket.SOCK_STREAM),
            repeat=5,
        )
        probe(
            "getaddrinfo 127.0.0.1",
            lambda: socket.getaddrinfo("127.0.0.1", port, type=socket.SOCK_STREAM),
            repeat=5,
        )

        def connect(host: str) -> None:
            with socket.create_connection((host, port), timeout=10):
                pass

        probe("connect localhost", lambda: connect("localhost"))
        probe("connect 127.0.0.1", lambda: connect("127.0.0.1"))
        probe("urllib localhost", lambda: urllib.request.urlopen(url, timeout=10).read())
        probe(
            "urllib 127.0.0.1",
            lambda: urllib.request.urlopen(loopback, timeout=10).read(),
        )
        probe("requests localhost", lambda: requests.get(url, timeout=10))
        probe("requests 127.0.0.1", lambda: requests.get(loopback, timeout=10))
        probe(
            "requests localhost trust_env=False",
            lambda: requests.get(url, timeout=10, trust_env=False),
        )
        probe("getproxies", urllib.request.getproxies)
        print(f"proxy scheme keys: {sorted(urllib.request.getproxies())}")
        print(f"NO_PROXY set: {'NO_PROXY' in os.environ}")
        print(f"no_proxy set: {'no_proxy' in os.environ}")
        print(f"proxy_bypass localhost: {urllib.request.proxy_bypass('localhost')}")
        probe("getfqdn 127.0.0.1", lambda: socket.getfqdn("127.0.0.1"))
    finally:
        server.stop()


def run_control_server_cycle() -> None:
    start = time.perf_counter()
    tiny = ThreadingHTTPServer(("127.0.0.1", 0), TinyHandler)
    built = time.perf_counter() - start
    threading.Thread(target=tiny.serve_forever, daemon=True).start()
    tiny_port = tiny.server_address[1]
    print(f"control http.server build: {built * 1000:.0f} ms (port={tiny_port})")
    try:
        probe(
            "control requests 127.0.0.1",
            lambda: requests.get(f"http://127.0.0.1:{tiny_port}/", timeout=10),
            repeat=2,
        )
        probe(
            "control requests localhost",
            lambda: requests.get(f"http://localhost:{tiny_port}/", timeout=10),
            repeat=2,
        )
    finally:
        tiny.shutdown()


def main() -> None:
    run_pytest_httpserver_cycle()
    print("")
    run_control_server_cycle()


if __name__ == "__main__":
    main()