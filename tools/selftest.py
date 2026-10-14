#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ocgo-bridge offline self-test.

Spins up a local mock upstream, starts proxy.py against it, and asserts the
behaviour that matters. Needs no internet and no API key, so a failure here
means the package or the Python environment is broken -- not the network and
not your OpenCode account.

    python tools/selftest.py

Exit code 0 = all checks passed, 1 = something failed.
"""

import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROXY = os.path.join(ROOT, "proxy.py")
MOCK_PORT = 8899
PROXY_PORT = 8790
KEY = "selftest-key"
VALID_IDS = {
    "deepseek-v4.1-flash", "deepseek-v4-flash", "deepseek-v4-pro",
    "deepseek-flash", "mimo-v2.6-flash", "glm-5.3-flash", "kimi-k3",
}

seen = []


# ----------------------------------------------------------------- mock ----
class MockUpstream(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        body = b'{"object":"list","data":[]}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = {}
        seen.append({
            "path": self.path,
            "auth": self.headers.get("Authorization"),
            "apikey": self.headers.get("x-api-key"),
            "session": self.headers.get("x-opencode-session"),
            "ua": self.headers.get("User-Agent"),
            "model": payload.get("model"),
            "stream": bool(payload.get("stream")),
        })
        if payload.get("stream"):
            body = (b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
                    b"data: [DONE]\n\n")
            ctype = "text/event-stream"
        else:
            body = json.dumps({"id": "x", "object": "chat.completion",
                               "choices": [{"message": {"role": "assistant",
                                                        "content": "ok"}}]}).encode()
            ctype = "application/json"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def wait_port(port, timeout=15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = socket.socket()
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            time.sleep(0.3)
        finally:
            s.close()
    return False


def post(path, payload, headers):
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (PROXY_PORT, path),
        data=json.dumps(payload).encode("utf-8"),
        headers=dict({"Content-Type": "application/json"}, **headers),
        method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=25)
        return r.status, len(r.read())
    except urllib.error.HTTPError as e:
        return e.code, len(e.read())
    except Exception as e:                                  # noqa: BLE001
        return 0, repr(e)


def main():
    if not os.path.isfile(PROXY):
        print("  [fail] proxy.py not found at %s" % PROXY)
        return 1

    mock = ThreadingHTTPServer(("127.0.0.1", MOCK_PORT), MockUpstream)
    threading.Thread(target=mock.serve_forever, daemon=True).start()

    env = dict(os.environ)
    env["OPENCODE_GO_UPSTREAM"] = "http://127.0.0.1:%d/v1" % MOCK_PORT
    env["OPENCODE_GO_KEY"] = KEY
    # Make sure the test does not accidentally inherit a user config.json
    env["OPENCODE_GO_MODEL"] = "deepseek-v4.1-flash"
    # Keep test traffic out of the package's proxy.log. The log is the first
    # place anyone looks when diagnosing, so it must not contain mock requests
    # interleaved with a live proxy's.
    env["OPENCODE_GO_LOG"] = os.path.join(tempfile.gettempdir(),
                                          "ocgo-selftest.log")

    proc = subprocess.Popen(
        [sys.executable, PROXY, "--port", str(PROXY_PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd=ROOT)

    try:
        if not wait_port(PROXY_PORT):
            print("  [fail] proxy did not start on port %d" % PROXY_PORT)
            return 1
        print("  proxy up on 127.0.0.1:%d (mock upstream on %d)"
              % (PROXY_PORT, MOCK_PORT))

        # --- four protocol / streaming combinations -------------------------
        body = {"model": "opencode-go-deepseek-v4.1-flash",
                "messages": [{"role": "user", "content": "hi"}]}
        cases = [
            ("openai   non-stream", "/v1/chat/completions",
             dict(body, stream=False), {"Authorization": "Bearer " + KEY}),
            ("openai   stream    ", "/v1/chat/completions",
             dict(body, stream=True), {"Authorization": "Bearer " + KEY}),
            ("anthropic non-stream", "/v1/messages",
             dict(body, max_tokens=16), {"x-api-key": KEY,
                                         "anthropic-version": "2023-06-01"}),
            ("anthropic stream    ", "/v1/messages",
             dict(body, max_tokens=16, stream=True),
             {"x-api-key": KEY, "anthropic-version": "2023-06-01"}),
        ]
        http_ok = True
        for name, path, payload, hdr in cases:
            code, size = post(path, payload, hdr)
            if code != 200:
                http_ok = False
            print("  %s %s -> HTTP %s (%s bytes)"
                  % ("[ok]  " if code == 200 else "[fail]", name, code, size))

        # --- id normalisation fallback --------------------------------------
        post("/v1/chat/completions",
             {"model": "DeepSeek-V4.1-Flash",
              "messages": [{"role": "user", "content": "hi"}]},
             {"Authorization": "Bearer " + KEY})

        # --- multi-turn session stability -----------------------------------
        post("/v1/chat/completions",
             {"model": "deepseek-v4.1-flash",
              "messages": [{"role": "user", "content": "stable-seed"}]},
             {"Authorization": "Bearer " + KEY})
        post("/v1/chat/completions",
             {"model": "deepseek-v4.1-flash",
              "messages": [{"role": "user", "content": "stable-seed"},
                           {"role": "assistant", "content": "y"},
                           {"role": "user", "content": "more"}]},
             {"Authorization": "Bearer " + KEY})

        checks = [
            ("every request carries x-opencode-session",
             all(r["session"] for r in seen)),
            ("/messages authenticates with x-api-key, never Bearer",
             all(r["apikey"] == KEY and r["auth"] is None
                 for r in seen if r["path"].endswith("/messages"))),
            ("/chat/completions authenticates with Bearer, never x-api-key",
             all(r["auth"] == "Bearer " + KEY and r["apikey"] is None
                 for r in seen if r["path"].endswith("/chat/completions"))),
            ("model ids normalised to valid lowercase ids",
             all(r["model"] in VALID_IDS for r in seen)),
            ("session id stable across turns of one conversation",
             seen[-1]["session"] == seen[-2]["session"]),
        ]

        print("")
        all_ok = http_ok
        for name, ok in checks:
            if not ok:
                all_ok = False
            print("  %s %s" % ("[ok]  " if ok else "[fail]", name))

        print("")
        print("  RESULT: %s" % ("PASS" if all_ok else "FAIL"))
        return 0 if all_ok else 1
    finally:
        proc.terminate()
        mock.shutdown()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
