"""Stand-ins for the contact form's outside world (docs/kontaktskjema.md).

Everything here is simulated and local: a CAPTCHA verifier that answers like Turnstile/hCaptcha
siteverify, a sendmail replacement for PHP's mail(), a small SMTP server with optional
STARTTLS and AUTH LOGIN, and a webhotel-like layout (home/www + home/bootdisk-privat). All
addresses, keys and passwords are invented; none of them is a real Bootdisk setting.
"""
from __future__ import annotations

import base64
import contextlib
import email
import email.policy
import http.server
import json
import os
import shutil
import socket
import socketserver
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHP = shutil.which("php")
# Ports Stian and Birk use for live previews.
RESERVED_PORTS = {8772, 8794, 8795, 8796, 8797, 8798, 8803, 8812}

# Oppdiktede verdier. De brukes også til lekkasjekontrollen: ingen av dem skal finnes i Git
# eller i pakken, bortsett fra der testene selv skriver dem til midlertidige mapper.
FAKE_RECIPIENT = "mottaker.oppdiktet@kontakt-test.invalid"
FAKE_SENDER = "avsender.oppdiktet@kontakt-test.invalid"
FAKE_SITE_KEY = "oppdiktet-offentlig-nokkel-7f3a"
FAKE_SECRET = "oppdiktet-hemmelig-nokkel-91c2e"
FAKE_SALT = "oppdiktet-salt-0123456789abcdef0123456789abcdef"
FAKE_SMTP_USER = "smtp-bruker-oppdiktet"
FAKE_SMTP_PASSWORD = "smtp-passord-oppdiktet-55d1"
FAKE_VALUES = (FAKE_RECIPIENT, FAKE_SENDER, FAKE_SITE_KEY, FAKE_SECRET, FAKE_SALT, FAKE_SMTP_USER, FAKE_SMTP_PASSWORD)
# The site key is public by design: it is sent to browsers. Everything else stays on the server.
SERVER_ONLY_VALUES = tuple(value for value in FAKE_VALUES if value != FAKE_SITE_KEY)

TOKENS = {
    "ok-token": {"success": True, "hostname": "127.0.0.1"},
    "expired-token": {"success": False, "error-codes": ["timeout-or-duplicate"]},
    "seen-token": {"success": False, "error-codes": ["already-seen-response"]},
    "bad-token": {"success": False, "error-codes": ["invalid-input-response"]},
    "fault-token": {"success": False, "error-codes": ["invalid-input-secret"]},
    "wrong-host-token": {"success": True, "hostname": "elsewhere.invalid"},
}


def free_port() -> int:
    while True:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        if port not in RESERVED_PORTS:
            return port


def php_literal(value) -> str:
    if isinstance(value, dict):
        return "[" + ", ".join(f"{php_literal(k)} => {php_literal(v)}" for k, v in value.items()) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return "null"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


class Verifier:
    """Fake siteverify. Records every call; answers by token."""

    def __init__(self):
        self.calls: list[dict] = []
        self.down = False
        verifier = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                form = dict(urllib.parse.parse_qsl(self.rfile.read(length).decode()))
                verifier.calls.append(form)
                if verifier.down:
                    self.send_response(500)
                    self.end_headers()
                    return
                answer = TOKENS.get(form.get("response"), {"success": False, "error-codes": ["invalid-input-response"]})
                if form.get("secret") != FAKE_SECRET:
                    answer = {"success": False, "error-codes": ["invalid-input-secret"]}
                body = json.dumps(answer).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/siteverify"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


SENDMAIL = r'''
import os, sys, time
outbox = sys.argv[1]
data = sys.stdin.buffer.read()
if os.path.exists(os.path.join(outbox, "FAIL")):
    sys.exit(1)
name = os.path.join(outbox, f"{time.time_ns()}.eml")
with open(name + ".args", "w") as handle:
    handle.write("\n".join(sys.argv[2:]))
with open(name, "wb") as handle:
    handle.write(data)
'''


