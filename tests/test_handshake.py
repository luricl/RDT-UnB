import socket
import threading
import unittest

from src.handshake import HandshakeError, handshake

OK_PACKET = (b"OK|file_size=1048576|checksum=f5adc7ebd10d3997cfa18c8a73a7f9a5"
             b"|seed=rdtunb_teste_2026_10|total_segments=1024|segment_size=1024")


class FakeServer:
    """Servidor UDP em localhost que executa um roteiro de respostas.

    `script` tem uma entrada por HELLO recebido: bytes a responder, ou None
    para fingir perda (não responde).
    """

    def __init__(self, script):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(2)
        self.addr = self.sock.getsockname()
        self.received = []
        self.script = list(script)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        for reply in self.script:
            try:
                data, client = self.sock.recvfrom(2048)
            except socket.timeout:
                return
            self.received.append(data)
            if reply is not None:
                self.sock.sendto(reply, client)

    def close(self):
        self.thread.join(timeout=3)
        self.sock.close()


class HandshakeTest(unittest.TestCase):
    def setUp(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client.bind(("127.0.0.1", 0))
        self.addCleanup(self.client.close)

    def run_handshake(self, server, max_attempts=3):
        self.addCleanup(server.close)
        return handshake(self.client, server.addr, "grupo07", "small", 512,
                         timeout_ms=100, max_attempts=max_attempts)

    def test_returns_negotiated_values(self):
        server = FakeServer([OK_PACKET])
        ok = self.run_handshake(server)
        self.assertEqual(server.received,
                         [b"HELLO|grupo=grupo07|segment_size=512|file=small"])
        self.assertEqual(ok.segment_size, 1024)  # difere do solicitado (512)
        self.assertEqual(ok.total_segments, 1024)
        self.assertEqual(ok.file_size, 1048576)

    def test_retransmits_hello_after_loss(self):
        server = FakeServer([None, None, OK_PACKET])
        ok = self.run_handshake(server)
        self.assertEqual(len(server.received), 3)
        self.assertEqual(ok.segment_size, 1024)

    def test_fails_after_max_attempts(self):
        server = FakeServer([None, None, None])
        with self.assertRaises(HandshakeError):
            self.run_handshake(server)
        self.assertEqual(len(server.received), 3)

    def test_ignores_error_and_garbage_until_ok(self):
        # Um único HELLO; o servidor manda lixo e ERROR antes do OK.
        server = FakeServer([None])
        self.addCleanup(server.close)

        # Respostas extras enviadas manualmente após o HELLO chegar.
        def extra():
            server.thread.join(timeout=2)
            client_addr = self.client.getsockname()
            for pkt in (b"ERROR|msg=algo", b"lixo", OK_PACKET):
                server.sock.sendto(pkt, client_addr)
        threading.Thread(target=extra, daemon=True).start()
        ok = handshake(self.client, server.addr, "grupo07", "small", 512,
                       timeout_ms=1000, max_attempts=1)
        self.assertEqual(ok.segment_size, 1024)


if __name__ == "__main__":
    unittest.main()
