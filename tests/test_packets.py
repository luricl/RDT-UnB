import unittest

from src.packets import (
    Data, Done, Error, Ok, PacketError, Pong,
    build_ack, build_fin, build_hello, build_ping, build_req, parse,
)

# Respostas reais do servidor (grupo "teste", arquivo small).
OK_REAL = (b"OK|file_size=1048576|checksum=f5adc7ebd10d3997cfa18c8a73a7f9a5"
           b"|seed=rdtunb_teste_2026_10|total_segments=2048|segment_size=512")


def data_packet(seq, payload):
    return f"DATA|seq={seq}|total={len(payload)}|".encode() + payload


class BuildTest(unittest.TestCase):
    def test_hello(self):
        self.assertEqual(build_hello("grupo01", 512, "small"),
                         b"HELLO|grupo=grupo01|segment_size=512|file=small")

    def test_req_ack_fin_ping(self):
        self.assertEqual(build_req(0), b"REQ|seq=0")
        self.assertEqual(build_ack(2047), b"ACK|seq=2047")
        self.assertEqual(build_fin("f5adc7eb"), b"FIN|checksum=f5adc7eb")
        self.assertEqual(build_ping(), b"PING")

    def test_invalid_seq_is_refused(self):
        for seq in (-1, "3", 1.0, True):
            with self.subTest(seq=seq):
                with self.assertRaises(ValueError):
                    build_req(seq)

    def test_separator_in_field_is_refused(self):
        with self.assertRaises(ValueError):
            build_hello("a|b", 512, "small")
        with self.assertRaises(ValueError):
            build_fin("abc=def")


class ParseTest(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(parse(OK_REAL), Ok(
            file_size=1048576,
            checksum="f5adc7ebd10d3997cfa18c8a73a7f9a5",
            seed="rdtunb_teste_2026_10",
            total_segments=2048,
            segment_size=512,
        ))

    def test_data_payload_with_separator_and_zero_bytes(self):
        payload = b"a|b|c\x00\xff|=" + bytes(range(256))
        self.assertEqual(parse(data_packet(7, payload)), Data(seq=7, payload=payload))

    def test_data_empty_payload(self):
        self.assertEqual(parse(b"DATA|seq=3|total=0|"), Data(seq=3, payload=b""))

    def test_data_with_wrong_total_is_refused(self):
        with self.assertRaises(PacketError):
            parse(b"DATA|seq=0|total=512|curto")

    def test_done(self):
        self.assertEqual(parse(b"DONE|ok=1"), Done(ok=True))
        self.assertEqual(parse(b"DONE|ok=0"), Done(ok=False))

    def test_pong(self):
        self.assertEqual(parse(b"PONG|time=1791931816.249"), Pong(time=1791931816.249))

    def test_error(self):
        self.assertEqual(parse(b"ERROR|msg=tipo_desconhecido_ACK"),
                         Error(msg="tipo_desconhecido_ACK"))

    def test_malformed_packets_are_refused(self):
        for packet in (
            b"",
            b"XYZ|a=1",
            b"DATA|seq=0",
            b"DATA|seq=x|total=0|",
            b"OK|file_size=10",
            b"OK" + OK_REAL[2:].replace(b"file_size=1048576", b"file_size=muito"),
            b"DONE|ok=2",
            b"DONE|ok",
            b"PONG|time=\xff",
        ):
            with self.subTest(packet=packet):
                with self.assertRaises(PacketError):
                    parse(packet)


if __name__ == "__main__":
    unittest.main()
