import socket
import threading
import unittest

from src.saw import DownloadError
from src.sr import download

SEGMENTS = [b"aaaa|bb", b"cccc", b"dd", b"e|e", b"ffff"]


def data_packet(seq, payload):
    return f"DATA|seq={seq}|total={len(payload)}|".encode() + payload


class FakeServer:
    """Responde REQ com DATA e registra a ordem dos REQs recebidos.

    `drop` = {(seq, n)}: ignora o n-ésimo REQ do seq.
    `delay` = seqs cujo DATA só é enviado depois do DATA do próximo REQ, para
    chegar fora de ordem. `dup` = seqs cujo DATA é enviado duas vezes.
    """

    def __init__(self, drop=(), delay=(), dup=()):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(1)
        self.addr = self.sock.getsockname()
        self.drop, self.delay, self.dup = set(drop), set(delay), set(dup)
        self.reqs = []
        self.held = []
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
            self.reqs.append(seq)
            if (seq, self.reqs.count(seq)) in self.drop:
                continue
            pkt = data_packet(seq, SEGMENTS[seq])
            if seq in self.delay and not self.held:
                self.held.append(pkt)
                continue
            self.sock.sendto(pkt, client)
            if seq in self.dup:
                self.sock.sendto(pkt, client)
            for held in self.held:
                self.sock.sendto(held, client)
            self.held.clear()

    def close(self):
        self.thread.join(timeout=3)
        self.sock.close()


class SrTest(unittest.TestCase):
    def run_download(self, server, window=3, max_retries=3, **kwargs):
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.bind(("127.0.0.1", 0))
        self.addCleanup(client.close)
        self.addCleanup(server.close)
        return download(client, server.addr, len(SEGMENTS), 100, window,
                        max_retries, **kwargs)

    def test_downloads_all_segments(self):
        result = self.run_download(FakeServer())
        self.assertEqual(result.content, b"".join(SEGMENTS))
        self.assertEqual(result.retransmissions, 0)
        self.assertEqual([s.seq for s in result.segments], [0, 1, 2, 3, 4])

    def test_window_limits_requests_in_flight(self):
        # O DATA 0 se perde: com janela 2, o REQ 2 só sai depois que o 0 chega.
        server = FakeServer(drop={(0, 1)})
        result = self.run_download(server, window=2)
        self.assertEqual(result.content, b"".join(SEGMENTS))
        self.assertEqual(server.reqs[:4], [0, 1, 0, 2])

    def test_retransmits_only_the_lost_segment(self):
        server = FakeServer(drop={(1, 1)})
        result = self.run_download(server)
        self.assertEqual(result.content, b"".join(SEGMENTS))
        self.assertEqual([s.retransmissions for s in result.segments],
                         [0, 1, 0, 0, 0])
        self.assertEqual(sorted(server.reqs), [0, 1, 1, 2, 3, 4])

    def test_buffers_out_of_order_data(self):
        # DATA 0 chega depois do DATA 1: é guardado, sem retransmissão.
        result = self.run_download(FakeServer(delay={0}))
        self.assertEqual(result.content, b"".join(SEGMENTS))
        self.assertEqual(result.retransmissions, 0)
        received_order = sorted(result.segments, key=lambda s: s.received_at)
        self.assertEqual(received_order[0].seq, 1)

    def test_discards_duplicates(self):
        result = self.run_download(FakeServer(dup={0, 2}))
        self.assertEqual(result.content, b"".join(SEGMENTS))
        self.assertEqual(len(result.segments), len(SEGMENTS))

    def test_simulated_loss_is_recorded(self):
        result = self.run_download(FakeServer(), max_retries=10, loss=0.5,
                                   seed=1)
        self.assertEqual(result.content, b"".join(SEGMENTS))
        lost = [s for s in result.segments if s.loss_simulated]
        self.assertTrue(lost)
        for s in lost:
            self.assertGreater(s.retransmissions, 0)

    def test_fixed_timeout_by_default(self):
        result = self.run_download(FakeServer())
        self.assertEqual({s.timeout_ms for s in result.segments}, {100})

    def test_adaptive_timeout_varies_and_skips_retransmitted(self):
        server = FakeServer(drop={(1, 1)})
        result = self.run_download(server, window=1, adaptive=True)
        self.assertEqual(result.content, b"".join(SEGMENTS))
        by_seq = {s.seq: s for s in result.segments}
        self.assertEqual(by_seq[0].timeout_ms, 100)   # ainda sem amostra
        later = [by_seq[i].timeout_ms for i in (2, 3, 4)]
        self.assertTrue(all(t < 100 for t in later))  # RTT local << 100 ms
        # Karn: o segmento retransmitido não altera a estimativa.
        self.assertEqual(by_seq[1].retransmissions, 1)
        self.assertEqual(by_seq[1].rtt_estimated_ms, by_seq[0].rtt_estimated_ms)

    def test_adaptive_timeout_floor_and_backoff(self):
        # REQ 1 perdido duas vezes: o timer dele dobra a cada retransmissão.
        server = FakeServer(drop={(1, 1), (1, 2)})
        result = self.run_download(server, window=1, adaptive=True,
                                   min_timeout_ms=20)
        self.assertEqual(result.content, b"".join(SEGMENTS))
        by_seq = {s.seq: s for s in result.segments}
        # RTT local << 20 ms: depois da 1ª amostra, vale o piso.
        self.assertEqual([by_seq[i].timeout_ms for i in (2, 3, 4)], [20] * 3)
        self.assertEqual(by_seq[1].retransmissions, 2)
        self.assertEqual(by_seq[1].timeout_ms, 80)  # 20 -> 40 -> 80

    def test_gives_up_after_max_retries(self):
        server = FakeServer(drop={(1, n) for n in range(1, 10)})
        with self.assertRaises(DownloadError) as ctx:
            self.run_download(server, max_retries=2)
        # Os segmentos que chegaram vão para o CSV mesmo com a falha.
        self.assertIn(0, [s.seq for s in ctx.exception.segments])
        self.assertNotIn(1, [s.seq for s in ctx.exception.segments])


if __name__ == "__main__":
    unittest.main()
