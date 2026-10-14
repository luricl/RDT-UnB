"""Loop Stop-and-Wait do RDT-UnB v1.0: REQ -> DATA -> ACK, um segmento por vez."""

import socket
import time
from dataclasses import dataclass

from src.packets import Data, PacketError, build_ack, build_req, parse

DEFAULT_MAX_RETRIES = 10
RECV_BUFFER = 65535


class DownloadError(Exception):
    """A transferência não pôde ser concluída."""


@dataclass(frozen=True)
class SegmentStats:
    """Métricas de um segmento, base de uma linha do CSV."""
    seq: int
    received_at: float     # time.time() na chegada do DATA (mesmo relógio do Wireshark)
    size_bytes: int
    rtt_ms: float          # do último REQ enviado até o DATA
    retransmissions: int   # REQs reenviados por timeout

    @property
    def timeout_occurred(self):
        return self.retransmissions > 0


@dataclass(frozen=True)
class Download:
    content: bytes
    segments: list

    @property
    def retransmissions(self):
        return sum(s.retransmissions for s in self.segments)


def wait_for_data(sock, server_addr, expected_seq, timeout_s):
    """Espera até `timeout_s` segundos pelo `DATA` com `seq == expected_seq`.

    Devolve o `Data` esperado, ou None se o prazo estourar.
    """
    deadline = time.monotonic() + timeout_s

    while True:
        time_left = deadline - time.monotonic()
        if time_left <= 0:
            return None
        sock.settimeout(time_left)
        try:
            raw, addr = sock.recvfrom(RECV_BUFFER)
        except socket.timeout:
            return None

        if addr != server_addr:
            continue
        try:
            packet = parse(raw)
        except PacketError:
            continue

        # Duplicata de segmento já confirmado ou fora de ordem: descarta.
        if isinstance(packet, Data) and packet.seq == expected_seq:
            return packet


def download(sock, server_addr, total_segments, timeout_ms,
             max_retries=DEFAULT_MAX_RETRIES):
    """Baixa todos os segmentos em Stop-and-Wait e remonta o arquivo."""
    payloads = []
    stats = []

    for seq in range(total_segments):
        req = build_req(seq)
        for attempt in range(max_retries + 1):
            sock.sendto(req, server_addr)
            sent_at = time.monotonic()
            data = wait_for_data(sock, server_addr, seq, timeout_ms / 1000)
            if data is not None:
                break
        else:
            raise DownloadError(
                f"segmento {seq}: sem resposta após {max_retries} retransmissões")

        # RTT medido a partir do último REQ: com retransmissão não dá para
        # saber a qual REQ o DATA responde (algoritmo de Karn).
        rtt_ms = (time.monotonic() - sent_at) * 1000
        stats.append(SegmentStats(seq=seq, received_at=time.time(),
                                  size_bytes=len(data.payload), rtt_ms=rtt_ms,
                                  retransmissions=attempt))
        payloads.append(data.payload)
        sock.sendto(build_ack(seq), server_addr)

    return Download(content=b"".join(payloads), segments=stats)
