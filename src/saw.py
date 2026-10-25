"""Loop Stop-and-Wait do RDT-UnB v1.0: REQ -> DATA -> ACK, um segmento por vez."""

import random
import socket
import time
from dataclasses import dataclass

from src.packets import Data, PacketError, build_ack, build_req, parse
from src.rtt import RttEstimator
from src.packets import Download, DownloadError, SegmentStats, DEFAULT_MAX_RETRIES, RECV_BUFFER


def wait_for_data(sock, server_addr, expected_seq, timeout_s, loss=0.0,
                  rng=None, loss_flags=None):
    """Espera até `timeout_s` segundos pelo `DATA` com `seq == expected_seq`.

    `loss` é a probabilidade (0 a 1) de simular perda de rede sobre o `DATA`
    recebido; `rng` é o gerador (random.Random) usado para a decisão, e
    `loss_flags` (lista opcional) recebe um True cada vez que uma perda é
    simulada, para que o chamador saiba se o segmento teve alguma perda.

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

        if not (isinstance(packet, Data) and packet.seq == expected_seq):
            continue

        # descartar o DATA recebido com probabilidade P, deixando
        # o laço continuar esperando até o timeout real.
        # desabilitado por default (loss deve ser > 0)
        if loss > 0.0 and rng.random() < loss:
            loss_flags.append(True)
            continue

        return packet


def download(sock, server_addr, total_segments, timeout_ms,
             max_retries=DEFAULT_MAX_RETRIES, loss=0.0, seed=0):
    """Baixa todos os segmentos em Stop-and-Wait e remonta o arquivo.

    `loss` e `seed` controlam a simulação de perda (item T11, issue #9):
    `loss` é a probabilidade (0 a 1) de simular perda sobre cada DATA
    recebido, e `seed` torna a sequência de decisões reproduzível entre
    execuções.
    """
    payloads = []
    stats = []
    estimator = RttEstimator()
    rng = random.Random(seed)

    for seq in range(total_segments):
        req = build_req(seq)
        first_sent_at = time.monotonic()
        loss_flags = []
        for attempt in range(max_retries + 1):
            sock.sendto(req, server_addr)
            sent_at = time.monotonic()
            data = wait_for_data(sock, server_addr, seq, timeout_ms / 1000,
                                 loss=loss, rng=rng, loss_flags=loss_flags)
            if data is not None:
                break
        else:
            raise DownloadError(
                f"segmento {seq}: sem resposta após {max_retries} retransmissões",
                segments=stats)

        now = time.monotonic()
        # RTT medido a partir do último REQ: com retransmissão não dá para
        # saber a qual REQ o DATA responde (algoritmo de Karn).
        rtt_ms = (now - sent_at) * 1000
        # Pelo mesmo motivo (Karn), só amostras sem retransmissão alimentam a
        # estimativa EWMA; nas outras a estimativa anterior é mantida.
        if attempt == 0:
            estimator.update(rtt_ms)
        stats.append(SegmentStats(seq=seq, received_at=time.time(),
                                  size_bytes=len(data.payload), rtt_ms=rtt_ms,
                                  retransmissions=attempt,
                                  rtt_estimated_ms=estimator.estimated_ms,
                                  timeout_ms=timeout_ms,
                                  elapsed_ms=(now - first_sent_at) * 1000,
                                  loss_simulated=bool(loss_flags)))
        payloads.append(data.payload)
        sock.sendto(build_ack(seq), server_addr)

    return Download(content=b"".join(payloads), segments=stats)
