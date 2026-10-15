import csv
import os
import tempfile
import time
import unittest
from datetime import datetime

from src.metrics import COLUMNS, metrics_filename, write_metrics
from src.rtt import RttEstimator
from src.saw import SegmentStats

EXPECTED_COLUMNS = [
    "segment", "timestamp", "size_bytes", "rtt_ms", "rtt_estimated_ms",
    "timeout_ms", "throughput_kbps", "retransmissions", "timeout_occurred",
    "window_size", "protocol", "loss_simulated",
]


def stat(seq, retransmissions=0, rtt_estimated_ms=20.0, loss_simulated=False):
    return SegmentStats(seq=seq, received_at=time.time(), size_bytes=512,
                        rtt_ms=20.0, retransmissions=retransmissions,
                        rtt_estimated_ms=rtt_estimated_ms, timeout_ms=1000.0,
                        elapsed_ms=20.0, loss_simulated=loss_simulated)


class MetricsFileTest(unittest.TestCase):
    def write(self, segments, **kw):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = write_metrics(segments, "grupo07", "saw", 1,
                             datetime(2026, 10, 14, 21, 5, 9),
                             directory=tmp.name, **kw)
        with open(path, newline="", encoding="utf-8") as f:
            return path, list(csv.reader(f))

    def test_filename_pattern(self):
        self.assertEqual(
            metrics_filename("grupo07", "saw", datetime(2026, 10, 14, 21, 5, 9)),
            "metrics_grupo07_saw_20261014_210509.csv")

    def test_header_has_all_columns_in_order(self):
        self.assertEqual(list(COLUMNS), EXPECTED_COLUMNS)
        path, rows = self.write([])
        self.assertEqual(rows[0], EXPECTED_COLUMNS)
        self.assertEqual(len(rows), 1)  # sessão sem segmentos: só cabeçalho
        self.assertTrue(os.path.basename(path).startswith("metrics_grupo07_saw_"))

    def test_row_values(self):
        _, rows = self.write([stat(0), stat(1, retransmissions=2,
                                            loss_simulated=True)])
        first = dict(zip(rows[0], rows[1]))
        second = dict(zip(rows[0], rows[2]))
        self.assertEqual(first["segment"], "0")
        self.assertEqual(first["size_bytes"], "512")
        self.assertEqual(first["rtt_ms"], "20.000")
        self.assertEqual(first["timeout_ms"], "1000.000")
        # 512 bytes * 8 / 20 ms = 204.8 kbit/s
        self.assertEqual(first["throughput_kbps"], "204.800")
        self.assertEqual(first["timeout_occurred"], "0")
        self.assertEqual(first["window_size"], "1")
        self.assertEqual(first["protocol"], "saw")
        self.assertEqual(first["loss_simulated"], "0")
        self.assertEqual(second["retransmissions"], "2")
        self.assertEqual(second["timeout_occurred"], "1")
        self.assertEqual(second["loss_simulated"], "1")

    def test_timestamp_is_iso8601_with_timezone(self):
        _, rows = self.write([stat(0)])
        ts = datetime.fromisoformat(rows[1][1])
        self.assertIsNotNone(ts.tzinfo)
        self.assertLess(abs(ts.timestamp() - time.time()), 60)

    def test_missing_estimate_is_blank(self):
        _, rows = self.write([stat(0, rtt_estimated_ms=None)])
        self.assertEqual(dict(zip(rows[0], rows[1]))["rtt_estimated_ms"], "")


class RttEstimatorTest(unittest.TestCase):
    def test_first_sample_initializes(self):
        est = RttEstimator()
        self.assertIsNone(est.estimated_ms)
        self.assertEqual(est.update(100.0), 100.0)

    def test_ewma(self):
        est = RttEstimator(alpha=0.125)
        est.update(100.0)
        # 0.875 * 100 + 0.125 * 200 = 112.5
        self.assertAlmostEqual(est.update(200.0), 112.5)

    def test_invalid_alpha(self):
        with self.assertRaises(ValueError):
            RttEstimator(alpha=0)


if __name__ == "__main__":
    unittest.main()
