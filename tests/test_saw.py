import socket
import threading
import unittest

from src.saw import DownloadError, download

SEGMENTS = [b"aaaa|bb", b"cccc", b"dd"]


def data_packet(seq, payload):
    return f"DATA|seq={seq}|total={len(payload)}|".encode() + payload


class FakeServer:
    """Responde REQ com DATA. `drop` = {(seq, n)}: ignora o n-ésimo REQ do seq.
    `dup` = seqs cujo DATA é enviado duas vezes, mais um DATA antigo antes."""

    def __init__(self, drop=(), dup=()):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(1)
        self.addr = self.sock.getsockname()
        self.drop, self.dup = set(drop), set(dup)
        self.req_count = {}
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while True:
            try:
                data, client = self.sock.recvfrom(2048)
            except (socket.timeout, OSError):
                return
            if not data.startswith(b"REQ|seq="):
                self.sock.sendto(b"ERROR|msg=tipo_desconhecido_ACK", client)
                continue
            seq = int(data.split(b"=")[1])
            n = self.req_count[seq] = self.req_count.get(seq, 0) + 1
            if (seq, n) in self.drop:
                continue
            if seq in self.dup and seq > 0:
                self.sock.sendto(data_packet(seq - 1, SEGMENTS[seq - 1]), client)
            pkt = data_packet(seq, SEGMENTS[seq])
            self.sock.sendto(pkt, client)
            if seq in self.dup:
                self.sock.sendto(pkt, client)

    def close(self):
        self.thread.join(timeout=3)
        self.sock.close()


class SawTest(unittest.TestCase):
    def run_download(self, server, max_retries=3):
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.bind(("127.0.0.1", 0))
        self.addCleanup(client.close)
        self.addCleanup(server.close)
        return download(client, server.addr, len(SEGMENTS), 100, max_retries)

    def test_downloads_all_segments(self):
        result = self.run_download(FakeServer())
        self.assertEqual(result.content, b"".join(SEGMENTS))
        self.assertEqual(result.retransmissions, 0)
        self.assertEqual([s.seq for s in result.segments], [0, 1, 2])
        self.assertEqual([s.size_bytes for s in result.segments],
                         [len(p) for p in SEGMENTS])

    def test_segment_stats_after_retransmission(self):
        result = self.run_download(FakeServer(drop={(1, 1), (1, 2)}))
        self.assertEqual([s.retransmissions for s in result.segments], [0, 2, 0])
        self.assertEqual([s.timeout_occurred for s in result.segments],
                         [False, True, False])
        # RTT conta a partir do último REQ, não inclui os 2 timeouts de 100 ms.
        self.assertLess(result.segments[1].rtt_ms, 100)

    def test_retransmits_lost_req(self):
        result = self.run_download(FakeServer(drop={(1, 1), (1, 2)}))
        self.assertEqual(result.content, b"".join(SEGMENTS))
        self.assertEqual(result.retransmissions, 2)

    def test_discards_duplicates_and_old_data(self):
        result = self.run_download(FakeServer(dup={1, 2}))
        self.assertEqual(result.content, b"".join(SEGMENTS))

    def test_gives_up_after_max_retries(self):
        server = FakeServer(drop={(0, n) for n in range(1, 10)})
        with self.assertRaises(DownloadError):
            self.run_download(server, max_retries=2)


if __name__ == "__main__":
    unittest.main()