class Smtp:
    """Small SMTP server: EHLO, optional STARTTLS, AUTH LOGIN, MAIL, RCPT, DATA, QUIT."""

    def __init__(self, workdir: Path, *, tls: bool = False, refuse_rcpt: bool = False):
        self.refuse_rcpt = refuse_rcpt
        self.messages: list[dict] = []
        self.logins: list[tuple[str, str]] = []
        self.plain_commands: list[str] = []
        self.context = None
        self.cert = None
        if tls:
            self.cert = workdir / "smtp-cert.pem"
            key = workdir / "smtp-key.pem"
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=localhost",
                            "-addext", "subjectAltName=DNS:localhost", "-keyout", str(key), "-out", str(self.cert)],
                           check=True, capture_output=True)
            self.context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.context.load_cert_chain(self.cert, key)
        smtp = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                conn = self.connection
                reader = conn.makefile("rb")
                secure = False

                def say(line):
                    conn.sendall(line.encode() + b"\r\n")

                def read():
                    return reader.readline().decode().rstrip("\r\n")

                say("220 localhost ESMTP fake")
                envelope = {"from": None, "to": []}
                while True:
                    line = read()
                    if not line:
                        return
                    if not secure:
                        smtp.plain_commands.append(line)
                    verb = line.split(" ")[0].upper()
                    if verb == "EHLO":
                        extras = ["250-STARTTLS"] if smtp.context and not secure else []
                        for extra in extras + ["250-AUTH LOGIN"]:
                            say(extra)
                        say("250 OK")
                    elif verb == "STARTTLS" and smtp.context:
                        say("220 go ahead")
                        reader.close()
                        try:
                            conn = smtp.context.wrap_socket(conn, server_side=True)
                        except (ssl.SSLError, OSError):
                            return  # klienten stolte ikke på sertifikatet; det er forventet i én test
                        reader = conn.makefile("rb")
                        secure = True
                    elif verb == "AUTH":
                        say("334 VXNlcm5hbWU6")
                        user = base64.b64decode(read()).decode()
                        say("334 UGFzc3dvcmQ6")
                        password = base64.b64decode(read()).decode()
                        smtp.logins.append((user, password))
                        say("235 ok" if password == FAKE_SMTP_PASSWORD else "535 nope")
                    elif verb == "MAIL":
                        envelope = {"from": line.split(":", 1)[1].strip("<> "), "to": []}
                        say("250 OK")
                    elif verb == "RCPT":
                        if smtp.refuse_rcpt:
                            say("550 no such user")
                        else:
                            envelope["to"].append(line.split(":", 1)[1].strip("<> "))
                            say("250 OK")
                    elif verb == "DATA":
                        say("354 end with .")
                        lines = []
                        while (part := read()) != ".":
                            lines.append(part)
                        smtp.messages.append({**envelope, "data": "\r\n".join(lines).encode(), "secure": secure})
                        say("250 queued")
                    elif verb == "QUIT":
                        say("221 bye")
                        return
                    else:
                        say("502 unknown")

        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def base_config(state_dir: Path, verifier: Verifier, origin: str) -> dict:
    return {
        "recipient": FAKE_RECIPIENT,
        "sender": FAKE_SENDER,
        "sender_name": "Bootdisk kontaktskjema",
        "allowed_origin": origin,
        "state_dir": str(state_dir),
        "client_salt": FAKE_SALT,
        "rate_limit": {"window": 600, "per_client": 3, "per_day": 40},
        "captcha": {"provider": "turnstile", "site_key": FAKE_SITE_KEY, "secret": FAKE_SECRET, "verify_url": verifier.url},
        "transport": {"type": "mail"},
    }


class Webhotel:
    """home/www (document root) and home/bootdisk-privat (private config + state), served by php -S."""

    def __init__(self, workdir: Path, *, site_files=("api/kontakt.php",), port: int | None = None):
        self.home = workdir / "home"
        self.www = self.home / "www"
        self.private = self.home / "bootdisk-privat"
        self.state = self.private / "kontakt-tilstand"
        self.outbox = workdir / "outbox"
        for directory in (self.www, self.state, self.outbox):
            directory.mkdir(parents=True, exist_ok=True)
        for name in site_files:
            target = self.www / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        self.sendmail = workdir / "fake_sendmail.py"
        self.sendmail.write_text(SENDMAIL, encoding="utf-8")
        self.port = port or free_port()
        self.origin = f"http://127.0.0.1:{self.port}"
        self.url = self.origin
        self.process = None

    @property
    def config_file(self) -> Path:
        return self.private / "kontakt-config.php"

    def write_config(self, config: dict | None, path: Path | None = None) -> None:
        path = path or self.config_file
        if config is None:
            path.unlink(missing_ok=True)
            return
        path.write_text("<?php\nreturn " + php_literal(config) + ";\n", encoding="utf-8")

    def start(self, env: dict | None = None) -> str:
        command = [PHP, "-d", f"sendmail_path={sys.executable} {self.sendmail} {self.outbox}", "-d", "log_errors=1",
                   "-d", "display_errors=0", "-d", f"error_log={self.home / 'php-error.log'}",
                   "-S", f"127.0.0.1:{self.port}", "-t", str(self.www)]
        environment = {key: value for key, value in os.environ.items() if not key.startswith("BOOTDISK_CONTACT")}
        environment.update(env or {})
        self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=environment, cwd=self.www)
        for _ in range(100):
            with contextlib.suppress(OSError), socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                return self.url
            time.sleep(0.05)
        raise AssertionError("PHP-serveren startet ikke")

    def stop(self) -> None:
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=10)
            self.process = None

    def fail_sending(self, on: bool = True) -> None:
        flag = self.outbox / "FAIL"
        if on:
            flag.write_text("1")
        else:
            flag.unlink(missing_ok=True)

    def sent(self) -> list[dict]:
        mails = []
        for path in sorted(self.outbox.glob("*.eml")):
            message = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
            mails.append({"message": message, "args": Path(str(path) + ".args").read_text().split("\n"),
                          "raw": path.read_bytes()})
        return mails

    def error_log(self) -> str:
        path = self.home / "php-error.log"
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def call(url, method="GET", body=None, origin=None, headers=None, content_type="application/json"):
    data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", content_type)
    if origin:
        request.add_header("Origin", origin)
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
            return response.status, json.loads(raw or b"null"), dict(response.headers), raw
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            parsed = json.loads(raw or b"null")
        except json.JSONDecodeError:
            parsed = None
        return error.code, parsed, dict(error.headers), raw
