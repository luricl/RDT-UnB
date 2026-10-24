import socket
import unittest

from src.packets import DownloadError
from src.gbn import download
from tests.test_saw import FakeServer, SEGMENTS


class GbnTest(unittest.TestCase):
    def run_download(self, server, window=3, max_retries=3):
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.bind(("127.0.0.1", 0))
        self.addCleanup(client.close)
        self.addCleanup(server.close)
        return download(client, server.addr, len(SEGMENTS), 100, window,
                        max_retries=max_retries)

    def test_downloads_all_segments(self):
        result = self.run_download(FakeServer())
        self.assertEqual(result.content, b"".join(SEGMENTS))
        self.assertEqual(result.retransmissions, 0)
        self.assertEqual([s.seq for s in result.segments], [0, 1, 2])

    def test_window_larger_than_file(self):
        result = self.run_download(FakeServer(), window=10)
        self.assertEqual(result.content, b"".join(SEGMENTS))

    def test_window_of_one_behaves_like_saw(self):
        result = self.run_download(FakeServer(drop={(1, 1)}), window=1)
        self.assertEqual(result.content, b"".join(SEGMENTS))
        self.assertEqual([s.retransmissions for s in result.segments], [0, 1, 0])

    def test_go_back_retransmits_whole_window(self):
        # O REQ de 1 se perde. O DATA de 2 chega enquanto a base é 1 e é
        # descartado; o timeout de 1 reenvia REQ de 1 e de 2.
        result = self.run_download(FakeServer(drop={(1, 1)}), window=3)
        self.assertEqual(result.content, b"".join(SEGMENTS))
        self.assertEqual([s.retransmissions for s in result.segments], [0, 1, 1])

    def test_discards_duplicates_and_old_data(self):
        result = self.run_download(FakeServer(dup={1, 2}))
        self.assertEqual(result.content, b"".join(SEGMENTS))

    def test_partial_stats_on_failure(self):
        server = FakeServer(drop={(1, n) for n in range(1, 10)})
        with self.assertRaises(DownloadError) as ctx:
            self.run_download(server, max_retries=1)
        self.assertEqual([s.seq for s in ctx.exception.segments], [0])

    def test_gives_up_after_max_retries(self):
        server = FakeServer(drop={(0, n) for n in range(1, 10)})
        with self.assertRaises(DownloadError):
            self.run_download(server, max_retries=2)


if __name__ == "__main__":
    unittest.main()
