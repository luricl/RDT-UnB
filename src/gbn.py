"""Loop Go-Back-N do RDT-UnB v1.0 (item T12, issue #10).

Igual ao Stop-and-Wait (REQ -> DATA, cliente sempre pede), mas com até
`window` REQs em voo sem terem recebido DATA, e retransmissão de toda a
janela a partir da base quando a base estoura o timeout.
"""

import random
import socket
import time

from src.packets import (Data, PacketError, build_ack, build_req, parse,
                         Download, DownloadError, SegmentStats,
                         DEFAULT_MAX_RETRIES, RECV_BUFFER)
from src.rtt import RttEstimator


def recv_any_data(sock, server_addr, timeout_s, loss=0.0, rng=None, loss_flags=None):
    """Espera por qualquer `DATA` do servidor até `timeout_s` segundos.

    Diferente de `wait_for_data` (saw.py), não filtra por `seq`: com vários
    REQs em voo, o próximo DATA a chegar pode ser de qualquer um deles.
    Devolve o `Data` recebido, ou None se o prazo estourar.
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
        if not isinstance(packet, Data):
            continue

        if loss > 0.0 and rng.random() < loss:
            loss_flags.append(packet.seq)
            continue

        return packet


def download(sock, server_addr, total_segments, timeout_ms, window_size,
             max_retries=DEFAULT_MAX_RETRIES, loss=0.0, seed=0):
    """Baixa todos os segmentos em Go-Back-N e remonta o arquivo.

    `window` é o tamanho da janela (N REQs sem DATA em voo). `loss` e `seed`
    controlam a simulação de perda, como no Stop-and-Wait (item T11).
    """
    payloads = [None] * total_segments
    stats = []
    estimator = RttEstimator()
    rng = random.Random(seed)
    loss_flags = []
    timeout_s = timeout_ms / 1000

    # Métricas por segmento: primeiro e último REQ enviados, e retransmissões.
    first_sent_at = [None] * total_segments
    last_sent_at = [None] * total_segments
    retransmissions = [0] * total_segments

    def send_req(seq):
        now = time.monotonic()
        if first_sent_at[seq] is None:
            first_sent_at[seq] = now
        last_sent_at[seq] = now
        sock.sendto(build_req(seq), server_addr)

    base_seq = 0    # seq mais antigo ainda sem DATA recebido (início da janela)
    next_seq = 0    # próximo seq ainda não pedido (fim da janela, exclusivo)
    timeouts = 0    # timeouts seguidos na mesma base; zera quando a base avança

    while base_seq < total_segments:
        # Mantém a janela cheia: pede todo seq que ainda cabe nela.
        while next_seq < min(base_seq + window_size, total_segments):
            send_req(next_seq)
            next_seq += 1

        # O prazo é contado a partir do último REQ da base, não do último DATA
        # recebido; senão DATAs de outros seqs adiariam o timeout para sempre.
        remaining = last_sent_at[base_seq] + timeout_s - time.monotonic()
        packet = recv_any_data(sock, server_addr, max(remaining, 0),
                               loss, rng, loss_flags)

        if packet is None:
            # Timeout da base: retransmite a janela inteira, do base ao último REQ.
            timeouts += 1
            if timeouts > max_retries:
                raise DownloadError(
                    f"segmento {base_seq}: sem resposta após {max_retries} retransmissões",
                    segments=stats)
            for seq in range(base_seq, next_seq):
                send_req(seq)
                retransmissions[seq] += 1
            continue

        # DATA fora da base (atrasado, duplicado ou fora de ordem) é descartado;
        # os seqs da janela que se perderem voltam pelo retransmit da base.
        if packet.seq != base_seq:
            continue

        seq = base_seq
        now = time.monotonic()
        rtt_ms = (now - last_sent_at[seq]) * 1000
        # só amostras de segmentos sem retransmissão alimentam o EWMA.
        if retransmissions[seq] == 0:
            estimator.update(rtt_ms)
        stats.append(SegmentStats(seq=seq, received_at=time.time(),
                                  size_bytes=len(packet.payload), rtt_ms=rtt_ms,
                                  retransmissions=retransmissions[seq],
                                  rtt_estimated_ms=estimator.estimated_ms,
                                  timeout_ms=timeout_ms,
                                  elapsed_ms=(now - first_sent_at[seq]) * 1000,
                                  loss_simulated=seq in loss_flags))
        payloads[seq] = packet.payload
        sock.sendto(build_ack(seq), server_addr)
        base_seq += 1
        timeouts = 0

    return Download(content=b"".join(payloads), segments=stats)
