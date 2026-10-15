import contextlib
import io
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

from src.cli import DEFAULT_GBN_SR_WINDOW, parse_args

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = ["--server", "137.131.178.229", "--group", "grupo07"]


def parse_fails(argv):
    """Retorna (status, stderr) de um parse_args que deve encerrar."""
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        with unittest.TestCase().assertRaises(SystemExit) as ctx:
            parse_args(argv)
    return ctx.exception.code, stderr.getvalue()


class ParseArgsTest(unittest.TestCase):
    def test_defaults(self):
        config = parse_args(BASE)
        self.assertEqual(config.server, "137.131.178.229")
        self.assertEqual(config.port, 8080)
        self.assertEqual(config.group, "grupo07")
        self.assertEqual(config.file, "small")
        self.assertEqual(config.protocol, "saw")
        self.assertEqual(config.window, 1)
        self.assertEqual(config.segment_size, 512)
        self.assertEqual(config.loss, 0.0)

    def test_all_options(self):
        config = parse_args(BASE + [
            "--file", "large", "--protocol", "sr", "--window", "16",
            "--segment-size", "1024", "--loss", "0.1", "--timeout", "250",
        ])
        self.assertEqual(config.file, "large")
        self.assertEqual(config.protocol, "sr")
        self.assertEqual(config.window, 16)
        self.assertEqual(config.segment_size, 1024)
        self.assertEqual(config.loss, 0.1)
        self.assertEqual(config.timeout_ms, 250.0)

    def test_missing_group_is_refused(self):
        status, err = parse_fails(["--server", "137.131.178.229"])
        self.assertEqual(status, 2)
        self.assertIn("--group é obrigatório", err)

    def test_blank_group_is_refused(self):
        status, err = parse_fails(["--server", "x", "--group", "  "])
        self.assertEqual(status, 2)
        self.assertIn("--group é obrigatório", err)

    def test_group_with_protocol_separator_is_refused(self):
        status, _ = parse_fails(["--server", "x", "--group", "a|b"])
        self.assertEqual(status, 2)

    def test_gbn_sr_default_window(self):
        for protocol in ("gbn", "sr"):
            config = parse_args(BASE + ["--protocol", protocol])
            self.assertEqual(config.window, DEFAULT_GBN_SR_WINDOW)

    def test_saw_rejects_window_other_than_one(self):
        status, _ = parse_fails(BASE + ["--window", "4"])
        self.assertEqual(status, 2)

    def test_invalid_values_are_refused(self):
        for extra in (
            ["--file", "huge"],
            ["--protocol", "tcp"],
            ["--protocol", "gbn", "--window", "0"],
            ["--segment-size", "0"],
            ["--segment-size", "70000"],
            ["--loss", "1.5"],
            ["--loss", "-0.1"],
            ["--timeout", "0"],
            ["--port", "70000"],
        ):
            with self.subTest(extra=extra):
                status, _ = parse_fails(BASE + extra)
                self.assertEqual(status, 2)


class FakeServer:
    """Servidor UDP em localhost que serve um arquivo de um único segmento."""

    REPLIES = {
        b"HELLO": b"OK|file_size=4|checksum=e2fc714c4727ee9395f324cd2e7f331f"
                  b"|seed=s|total_segments=1|segment_size=4",
        b"REQ": b"DATA|seq=0|total=4|abcd",
        b"FIN": b"DONE|ok=1",
    }

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(5)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            try:
                data, client = self.sock.recvfrom(2048)
            except OSError:
                return
            kind = data.split(b"|", 1)[0]
            self.sock.sendto(self.REPLIES.get(kind, b"ERROR|msg=x"), client)


class EntryPointTest(unittest.TestCase):
    def run_cliente(self, *args):
        # Roda em diretório temporário para não sobrescrever data/ do repositório.
        with tempfile.TemporaryDirectory() as cwd:
            return subprocess.run(
                [sys.executable, os.path.join(ROOT, "cliente.py"), *args],
                cwd=cwd, capture_output=True, text=True, timeout=30,
            )

    def test_starts_with_group(self):
        server = FakeServer()
        self.addCleanup(server.sock.close)
        result = self.run_cliente(
            "--server", "127.0.0.1", "--port", str(server.port),
            "--group", "grupo07", "--file", "small")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("grupo=grupo07", result.stdout)
        self.assertIn("DONE ok=1", result.stdout)

    def test_exits_with_error_without_group(self):
        result = self.run_cliente("--server", "137.131.178.229", "--file", "small")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--group é obrigatório", result.stderr)


if __name__ == "__main__":
    unittest.main()
