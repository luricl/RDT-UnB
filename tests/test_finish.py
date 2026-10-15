import socket
import threading
import unittest

from src.finish import FinishError, finish, md5_hex

CONTENT = b"abcd"
MD5 = "e2fc714c4727ee9395f324cd2e7f331f"


class FakeServer:
    """Imita o servidor real: o primeiro FIN encerra a sessão e recebe DONE;
    os seguintes recebem ERROR. `drop_fin`/`drop_done`: quantos FINs/DONEs
    perder. `ack_error`: manda o ERROR do último ACK antes do DONE."""

    def __init__(self, checksum=MD5, drop_fin=0, drop_done=0, ack_error=False,
                 session=True):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(1)
        self.addr = self.sock.getsockname()
        self.checksum = checksum
        self.drop_fin, self.drop_done = drop_fin, drop_done
        self.ack_error, self.session = ack_error, session
        self.fins = 0
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while True:
            try:
                data, client = self.sock.recvfrom(2048)
            except (socket.timeout, OSError):
                return
            self.fins += 1
            if self.fins <= self.drop_fin:
                continue
            if not self.session:
                self.sock.sendto(b"ERROR|msg=sessao_nao_iniciada", client)
                continue
            self.session = False
            if self.ack_error:
                self.sock.sendto(b"ERROR|msg=tipo_desconhecido_ACK", client)
            if self.drop_done > 0:
                self.drop_done -= 1
                continue
            ok = data == f"FIN|checksum={self.checksum}".encode()
            self.sock.sendto(
                f"DONE|ok={int(ok)}|expected={self.checksum}".encode(), client)

    def close(self):
        self.thread.join(timeout=3)
        self.sock.close()


class FinishTest(unittest.TestCase):
    def run_finish(self, server, content=CONTENT, max_retries=3):
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.bind(("127.0.0.1", 0))
        self.addCleanup(client.close)
        self.addCleanup(server.close)
        return finish(client, server.addr, content, server.checksum, 100,
                      max_retries)

    def test_md5(self):
        self.assertEqual(md5_hex(CONTENT), MD5)

    def test_done_ok(self):
        result = self.run_finish(FakeServer())
        self.assertEqual(result.md5, MD5)
        self.assertTrue(result.local_ok)
        self.assertTrue(result.server_ok)

    def test_corrupted_file(self):
        result = self.run_finish(FakeServer(), content=b"abce")
        self.assertFalse(result.local_ok)
        self.assertFalse(result.server_ok)

    def test_ignores_ack_error_before_done(self):
        result = self.run_finish(FakeServer(ack_error=True))
        self.assertTrue(result.server_ok)

    def test_retransmits_lost_fin(self):
        result = self.run_finish(FakeServer(drop_fin=2))
        self.assertTrue(result.server_ok)

    def test_lost_done_falls_back_to_local_check(self):
        result = self.run_finish(FakeServer(drop_done=1))
        self.assertIsNone(result.server_ok)
        self.assertTrue(result.local_ok)

    def test_no_session_is_an_error(self):
        with self.assertRaises(FinishError):
            self.run_finish(FakeServer(session=False))

    def test_gives_up_after_max_retries(self):
        with self.assertRaises(FinishError):
            self.run_finish(FakeServer(drop_fin=10), max_retries=2)


if __name__ == "__main__":
    unittest.main()
